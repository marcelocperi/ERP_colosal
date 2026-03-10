from apps.core.services.numeration_service import NumerationService
from .afip_service import AfipService
import json
import logging

logger = logging.getLogger(__name__)

class BillingService:
    @staticmethod
    def process_invoice(user_data, payload):
        """
        Procesa una factura completa: numeración, guardado, contabilidad y AFIP.
        Optimizado para entornos multi-tenant asíncronos.
        """
        enterprise_id = user_data['enterprise_id']
        user_id = user_data['id']
        
        try:
            with get_db_cursor(dictionary=True) as cursor:
                # 1. Datos básicos y numeración
                punto_venta = payload.get('punto_venta', 1)
                tipo_comp = payload['tipo_comprobante']
                
                cursor.execute("SELECT letra FROM sys_tipos_comprobante WHERE codigo = %s", (tipo_comp,))
                tipo_row = dictfetchone(cursor)
                letra = tipo_row['letra'] if tipo_row else 'X'

                # Obtenemos el próximo número dentro de la transacción
                numero = NumerationService.get_next_number(enterprise_id, 'COMPROBANTE', tipo_comp, punto_venta, cursor)

                # 2. Cálculos de totales
                neto = Decimal('0.00')
                iva = Decimal('0.00')
                total = Decimal('0.00')
                
                for item in payload['items']:
                    cant = Decimal(str(item['cantidad']))
                    precio = Decimal(str(item['precio']))
                    alic = Decimal(str(item['alic_iva']))
                    
                    sub_neto = (cant * precio).quantize(Decimal('0.01'))
                    sub_iva = (sub_neto * (alic / Decimal('100'))).quantize(Decimal('0.01'))
                    
                    neto += sub_neto
                    iva += sub_iva
                    total += (sub_neto + sub_iva)

                # 3. Guardar Cabecera (Estado inicial PENDING)
                cursor.execute("""
                    INSERT INTO erp_comprobantes (
                        enterprise_id, modulo, tercero_id, tipo_comprobante, letra,
                        punto_venta, numero, fecha_emision, importe_neto, importe_iva, importe_total,
                        estado_pago, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, %s, %s, %s, 'PENDIENTE', %s)
                """, (enterprise_id, 'VENTAS', payload['cliente_id'], tipo_comp, letra,
                      punto_venta, numero, neto, iva, total, user_id))
                
                cursor.execute("SELECT LAST_INSERT_ID() as last_id")
                comprobante_id = dictfetchone(cursor)['last_id']

                # 4. Guardar Detalles
                for item in payload['items']:
                    cant = Decimal(str(item['cantidad']))
                    precio = Decimal(str(item['precio']))
                    alic = Decimal(str(item['alic_iva']))
                    item_neto = (cant * precio).quantize(Decimal('0.01'))
                    item_iva = (item_neto * (alic / Decimal('100'))).quantize(Decimal('0.01'))
                    
                    cursor.execute("""
                        INSERT INTO erp_comprobantes_detalle (
                            comprobante_id, articulo_id, nombre, cantidad, precio_unitario,
                            alicuota_iva, importe_neto, importe_iva, importe_total, enterprise_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (comprobante_id, item['id'], item['nombre'], cant, precio,
                          alic, item_neto, item_iva, item_neto + item_iva, enterprise_id))

                # 5. Contabilidad (Generar asiento)
                BillingService._generar_asiento_contable(enterprise_id, comprobante_id, cursor)
                
                # Actualizar último número en el maestro para evitar colisiones
                NumerationService.update_last_number(enterprise_id, 'COMPROBANTE', tipo_comp, punto_venta, numero, cursor)

            # 6. AFIP (Fuera de la transacción principal para evitar bloqueos largos)
            # El sistema "espera" aquí la respuesta para el modo síncrono del cliente
            afip_res = AfipService.solicitar_cae(enterprise_id, comprobante_id)

            return {
                'success': True,
                'id': comprobante_id,
                'numero': numero,
                'afip': afip_res
            }

        except Exception as e:
            logger.exception("Error en BillingService.process_invoice")
            return {'success': False, 'message': str(e)}

    @staticmethod
    def _generar_asiento_contable(enterprise_id, comprobante_id, cursor):
        """Mismo método que estaba en views.py, encapsulado en el servicio."""
        cursor.execute("SELECT * FROM erp_comprobantes WHERE id = %s", (comprobante_id,))
        comp = dictfetchone(cursor)
        if not comp: return
        
        cursor.execute("""
            INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, comprobante_id, estado)
            VALUES (%s, %s, %s, 'VENTAS', %s, 'CONFIRMADO')
        """, (enterprise_id, comp['fecha_emision'], f"Venta Comp. {comp['tipo_comprobante']} {comp['numero']}", comprobante_id))
        
        cursor.execute("SELECT LAST_INSERT_ID() as last_id")
        asiento_id = dictfetchone(cursor)['last_id']

        # Asientos simplificados (basado en el código original)
        cursor.execute("""
            INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
            SELECT %s, id, %s, 0, 'Deudores por Ventas' FROM cont_plan_cuentas WHERE codigo = '1.3.01' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
        """, (asiento_id, comp['importe_total'], enterprise_id))

        cursor.execute("""
            INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
            SELECT %s, id, 0, %s, 'Ventas' FROM cont_plan_cuentas WHERE codigo = '4.1' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
        """, (asiento_id, comp['importe_neto'], enterprise_id))

        if comp.get('importe_iva') and float(comp['importe_iva']) > 0:
            cursor.execute("""
                INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
                SELECT %s, id, 0, %s, 'IVA Débito Fiscal' FROM cont_plan_cuentas WHERE codigo = '2.2.01' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
            """, (asiento_id, comp['importe_iva'], enterprise_id))

        cursor.execute("UPDATE erp_comprobantes SET asiento_id = %s WHERE id = %s", (asiento_id, comprobante_id))
    @staticmethod
    def calculate_item_totals(cantidad, precio_unitario, alicuota_iva):
        """Calcula los totales para un ítem de factura."""
        qty = Decimal(str(cantidad))
        price = Decimal(str(precio_unitario))
        iva_rate = Decimal(str(alicuota_iva)) / Decimal('100')
        
        neto = (qty * price).quantize(Decimal('0.01'))
        iva = (neto * iva_rate).quantize(Decimal('0.01'))
        total = neto + iva
        
        return {
            'neto': neto,
            'iva': iva,
            'total': total
        }

    @staticmethod
    def is_monotributo(condicion):
        if not condicion: return False
        c = str(condicion).upper()
        return 'MONOTRIBUTO' in c or 'MONOTRIBUTISTA' in c

    @staticmethod
    def determine_invoice_type(emisor_tipo, cliente_tipo):
        """Determina el tipo de comprobante AFIP (001=A, 006=B, 011=C)."""
        if BillingService.is_monotributo(emisor_tipo):
            return '011' # Factura C
            
        emisor = str(emisor_tipo).upper()
        cliente = str(cliente_tipo).upper()
        
        if 'RESPONSABLE INSCRIPTO' in emisor:
            if 'RESPONSABLE INSCRIPTO' in cliente:
                return '001' # Factura A
            else:
                return '006' # Factura B
        
        return '006' # Default B

    @staticmethod
    def get_nc_type(tipo_factura):
        """Devuelve el tipo de Nota de Crédito correspondiente a un tipo de Factura."""
        mapping = {
            '001': '003', # Factura A -> NC A
            '006': '008', # Factura B -> NC B
            '011': '013', # Factura C -> NC C
            '002': '003', # ND A -> NC A
            '007': '008', # ND B -> NC B
            '012': '013', # ND C -> NC C
        }
        return mapping.get(str(tipo_factura), '008')

    @staticmethod
    def get_allowed_comprobantes(emisor_tipo, receptor_tipo, existing_cursor=None):
        # Normalizar para búsqueda
        emisor = (emisor_tipo or '').upper().replace(' ', '_')
        if 'MONOTRIBUTO' in emisor:
            emisor = 'MONOTRIBUTISTA'
            
        receptor = (receptor_tipo or '').upper().replace(' ', '_')
        if 'MONOTRIBUTO' in receptor:
            receptor = 'MONOTRIBUTISTA'
            
        if not receptor: receptor = '*'

        if existing_cursor:
            return BillingService._logic_allowed_comprobantes(emisor, receptor, existing_cursor)
        
        with get_db_cursor(dictionary=True) as cursor:
            return BillingService._logic_allowed_comprobantes(emisor, receptor, cursor)

    @staticmethod
    def _logic_allowed_comprobantes(emisor, receptor, cursor):
        cursor.execute("""
            SELECT allowed_codigos FROM sys_fiscal_comprobante_rules 
            WHERE (emisor_condicion = %s OR emisor_condicion = '*') 
              AND (receptor_condicion = %s OR receptor_condicion = '*')
            ORDER BY 
                (CASE WHEN emisor_condicion = '*' THEN 0 ELSE 1 END +
                 CASE WHEN receptor_condicion = '*' THEN 0 ELSE 1 END) DESC
            LIMIT 1
        """, (emisor, receptor))
        row = dictfetchone(cursor)
        return row['allowed_codigos'].split(',') if row else []

    @staticmethod
    def get_layout(enterprise_id, existing_cursor=None):
        if existing_cursor:
            return BillingService._logic_get_layout(enterprise_id, existing_cursor)
        
        with get_db_cursor(dictionary=True) as cursor:
            return BillingService._logic_get_layout(enterprise_id, cursor)

    @staticmethod
    def _logic_get_layout(enterprise_id, cursor):
        cursor.execute("SELECT * FROM sys_invoice_layouts WHERE enterprise_id = %s", (enterprise_id,))
        layout = dictfetchall(cursor)
        
        if not layout:
            cursor.execute("SELECT * FROM sys_invoice_layouts WHERE enterprise_id = 0")
            layout = dictfetchall(cursor)
    
        return {item['field_name']: item for item in layout}

    @staticmethod
    def prepare_invoice_values(c, detalles, empresa, cliente_dir, impuestos):
        tipo_comp = str(c.get('tipo_comprobante', ''))
        es_remito = tipo_comp in ['091', '099', 'REMITO']
        
        letra = c.get('letra', 'B')
        if es_remito:
            letra = 'R' if tipo_comp == '091' else 'X'
        
        entrega_str = '—'
        if c.get('entrega_calle'):
             entrega_str = f"{c['entrega_calle']} {c.get('entrega_numero','')} - {c.get('entrega_localidad','')}, {c.get('entrega_provincia','')}"
             if c.get('receptor_nombre'):
                 entrega_str = f"ENTREGAR A: {c['receptor_nombre']} | " + entrega_str

        static_logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
        logo_path = empresa.get('logo_path') or static_logo_path

        import datetime
        def format_date(d):
            if isinstance(d, datetime.date) or isinstance(d, datetime.datetime):
                return d.strftime('%d/%m/%Y')
            return str(d or '')

        vals = {
            'letra': letra,
            'tipo_comprobante_nombre': 'REMITO' if es_remito else c.get('tipo_nombre', '').replace('Factura A', 'Factura').replace('Factura B', 'Factura').replace('Factura C', 'Factura').replace('Nota de Crédito A', 'Nota de Crédito').replace('Nota de Crédito B', 'Nota de Crédito').replace('Nota de Crédito C', 'Nota de Crédito').replace('Nota de Débito A', 'Nota de Débito').replace('Nota de Débito B', 'Nota de Débito').replace('Nota de Débito C', 'Nota de Débito').upper(),
            'tipo_comprobante_codigo': f"COD. {c.get('tipo_comprobante', '')}",
            'punto_venta': f"{c.get('punto_venta', 0):05d}",
            'numero': f"{c.get('numero', 0):08d}",
            'cot': c.get('cot', ''),
            'fecha_emision': format_date(c.get('fecha_emision')),
            'emisor_nombre': empresa.get('nombre', '').upper() if empresa else '',
            'emisor_razon_social': empresa.get('nombre', '') if empresa else '',
            'emisor_cuit': empresa.get('cuit', '') if empresa else '',
            'emisor_domicilio': (empresa.get('domicilio', '') or empresa.get('direccion', '')) if empresa else '',
            'emisor_iibb': empresa.get('ingresos_brutos', '') if empresa else '',
            'emisor_inicio_actividades': format_date(empresa.get('inicio_actividades')) if empresa else '',
            'emisor_condicion_iva': empresa.get('condicion_iva', 'Responsable Inscripto') if empresa else 'Responsable Inscripto',
            'periodo_desde': format_date(c.get('fecha_emision')),
            'periodo_hasta': format_date(c.get('fecha_emision')),
            'vencimiento_pago': format_date(c.get('fecha_vencimiento') or c.get('fecha_emision')),
            'cliente_nombre': c.get('cliente_nombre', ''),
            'cliente_cuit': c.get('cliente_cuit', ''),
            'cliente_condicion_iva': c.get('cliente_condicion', ''),
            'cliente_domicilio': f"{cliente_dir['calle']} {cliente_dir['numero']} - {cliente_dir.get('localidad', '')}, {cliente_dir.get('provincia', '')}" if cliente_dir else '—',
            'entrega_domicilio': entrega_str,
            'condicion_venta': c.get('estado_pago', 'PENDIENTE'),
            'referencia_comercial': c.get('referencia_comercial', ''),
            'comprobante_asociado': f"Comprobante Asociado: {c.get('asoc_punto_venta', 0):04d}-{c.get('asoc_numero', 0):08d}" if c.get('comprobante_asociado_id') else '',
            'logo_path': logo_path,
            'total_subtotal_value': BillingService.format_money(c.get('importe_neto', 0) if not BillingService.is_monotributo(empresa.get('condicion_iva') if empresa else None) else c.get('importe_total', 0)),
            'total_otros_value': BillingService.format_money(sum(float(i['importe']) for i in impuestos) if impuestos else 0),
            'total_total_value': BillingService.format_money(c.get('importe_total', 0)),
            'cae_value': c.get('cae', '—') or '—',
            'vto_cae_value': format_date(c.get('vto_cae')) or '—',
            'label_punto_venta': 'Punto de Venta:',
            'label_numero': 'Comp. Nro:',
            'label_fecha_emision': 'Fecha de Emisión:',
            'label_emisor_rsocial': 'Razón Social:',
            'label_emisor_cuit': 'CUIT:',
            'label_emisor_domicilio': 'Domicilio Comercial:',
            'label_emisor_iibb': 'Ingresos Brutos:',
            'label_emisor_inicio': 'Fecha de Inicio de Actividades:',
            'label_emisor_iva': 'Condición frente al IVA:',
            'label_periodo_desde': 'Período Facturado Desde:',
            'label_periodo_hasta': 'Hasta:',
            'label_vencimiento_pago': 'Fecha de Vto. para el pago:',
            'label_cliente_rsocial': 'Destinatario de los Bienes:' if es_remito else 'Apellido y Nombre / Razón Social:',
            'label_cliente_cuit': 'CUIT:',
            'label_cliente_iva': 'Condición frente al IVA:',
            'label_cliente_domicilio': 'Domicilio Fiscal:' if es_remito else 'Domicilio:',
            'label_entrega_domicilio': 'Lugar de Entrega:' if es_remito else '',
            'label_condicion_venta': 'Condición de venta:' if not es_remito else 'Estado de Entrega:',
            'label_referencia': 'COT / Referencia:' if es_remito else 'Referencia Comercial:',
            'label_comprobante_asociado': 'Comprobante Asociado:' if c.get('comprobante_asociado_id') else '',
            'label_disclaimer': 'DOCUMENTO NO VÁLIDO COMO FACTURA' if es_remito else 'Esta Agencia no se responsabiliza por los datos ingresados en el detalle de la operación',
            'col_codigo': 'Código',
            'col_producto': 'Producto / Servicio',
            'col_cantidad': 'Cantidad',
            'col_medida': 'U. Medida',
            'col_precio': 'Precio Unit.',
            'col_bonif_pct': '% Bonif',
            'col_bonif_imp': 'Imp. Bonif.',
            'col_subtotal': 'Subtotal',
            'label_total_subtotal': 'Subtotal: $',
            'label_total_otros': 'Importe Otros Tributos: $',
            'label_total_total': 'Importe Total: $',
            'label_cae': 'CAE N°:',
            'label_vto_cae': 'Fecha de Vto. de CAE:',
            'label_autorizado': 'Comprobante Autorizado',
            'qr_code': BillingService._generate_qr(c, empresa, cliente_dir),
            'barcode': BillingService._generate_barcode(c, empresa)
        }
        return vals

    @staticmethod
    def _generate_qr(c, empresa, cliente_dir):
        try:
            from .barcode_service import BarcodeService
            return BarcodeService.generate_afip_qr(c, empresa, cliente_dir)
        except Exception as e:
            print(f"Error generando QR: {e}")
            return None

    @staticmethod
    def _generate_barcode(c, empresa):
        try:
            from .barcode_service import BarcodeService
            return BarcodeService.generate_afip_barcode(
                empresa.get('cuit', ''),
                c.get('tipo_comprobante', ''),
                c.get('punto_venta', 0),
                c.get('cae', ''),
                c.get('vto_cae', '')
            )
        except Exception as e:
            print(f"Error generando Barcode: {e}")
            return None

    @staticmethod
    def format_money(value):
        try:
            return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "0,00"
