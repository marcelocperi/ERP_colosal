import json
import datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
from .utils import parse_dynamic_barcode
from .billing_service import BillingService

@login_required
def api_cliente_logistica(request, id):
    enterprise_id = request.user.enterprise_id
    with get_db_cursor(dictionary=True) as cursor:
        # Direcciones de entrega
        cursor.execute("""
            SELECT id, etiqueta, calle, numero, localidad, provincia 
            FROM erp_direcciones 
            WHERE tercero_id = %s AND enterprise_id = %s
        """, (id, enterprise_id))
        direcciones = dictfetchall(cursor)
        
        # Contactos Receptores
        cursor.execute("""
            SELECT id, nombre, puesto, direccion_id 
            FROM erp_contactos 
            WHERE tercero_id = %s AND enterprise_id = %s 
            AND (es_receptor = 1 OR tipo_contacto = 'LOGISTICA')
        """, (id, enterprise_id))
        receptores = dictfetchall(cursor)
        
    return JsonResponse({
        'direcciones': direcciones,
        'receptores': receptores
    })

@login_required
def api_cliente_finanzas(request, id):
    enterprise_id = request.user.enterprise_id
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT erp_terceros.condicion_pago_id, fin_condiciones_pago.nombre as condicion_nombre, 
                   fin_condiciones_pago.dias_vencimiento, fin_condiciones_pago.descuento_pct
            FROM erp_terceros
            LEFT JOIN fin_condiciones_pago ON erp_terceros.condicion_pago_id = fin_condiciones_pago.id
            WHERE erp_terceros.id = %s AND erp_terceros.enterprise_id = %s
        """, (id, enterprise_id))
        data = dictfetchone(cursor) or {}

        # Datos Fiscales (Percepciones)
        cursor.execute("""
            SELECT jurisdiccion, alicuota 
            FROM erp_datos_fiscales 
            WHERE tercero_id = %s AND enterprise_id = %s
        """, (id, enterprise_id))
        data['datos_fiscales'] = dictfetchall(cursor)

    return JsonResponse(data)

@login_required
def api_cliente_saldo(request, id):
    enterprise_id = request.user.enterprise_id
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT 
                    monto_cta_cte, 
                    habilita_cta_cte,
                    estado_cta_cte_aprobacion,
                    cta_cte_pendiente_monto
                FROM erp_terceros 
                WHERE id = %s AND enterprise_id = %s
            """, (id, enterprise_id))
            cliente = dictfetchone(cursor)
            
            monto_cta_cte = float(cliente['monto_cta_cte']) if cliente and cliente['monto_cta_cte'] else 0.0
            habilita = cliente['habilita_cta_cte'] if cliente else 0
            estado_pendiente = cliente['estado_cta_cte_aprobacion'] if cliente else None
            monto_pendiente = float(cliente['cta_cte_pendiente_monto']) if cliente and cliente['cta_cte_pendiente_monto'] else 0.0

            DEBITO_TIPOS = "('001','002','006','007','011','012','005','010','015')"
            NC_TIPOS     = "('003','008','013')"
            
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN tipo_comprobante IN {DEBITO_TIPOS} THEN importe_total ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN tipo_comprobante IN {NC_TIPOS} THEN importe_total ELSE 0 END), 0) AS saldo_comp
                FROM erp_comprobantes 
                WHERE tercero_id = %s AND enterprise_id = %s AND modulo IN ('VEN', 'VENTAS')
            """, (id, enterprise_id))
            comp_res = dictfetchone(cursor)
            saldo_comp = float(comp_res['saldo_comp']) if comp_res else 0.0
            
            cursor.execute("""
                SELECT COALESCE(SUM(importe), 0) as saldo_recibos 
                FROM fin_recibos_detalles rd 
                JOIN fin_recibos r ON rd.recibo_id = r.id 
                WHERE r.tercero_id = %s AND r.enterprise_id = %s
            """, (id, enterprise_id))
            rec_res = dictfetchone(cursor)
            saldo_rec = float(rec_res['saldo_recibos']) if rec_res else 0.0
            
            saldo_total = saldo_comp - saldo_rec
            
        return JsonResponse({
            'success': True,
            'saldo': saldo_total, 
            'monto_cta_cte': monto_cta_cte,
            'habilita_cta_cte': habilita,
            'estado_pendiente': estado_pendiente,
            'monto_pendiente': monto_pendiente
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_cliente_condiciones(request, id):
    enterprise_id = request.user.enterprise_id
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT condicion_pago_id, condicion_mixta_id FROM erp_terceros WHERE id = %s", (id,))
        res = dictfetchone(cursor)
        master_id = res['condicion_pago_id'] if res else None
        mixta_id = res['condicion_mixta_id'] if res else None

        ids_maestra = set()
        if mixta_id:
            cursor.execute("""
                SELECT condicion_pago_id FROM fin_condiciones_pago_mixtas_detalle 
                WHERE mixta_id = %s AND (enterprise_id = 0 OR enterprise_id = %s)
            """, (mixta_id, enterprise_id))
            ids_maestra = {r['condicion_pago_id'] for r in dictfetchall(cursor)}
        elif master_id:
            ids_maestra = {master_id}

        if not ids_maestra:
            cursor.execute("SELECT id FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1", (enterprise_id,))
            condiciones = dictfetchall(cursor)
        else:
            placeholders = ', '.join(['%s'] * len(ids_maestra))
            cursor.execute(f"""
                SELECT id, nombre, dias_vencimiento, descuento_pct, 0 as is_mixed
                FROM fin_condiciones_pago 
                WHERE id IN ({placeholders}) AND activo = 1
            """, list(ids_maestra))
            condiciones = dictfetchall(cursor)

    return JsonResponse(condiciones, safe=False)

@login_required
def api_articulos_buscar(request):
    naturaleza = request.GET.get('naturaleza', '')
    query = request.GET.get('q', '').strip()
    enterprise_id = request.user.enterprise_id
    
    with get_db_cursor(dictionary=True) as cursor:
        parsed = parse_dynamic_barcode(query, enterprise_id, cursor)
        search_query = query
        found_dynamic = False
        dynamic_value = None

        if parsed:
            search_query = parsed['sku_plu']
            found_dynamic = True
            dynamic_value = parsed['valor']

        sql = """
            SELECT stk_articulos.id, stk_articulos.nombre, stk_articulos.precio_venta AS precio, 
                   stk_tipos_articulo.naturaleza, stk_articulos.codigo, stk_articulos.unidad_medida,
                   COALESCE(stk_articulos_codigos.codigo, '') AS sku_proveedor
            FROM stk_articulos
            LEFT JOIN stk_tipos_articulo ON stk_articulos.tipo_articulo_id = stk_tipos_articulo.id
            LEFT JOIN stk_articulos_codigos ON stk_articulos.id = stk_articulos_codigos.articulo_id 
                 AND stk_articulos_codigos.enterprise_id = stk_articulos.enterprise_id
            WHERE stk_articulos.enterprise_id = %s AND stk_articulos.activo = 1
        """
        params = [enterprise_id]
        
        if naturaleza:
            sql += " AND stk_tipos_articulo.naturaleza = %s"
            params.append(naturaleza)
            
        if search_query:
            if found_dynamic:
                sql += " AND (stk_articulos.codigo = %s OR stk_articulos_codigos.codigo = %s)"
                params.extend([search_query, search_query])
            else:
                sql += """ AND (stk_articulos.nombre LIKE %s OR stk_articulos.codigo LIKE %s 
                           OR stk_articulos_codigos.codigo LIKE %s OR stk_tipos_articulo.nombre LIKE %s)"""
                search = f"%{search_query}%"
                params.extend([search, search, search, search])
            
        sql += " ORDER BY stk_articulos.nombre LIMIT 100"
        
        cursor.execute(sql, params)
        articulos = dictfetchall(cursor)

        if found_dynamic and articulos:
            for a in articulos:
                a['dynamic_barcode'] = True
                a['dynamic_value'] = dynamic_value
                a['dynamic_type'] = parsed['tipo']
    
    return JsonResponse(articulos, safe=False)

@login_required
def api_ventas_fiscal_allowed_docs(request):
    tipo_responsable = request.GET.get('tipo_responsable', '')
    enterprise_id = request.user.enterprise_id
    
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT condicion_iva FROM sys_enterprises WHERE id = %s", (enterprise_id,))
        empresa = dictfetchone(cursor)
        emisor_tipo = empresa['condicion_iva'] if empresa else 'Responsable Inscripto'
    
    docs = BillingService.get_allowed_comprobantes(emisor_tipo, tipo_responsable) or []
    # Map to the format expected by frontend (codigo, descripcion, letra)
    with get_db_cursor(dictionary=True) as cursor:
        if docs:
            placeholders = ', '.join(['%s'] * len(docs))
            cursor.execute(f"SELECT codigo, descripcion, letra FROM sys_tipos_comprobante WHERE codigo IN ({placeholders})", list(docs))
            docs_data = dictfetchall(cursor)
            return JsonResponse(docs_data, safe=False)
            
    return JsonResponse([], safe=False)
