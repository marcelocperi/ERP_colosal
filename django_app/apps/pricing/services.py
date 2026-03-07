from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
import decimal
import logging
import datetime

logger = logging.getLogger(__name__)

class PricingService:
    @staticmethod
    def get_base_cost(cursor, article_id, method_code):
        """
        Determina el costo base de un artículo según el método solicitado.
        """
        cursor.execute("""
            SELECT costo, costo_reposicion, costo_importacion_ultimo, metodo_costeo
            FROM stk_articulos WHERE id = %s
        """, [article_id])
        art = dictfetchone(cursor)
        if not art:
            return decimal.Decimal('0.0000')
        
        costo_avg = art.get('costo')
        costo_repo = art.get('costo_reposicion')
        costo_imp = art.get('costo_importacion_ultimo')
        
        # Mapeo de métodos a columnas de stk_articulos
        if method_code == 'WAC':
            return costo_avg or decimal.Decimal('0.0000')
        elif method_code == 'REPOSICION':
            return costo_repo or costo_avg or decimal.Decimal('0.0000')
        elif method_code == 'IMPORTACION':
            return costo_imp or costo_avg or decimal.Decimal('0.0000')
        else:
            # Por defecto usamos el costo guardado en el artículo
            return costo_avg or decimal.Decimal('0.0000')

    @classmethod
    def calculate_list_prices(cls, enterprise_id, lista_id, user_id):
        """
        Genera propuestas de precios basadas en las reglas configuradas.
        No aplica el precio directamente, lo deja en estado PENDIENTE.
        """
        with get_db_cursor() as cursor:
            # 1. Obtener Reglas
            cursor.execute("""
                SELECT stk_pricing_reglas.naturaleza, stk_pricing_reglas.metodo_costo_id, stk_pricing_reglas.coeficiente_markup, stk_metodos_costeo.codigo as metodo_codigo
                FROM stk_pricing_reglas
                JOIN stk_metodos_costeo ON stk_pricing_reglas.metodo_costo_id = stk_metodos_costeo.id
                WHERE stk_pricing_reglas.lista_precio_id = %s AND stk_pricing_reglas.enterprise_id = %s
                ORDER BY stk_pricing_reglas.prioridad DESC
            """, [lista_id, enterprise_id])
            reglas = dictfetchall(cursor)
            
            if not reglas:
                return 0

            # 2. Obtener Artículos
            cursor.execute("""
                SELECT id, naturaleza, nombre 
                FROM stk_articulos 
                WHERE enterprise_id = %s OR enterprise_id = 0
            """, [enterprise_id])
            articulos = dictfetchall(cursor)
            
            count = 0
            ahora = datetime.datetime.now()
            
            # 0. Verificar si hay propuestas pendientes para bloquear el recalculo (Control de Auditoría)
            cursor.execute("SELECT COUNT(*) as c FROM stk_pricing_propuestas WHERE lista_id = %s AND estado = 'PENDIENTE'", [lista_id])
            if dictfetchone(cursor)['c'] > 0:
                raise Exception("No se puede recalcular. Existe un circuito de aprobación activo con propuestas pendientes.")

            # Limpiar propuestas pendientes anteriores (esta línea ahora es solo backup por seguridad)
            cursor.execute("DELETE FROM stk_pricing_propuestas WHERE lista_id = %s AND estado = 'PENDIENTE'", [lista_id])

            for art in articulos:
                art_id = art['id']
                art_nat = art['naturaleza']
                
                regla_aplicable = None
                
                # 1. Buscar regla específica por Naturaleza exacta
                # 2. Buscar regla general ('TODOS') si no hay específica
                regla_especifica = next((r for r in reglas if r['naturaleza'] == art_nat), None)
                regla_general = next((r for r in reglas if r['naturaleza'] == 'TODOS'), None)
                
                # Respetar la prioridad o preferir la específica
                regla_aplicable = regla_especifica or regla_general
                
                if regla_aplicable:
                    r_met_id = regla_aplicable['metodo_costo_id']
                    r_markup = regla_aplicable['coeficiente_markup']
                    r_met_code = regla_aplicable['metodo_codigo']
                    
                    costo_base = cls.get_base_cost(cursor, art_id, r_met_code)
                    precio_final = costo_base * decimal.Decimal(str(r_markup))
                    
                    # Insertar Propuesta (Origen por defecto para calculate_list_prices es LISTA_PROVEEDOR)
                    cursor.execute("""
                        INSERT INTO stk_pricing_propuestas 
                        (enterprise_id, lista_id, origen, documento_origen_id, articulo_id, costo_base_snapshot, precio_sugerido, markup_aplicado, metodo_costeo_id, usuario_id_propuesta, estado)
                        VALUES (%s, %s, 'LISTA_PROVEEDOR', %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE')
                    """, [enterprise_id, lista_id, lista_id, art_id, costo_base, precio_final, r_markup, r_met_id, user_id])
                    count += 1
            
            # Notificar por Email (Lógica de notificación se añade luego)
            cls.notificar_cost_accounting(enterprise_id, lista_id, count)
            
            return count

    @staticmethod
    def notificar_cost_accounting(enterprise_id, lista_id, count):
        pass

    @classmethod
    def generar_propuestas_desde_costo(cls, enterprise_id, origen, documento_origen_id, items_data, user_id):
        """
        Inyecta variaciones de costo directamente desde un documento operativo (Importación o Remito).
        items_data format: [{'articulo_id': int, 'costo_calculado': float, 'precio_sugerido': float}]
        """
        count = 0
        with get_db_cursor() as cursor:
            # Limpiar propuestas previas de este documento (por si se edita el prorrateo antes de aprobar)
            cursor.execute("""
                DELETE FROM stk_pricing_propuestas 
                WHERE origen = %s AND documento_origen_id = %s AND estado = 'PENDIENTE'
            """, [origen, documento_origen_id])

            for item in items_data:
                precio = item.get('precio_sugerido', item['costo_calculado'])
                cursor.execute("""
                    INSERT INTO stk_pricing_propuestas 
                    (enterprise_id, origen, documento_origen_id, articulo_id, costo_base_snapshot, precio_sugerido, markup_aplicado, usuario_id_propuesta, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, 1.0, %s, 'PENDIENTE')
                """, [
                    enterprise_id, origen, documento_origen_id, item['articulo_id'], 
                    item['costo_calculado'], precio, user_id
                ])
                count += 1
        return count

    @classmethod
    def procesar_aprobacion(cls, enterprise_id, propuesta_ids, estado, motivo, user_id):
        """Aprueba o rechaza un conjunto de propuestas."""
        with get_db_cursor() as cursor:
            ahora = datetime.datetime.now()
            for pid in propuesta_ids:
                if estado == 'APROBADO':
                    # 1. Obtener datos de la propuesta
                    cursor.execute("""
                        SELECT lista_id, articulo_id, costo_base_snapshot, precio_sugerido, usuario_id_propuesta 
                        FROM stk_pricing_propuestas WHERE id = %s
                    """, [pid])
                    prop = dictfetchone(cursor)
                    if not prop: continue
                    lid, aid, costo, precio, u_propuesta = prop['lista_id'], prop['articulo_id'], prop['costo_base_snapshot'], prop['precio_sugerido'], prop['usuario_id_propuesta']
                    
                    # --- SEGREGACIÓN DE FUNCIONES (SoD) ---
                    if str(u_propuesta) == str(user_id):
                        raise Exception(f"Error SoD: No puede aprobar la propuesta #{pid} porque fue creada por usted.")
                    
                    # 2. "Cerrar" precio anterior
                    cursor.execute("""
                        UPDATE stk_articulos_precios 
                        SET fecha_fin_vigencia = %s 
                        WHERE articulo_id = %s AND lista_precio_id = %s AND fecha_fin_vigencia IS NULL
                    """, [ahora, aid, lid])
                    
                    # 3. Insertar nuevo precio oficial
                    cursor.execute("""
                        INSERT INTO stk_articulos_precios 
                        (enterprise_id, lista_precio_id, articulo_id, costo_base_snapshot, precio_final, fecha_inicio_vigencia)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [enterprise_id, lid, aid, costo, precio, ahora])
                
                # Actualizar estado de la propuesta
                cursor.execute("""
                    UPDATE stk_pricing_propuestas 
                    SET estado = %s, motivo = %s, usuario_id_aprobacion = %s, fecha_aprobacion = %s
                    WHERE id = %s AND enterprise_id = %s
                """, [estado, motivo, user_id, ahora, pid, enterprise_id])
            
            return len(propuesta_ids)
