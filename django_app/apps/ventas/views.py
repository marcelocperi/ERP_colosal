from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
from apps.core.decorators import login_required
import json
import datetime
from .billing_service import BillingService
from .afip_service import AfipService
from apps.core.services.numeration_service import NumerationService

@login_required
def dashboard(request):
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT id, nombre, cuit, codigo
                FROM erp_terceros
                WHERE enterprise_id = %s AND es_cliente = 1
                ORDER BY nombre
            """, (request.user_data['enterprise_id'],))
            clientes = dictfetchall(cursor)
        return render(request, 'ventas/dashboard.html', {'clientes': clientes})
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Raise it directly to see the error in the browser/logs 
        raise e

@login_required
def clientes(request):
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT erp_terceros.*, erp_direcciones.calle, erp_direcciones.numero, 
                       erp_direcciones.localidad, erp_direcciones.provincia 
                FROM erp_terceros
                LEFT JOIN erp_direcciones ON erp_terceros.id = erp_direcciones.tercero_id AND erp_direcciones.es_fiscal = 1
                WHERE erp_terceros.enterprise_id = %s AND erp_terceros.es_cliente = 1
                GROUP BY erp_terceros.id
            """, (request.user_data['enterprise_id'],))
            clientes_list = dictfetchall(cursor)
        return render(request, 'ventas/clientes.html', {'clientes': clientes_list})
    except Exception as e:
        import traceback
        traceback.print_exc()
        from django.contrib import messages
        messages.error(request, f"Error al cargar listado de clientes: {str(e)}")
        return redirect('ventas:dashboard')

@login_required
def nuevo_cliente(request):
    from apps.ventas.services import TerceroService
    
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        nombre = request.POST.get('nombre')
        cuit = request.POST.get('cuit')
        email = request.POST.get('email')
        tipo = request.POST.get('tipo_responsable')
        observaciones = request.POST.get('observaciones', '')
        
        # Simulación de validación (debería migrarse validation_service si es complejo)
        # Por ahora limpiamos CUIT básico
        cuit = cuit.replace('-', '').replace('.', '').replace(' ', '')
        
        from django.contrib import messages
        try:
            with get_db_cursor(dictionary=True) as cursor:
                # Validar duplicados
                cursor.execute("SELECT id FROM erp_terceros WHERE cuit = %s AND enterprise_id = %s", 
                              (cuit, request.user_data['enterprise_id']))
                if dictfetchone(cursor):
                    messages.error(request, "Error: Ya existe un tercero con ese CUIT o DNI.")
                else:
                    # Generar código si no se proveyó
                    if not codigo:
                        codigo = TerceroService.generar_siguiente_codigo(request.user_data['enterprise_id'], 'CLI')

                    cursor.execute("""
                        INSERT INTO erp_terceros (enterprise_id, codigo, nombre, cuit, email, observaciones, es_cliente, tipo_responsable, naturaleza)
                        VALUES (%s, %s, %s, %s, %s, %s, 1, %s, 'CLI')
                    """, (request.user_data['enterprise_id'], codigo, nombre, cuit, email, observaciones, tipo))
                    
                    cursor.execute("SELECT LAST_INSERT_ID() as last_id")
                    new_id = dictfetchone(cursor)['last_id']
                    
                    # Crear dirección por defecto (Casa Central)
                    cursor.execute("""
                        INSERT INTO erp_direcciones (enterprise_id, tercero_id, etiqueta, calle, numero, localidad, provincia, es_fiscal, es_entrega)
                        VALUES (%s, %s, 'Casa Central', 'A completar', '0', 'Ciudad', 'Provincia', 1, 1)
                    """, (request.user_data['enterprise_id'], new_id))
                    
                    messages.success(request, f"Cliente registrado exitosamente con el número {codigo}. Ahora puede completar los detalles.")
                    return redirect('ventas:perfil_cliente', id=new_id)
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return render(request, 'ventas/cliente_form.html')


@login_required
def perfil_cliente(request, id):
    from apps.core.services.georef_service import GeorefService
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Datos básicos
            cursor.execute("SELECT * FROM erp_terceros WHERE id = %s AND enterprise_id = %s", (id, request.user_data['enterprise_id']))
            cliente = dictfetchone(cursor)
            if not cliente:
                from django.contrib import messages
                messages.warning(request, "Cliente no encontrado.")
                return redirect('ventas:clientes')
                
            # Direcciones
            cursor.execute("SELECT * FROM erp_direcciones WHERE tercero_id = %s AND enterprise_id = %s", (id, request.user_data['enterprise_id']))
            direcciones = dictfetchall(cursor)
            
            # Contactos joining with Puestos
            cursor.execute("""
                SELECT erp_contactos.*, erp_puestos.nombre as puesto_nombre, erp_direcciones.etiqueta as direccion_nombre
                FROM erp_contactos
                LEFT JOIN erp_puestos ON erp_contactos.puesto_id = erp_puestos.id
                LEFT JOIN erp_direcciones ON erp_contactos.direccion_id = erp_direcciones.id
                WHERE erp_contactos.tercero_id = %s AND erp_contactos.enterprise_id = %s
            """, (id, request.user_data['enterprise_id']))
            contactos = dictfetchall(cursor)
            
            # Datos Fiscales
            cursor.execute("SELECT * FROM erp_datos_fiscales WHERE tercero_id = %s AND enterprise_id = %s", (id, request.user_data['enterprise_id']))
            fiscales = dictfetchall(cursor)
            
            # Condiciones de Pago
            cursor.execute("""
                SELECT erp_terceros.condicion_pago_id, erp_terceros.condicion_pago_pendiente_id, erp_terceros.estado_aprobacion_pago,
                       erp_terceros.condicion_mixta_id, fin_condiciones_pago_mixtas.nombre as mixta_nombre,
                       cp_actual.nombre as condicion_nombre, cp_pendiente.nombre as condicion_pendiente_nombre,
                       sys_users.username as aprobador_nombre, erp_terceros.fecha_aprobacion_pago
                FROM erp_terceros
                LEFT JOIN fin_condiciones_pago AS cp_actual ON erp_terceros.condicion_pago_id = cp_actual.id
                LEFT JOIN fin_condiciones_pago AS cp_pendiente ON erp_terceros.condicion_pago_pendiente_id = cp_pendiente.id
                LEFT JOIN fin_condiciones_pago_mixtas ON erp_terceros.condicion_mixta_id = fin_condiciones_pago_mixtas.id
                LEFT JOIN sys_users ON erp_terceros.id_gerente_aprobador = sys_users.id
                WHERE erp_terceros.id = %s AND erp_terceros.enterprise_id = %s
            """, (id, request.user_data['enterprise_id']))
            pago_info = dictfetchone(cursor)

            # Todas las condiciones disponibles para el modal
            cursor.execute("SELECT * FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (request.user_data['enterprise_id'],))
            condiciones_disponibles = dictfetchall(cursor)
            
            # Condiciones mixtas disponibles
            cursor.execute("SELECT * FROM fin_condiciones_pago_mixtas WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (request.user_data['enterprise_id'],))
            mixtas_disponibles = dictfetchall(cursor)

            # Marcar cuáles están habilitadas y obtener fechas + estado
            cursor.execute("SELECT condicion_pago_id, fecha_habilitacion, habilitado FROM erp_terceros_condiciones WHERE tercero_id = %s AND enterprise_id = %s", (id, request.user_data['enterprise_id']))
            habilitaciones = {r['condicion_pago_id']: {'fecha': r['fecha_habilitacion'], 'habilitado': r['habilitado']} for r in dictfetchall(cursor)}
            
            # Identificar cuáles son parte de la "Maestra"
            incluidas_en_maestra = []
            if pago_info and pago_info.get('condicion_mixta_id'):
                cursor.execute("SELECT condicion_pago_id FROM fin_condiciones_pago_mixtas_detalle WHERE mixta_id = %s AND (enterprise_id = 0 OR enterprise_id = %s)", (pago_info['condicion_mixta_id'], request.user_data['enterprise_id']))
                incluidas_en_maestra = [r['condicion_pago_id'] for r in dictfetchall(cursor)]
            elif pago_info and pago_info.get('condicion_pago_id'):
                incluidas_en_maestra = [pago_info['condicion_pago_id']]
            
            # Provincias (Georef)
            provincias = GeorefService.get_provincias()

            # Impuestos Maestros (Configurables)
            cursor.execute("SELECT id, nombre FROM sys_impuestos WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (request.user_data['enterprise_id'],))
            impuestos_lista = dictfetchall(cursor)

            # Condiciones Fiscales (AFIP)
            condiciones_fiscales = [
                {'id': 1, 'nombre': 'IVA Responsable Inscripto'},
                {'id': 2, 'nombre': 'IVA Responsable no Inscripto'},
                {'id': 3, 'nombre': 'IVA no Responsable'},
                {'id': 4, 'nombre': 'IVA Sujeto Exento'},
                {'id': 5, 'nombre': 'Consumidor Final'},
                {'id': 6, 'nombre': 'Responsable Monotributo'},
                {'id': 7, 'nombre': 'Sujeto no Categorizado'},
                {'id': 8, 'nombre': 'Proveedor del Exterior'},
                {'id': 9, 'nombre': 'Cliente del Exterior'},
                {'id': 10, 'nombre': 'IVA Liberado - Ley Nº 19.640'},
                {'id': 11, 'nombre': 'IVA Responsable Inscripto - Agente de Percepción'},
                {'id': 12, 'nombre': 'Pequeño Contribuyente Eventual'},
                {'id': 13, 'nombre': 'Monotributo Social'},
                {'id': 14, 'nombre': 'Pequeño Contribuyente Eventual Social'},
            ]
            
            # Coeficientes CM05
            cursor.execute("""
                SELECT erp_terceros_cm05.*, sys_provincias.nombre as provincia_nombre
                FROM erp_terceros_cm05
                LEFT JOIN sys_provincias ON BINARY erp_terceros_cm05.jurisdiccion_code = BINARY LPAD(sys_provincias.id, 3, '0')
                WHERE erp_terceros_cm05.tercero_id = %s AND erp_terceros_cm05.enterprise_id = %s
                ORDER BY erp_terceros_cm05.periodo_anio DESC, erp_terceros_cm05.jurisdiccion_code ASC
            """, (id, request.user_data['enterprise_id']))
            coeficientes_cm = dictfetchall(cursor)
            
            for c in coeficientes_cm:
                if not c.get('provincia_nombre'):
                    c['provincia_nombre'] = f"Jurisdicción {c['jurisdiccion_code']}"

            # Cuenta Corriente
            cursor.execute("""
                SELECT
                    erp_comprobantes.fecha_emision                      AS fecha,
                    erp_comprobantes.tipo_comprobante                  AS tipo_doc,
                    CONCAT(
                        LPAD(erp_comprobantes.punto_venta, 4, '0'), '-',
                        LPAD(erp_comprobantes.numero,      8, '0')
                    )                                           AS nro_documento,
                    NULL                                        AS nro_recibo,
                    NULL                                        AS nro_doc_aplicado,
                    erp_comprobantes.importe_total                     AS importe_bruto,
                    erp_comprobantes.tipo_comprobante                  AS _signo_tipo,
                    erp_comprobantes.id                                AS comprobante_id,
                    erp_comprobantes.asiento_id                        AS asiento_id,
                    COALESCE((
                        SELECT SUM(erp_comprobantes_impuestos.importe)
                        FROM erp_comprobantes_impuestos
                        WHERE erp_comprobantes_impuestos.comprobante_id = erp_comprobantes.id
                          AND erp_comprobantes_impuestos.enterprise_id  = erp_comprobantes.enterprise_id
                    ), 0)                                       AS total_percepciones,
                    0                                           AS total_retenciones
                FROM erp_comprobantes
                WHERE erp_comprobantes.tercero_id = %s
                  AND erp_comprobantes.enterprise_id = %s
                  AND erp_comprobantes.modulo IN ('VEN', 'VENTAS')
            """, (id, request.user_data['enterprise_id']))
            rows_comp = dictfetchall(cursor)

            cursor.execute("""
                SELECT
                    fin_recibos.fecha                                     AS fecha,
                    'REC'                                       AS tipo_doc,
                    NULL                                        AS nro_documento,
                    CONCAT(
                        LPAD(fin_recibos.punto_venta, 4, '0'), '-',
                        LPAD(fin_recibos.numero,      8, '0')
                    )                                           AS nro_recibo,
                    GROUP_CONCAT(
                        DISTINCT CONCAT(
                            LPAD(erp_comprobantes.punto_venta, 4, '0'), '-',
                            LPAD(erp_comprobantes.numero,      8, '0')
                        )
                        ORDER BY erp_comprobantes.numero
                        SEPARATOR ' / '
                    )                                           AS nro_doc_aplicado,
                    SUM(fin_recibos_detalles.importe)                             AS importe_bruto,
                    'REC'                                       AS _signo_tipo,
                    NULL                                        AS comprobante_id,
                    fin_recibos.asiento_id                                AS asiento_id,
                    0                                           AS total_percepciones,
                    COALESCE((
                        SELECT SUM(fin_retenciones_emitidas.importe_retencion)
                        FROM fin_retenciones_emitidas
                        WHERE fin_retenciones_emitidas.comprobante_pago_id = fin_recibos.id
                          AND fin_retenciones_emitidas.enterprise_id = fin_recibos.enterprise_id
                    ), 0)                                       AS total_retenciones
                FROM fin_recibos
                JOIN fin_recibos_detalles ON fin_recibos_detalles.recibo_id = fin_recibos.id
                JOIN erp_comprobantes ON erp_comprobantes.id = fin_recibos_detalles.factura_id
                WHERE fin_recibos.tercero_id = %s
                  AND fin_recibos.enterprise_id = %s
                GROUP BY fin_recibos.id, fin_recibos.fecha, fin_recibos.punto_venta, fin_recibos.numero, fin_recibos.asiento_id
            """, (id, request.user_data['enterprise_id']))
            rows_rec = dictfetchall(cursor)

            DEBITO_TIPOS = {'001','002','006','007','011','012','005','010','015'}
            NC_TIPOS     = {'003','008','013'}

            cuenta_corriente = []
            saldo = 0.0
            all_rows = sorted(rows_comp + rows_rec, key=lambda r: (str(r['fecha']) if r['fecha'] else '1900-01-01'))
            
            for row in all_rows:
                tipo = row['_signo_tipo']
                importe = float(row['importe_bruto'] or 0)

                if tipo in DEBITO_TIPOS:
                    debe    = importe
                    haber   = 0.0
                    saldo  += importe
                elif tipo in NC_TIPOS:
                    debe    = 0.0
                    haber   = importe
                    saldo  -= importe
                else:  # REC — cobro
                    debe    = 0.0
                    haber   = importe
                    saldo  -= importe

                cuenta_corriente.append({
                    'fecha':              row['fecha'],
                    'tipo_doc':           row['tipo_doc'],
                    'nro_documento':      row['nro_documento'],
                    'nro_recibo':         row['nro_recibo'],
                    'nro_doc_aplicado':   row['nro_doc_aplicado'],
                    'debe':               debe,
                    'haber':              haber,
                    'saldo':              saldo,
                    'comprobante_id':     row['comprobante_id'],
                    'asiento_id':         row['asiento_id'],
                    'total_percepciones': float(row['total_percepciones'] or 0),
                    'total_retenciones':  float(row['total_retenciones'] or 0),
                })

            cursor.execute("""
                SELECT erp_terceros_cta_cte_track.*,
                       sys_users.username AS user_nombre
                FROM erp_terceros_cta_cte_track
                LEFT JOIN sys_users ON sys_users.id = erp_terceros_cta_cte_track.user_id
                WHERE erp_terceros_cta_cte_track.tercero_id = %s
                  AND erp_terceros_cta_cte_track.enterprise_id = %s
                ORDER BY erp_terceros_cta_cte_track.fecha_vigencia DESC
                LIMIT 20
            """, (id, request.user_data['enterprise_id']))
            cta_cte_track = dictfetchall(cursor)

        return render(request, 'ventas/perfil_cliente.html', {
            'cliente': cliente,
            'direcciones': direcciones,
            'contactos': contactos,
            'fiscales': fiscales,
            'pago_info': pago_info,
            'condiciones': condiciones_disponibles,
            'condiciones_pago': condiciones_disponibles,
            'condiciones_fiscales': condiciones_fiscales,
            'mixtas': mixtas_disponibles,
            'habilitadas': habilitaciones,
            'incluidas_en_maestra': incluidas_en_maestra,
            'provincias': provincias,
            'impuestos_lista': impuestos_lista,
            'cuenta_corriente': cuenta_corriente,
            'coeficientes_cm': coeficientes_cm,
            'cta_cte_track': cta_cte_track
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        from django.contrib import messages
        messages.error(request, f"Error al cargar perfil de cliente: {str(e)}")
        return redirect('ventas:clientes')

@login_required
def facturar(request):
    from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
    import datetime
    import json
    from django.shortcuts import render
    from django.http import HttpResponse
    from django.contrib import messages
    
    enterprise_id = request.user_data['enterprise_id']
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Clientes
            cursor.execute("SELECT id, nombre, cuit, tipo_responsable FROM erp_terceros WHERE (enterprise_id = 0 OR enterprise_id = %s) AND es_cliente = 1 AND activo = 1 ORDER BY nombre", (enterprise_id,))
            clientes = dictfetchall(cursor)
            
            # Tipos de Comprobante
            cursor.execute("SELECT codigo, descripcion, letra FROM sys_tipos_comprobante WHERE activo = 1 ORDER BY codigo")
            tipos = dictfetchall(cursor)
            
            # Depósitos
            cursor.execute("SELECT id, nombre FROM stk_depositos WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            depositos = dictfetchall(cursor)
            
            # Medios de Pago
            cursor.execute("SELECT id, nombre, recargo_pct FROM fin_medios_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            medios_pago = dictfetchall(cursor)
            
            # Condiciones de Pago
            cursor.execute("SELECT id, nombre, dias_vencimiento, descuento_pct FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            condiciones = dictfetchall(cursor)
            
            # Naturalezas (Rubros)
            cursor.execute("SELECT DISTINCT naturaleza FROM stk_articulos WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 AND naturaleza IS NOT NULL", (enterprise_id,))
            naturalezas = [r['naturaleza'] for r in dictfetchall(cursor)]
            
            # Condición IVA Empresa
            cursor.execute("SELECT condicion_iva FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            empresa = dictfetchone(cursor)
            condicion_iva_empresa = empresa['condicion_iva'] if empresa else 'Responsable Inscripto'
            
            # Jurisdicciones (Percepciones)
            cursor.execute("""
                SELECT jurisdiccion FROM sys_enterprises_fiscal 
                WHERE enterprise_id = %s AND activo = 1 AND tipo IN ('PERCEPCION', 'AMBOS')
            """, (enterprise_id,))
            agente_percepciones = [j['jurisdiccion'].upper() for j in dictfetchall(cursor)]
            
            # Transportistas
            cursor.execute("SELECT id, nombre, cuit FROM stk_logisticas WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            transportistas = dictfetchall(cursor)

        context = {
            'clientes': clientes,
            'tipos_comprobante': tipos,
            'depositos': depositos,
            'medios_pago': medios_pago,
            'condiciones': condiciones,
            'naturalezas': naturalezas,
            'condicion_iva_empresa': condicion_iva_empresa,
            'agente_percepciones': agente_percepciones,
            'agente_percepciones_json': json.dumps(agente_percepciones),
            'transportistas': transportistas,
            'now': datetime.date.today().isoformat(),
            'es_nota_credito': False
        }
        return render(request, 'ventas/facturar.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f"Error: {str(e)}", status=500)
        messages.error(request, f"Error al cargar perfil de cliente: {str(e)}")
        return redirect('ventas:clientes')

@login_required
def editar_cliente(request, id):
    if request.method == 'POST':
        enterprise_id = request.user_data['enterprise_id']
        codigo = request.POST.get('codigo')
        nombre = request.POST.get('nombre')
        cuit = request.POST.get('cuit')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        tipo_responsable = request.POST.get('tipo_responsable')
        condicion_pago_id = request.POST.get('condicion_pago_id') or None
        condicion_mixta_id = request.POST.get('condicion_mixta_id') or None
        observaciones = request.POST.get('observaciones')

        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE erp_terceros 
                    SET codigo=%s, nombre=%s, cuit=%s, email=%s, telefono=%s, tipo_responsable=%s, 
                        condicion_pago_id=%s, condicion_mixta_id=%s, observaciones=%s
                    WHERE id=%s AND enterprise_id=%s
                """, (codigo, nombre, cuit, email, telefono, tipo_responsable, condicion_pago_id, condicion_mixta_id, observaciones, id, enterprise_id))
            from django.contrib import messages
            messages.success(request, "Datos del cliente actualizados correctamente.")
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f"Error al actualizar cliente: {str(e)}")
            
        return redirect('ventas:perfil_cliente', id=id)

@login_required
def eliminar_detalle(request, tabla, item_id, cliente_id):
    tablas_permitidas = ['erp_direcciones', 'erp_contactos', 'erp_datos_fiscales', 'erp_terceros_cm05']
    if tabla not in tablas_permitidas:
        from django.contrib import messages
        messages.error(request, "Operación no permitida.")
        return redirect('ventas:perfil_cliente', id=cliente_id)

    enterprise_id = request.user_data['enterprise_id']
    from django.contrib import messages

    try:
        if tabla == 'erp_terceros_cm05':
            from .services import CM05Service
            CM05Service.delete_coeficiente(enterprise_id, item_id, request.user_data['id'])
        else:
            with get_db_cursor() as cursor:
                cursor.execute(f"DELETE FROM {tabla} WHERE id = %s AND tercero_id = %s AND enterprise_id = %s", (item_id, cliente_id, enterprise_id))
        messages.info(request, "Registro eliminado.")
    except Exception as e:
        messages.error(request, f"Error al eliminar registro: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=cliente_id)

@login_required
def solicitar_cta_cte(request, id):
    habilita = 1 if request.POST.get('habilita_cta_cte') else 0
    monto_raw = request.POST.get('monto_cta_cte', '0') or '0'
    motivo = request.POST.get('motivo', '')
    enterprise_id = request.user_data['enterprise_id']
    user_id = request.user_data['id']
    
    try:
        monto = float(monto_raw)
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE erp_terceros
                SET cta_cte_pendiente_habilita  = %s,
                    cta_cte_pendiente_monto     = %s,
                    estado_cta_cte_aprobacion   = 'PENDIENTE',
                    cta_cte_pendiente_user_id   = %s
                WHERE id = %s AND enterprise_id = %s
            """, (habilita, monto, user_id, id, enterprise_id))

            cursor.execute("""
                INSERT INTO erp_terceros_cta_cte_track
                    (enterprise_id, tercero_id, habilita_cta_cte, monto_cta_cte,
                     estado, motivo, user_id, fecha_vigencia)
                VALUES (%s, %s, %s, %s, 'PENDIENTE', %s, %s, NOW())
            """, (enterprise_id, id, habilita, monto, motivo, user_id))
        
        from django.contrib import messages
        messages.info(request, "Solicitud de Cuenta Corriente enviada a Tesorería para aprobación.")
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Solicitud fallida: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def aprobar_cta_cte(request, id):
    permissions = request.user_data.get('permissions', [])
    is_tesoreria = ('tesoreria' in permissions or 'admin' in permissions or 'all' in permissions)
    
    if not is_tesoreria:
        from django.contrib import messages
        messages.error(request, "No tiene permisos para aprobar cambios de Cuenta Corriente.")
        return redirect('ventas:perfil_cliente', id=id)

    action = request.POST.get('action') # 'approve' or 'reject'
    enterprise_id = request.user_data['enterprise_id']
    user_id = request.user_data['id']

    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT cta_cte_pendiente_habilita, cta_cte_pendiente_monto
                FROM erp_terceros
                WHERE id = %s AND enterprise_id = %s
            """, (id, enterprise_id))
            row = dictfetchone(cursor)

            if not row:
                from django.contrib import messages
                messages.warning(request, "Cliente no encontrado.")
                return redirect('ventas:perfil_cliente', id=id)

            nuevo_habilita = row['cta_cte_pendiente_habilita']
            nuevo_monto    = row['cta_cte_pendiente_monto']

            if action == 'approve':
                cursor.execute("""
                    UPDATE erp_terceros
                    SET habilita_cta_cte             = %s,
                        monto_cta_cte                = %s,
                        estado_cta_cte_aprobacion    = 'APROBADO',
                        cta_cte_aprobador_id         = %s,
                        cta_cte_fecha_aprobacion     = NOW(),
                        cta_cte_pendiente_habilita   = NULL,
                        cta_cte_pendiente_monto      = NULL,
                        cta_cte_pendiente_user_id    = NULL
                    WHERE id = %s AND enterprise_id = %s
                """, (nuevo_habilita, nuevo_monto, user_id, id, enterprise_id))

                cursor.execute("""
                    UPDATE erp_terceros_cta_cte_track
                    SET estado = 'APROBADO', aprobador_id = %s, fecha_aprobacion = NOW()
                    WHERE tercero_id = %s AND enterprise_id = %s
                      AND estado = 'PENDIENTE'
                    ORDER BY fecha_vigencia DESC LIMIT 1
                """, (user_id, id, enterprise_id))
                from django.contrib import messages
                messages.success(request, "Cuenta Corriente aprobada.")
            else:
                cursor.execute("""
                    UPDATE erp_terceros
                    SET estado_cta_cte_aprobacion  = 'RECHAZADO',
                        cta_cte_pendiente_habilita  = NULL,
                        cta_cte_pendiente_monto     = NULL,
                        cta_cte_pendiente_user_id   = NULL
                    WHERE id = %s AND enterprise_id = %s
                """, (id, enterprise_id))
                cursor.execute("""
                    UPDATE erp_terceros_cta_cte_track
                    SET estado = 'RECHAZADO', aprobador_id = %s, fecha_aprobacion = NOW()
                    WHERE tercero_id = %s AND enterprise_id = %s
                      AND estado = 'PENDIENTE'
                    ORDER BY fecha_vigencia DESC LIMIT 1
                """, (user_id, id, enterprise_id))
                from django.contrib import messages
                messages.warning(request, "Solicitud de Cuenta Corriente rechazada.")
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Aprobación fallida: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def toggle_convenio(request, id):
    es_convenio = 1 if 'es_convenio' in request.POST else 0
    with get_db_cursor() as cursor:
        cursor.execute("UPDATE erp_terceros SET es_convenio_multilateral = %s WHERE id = %s AND enterprise_id = %s", (es_convenio, id, request.user_data['enterprise_id']))
    from django.contrib import messages
    messages.success(request, "Configuración de convenio multilateral actualizada.")
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def agregar_cm05(request, id):
    jurisdiccion = request.POST.get('jurisdiccion_code')
    periodo_anio = request.POST.get('periodo_anio')
    coeficiente = request.POST.get('coeficiente')

    try:
        from .services import CM05Service
        CM05Service.upsert_coeficiente(request.user_data['enterprise_id'], id, jurisdiccion, periodo_anio, coeficiente, request.user_data['id'])
        from django.contrib import messages
        messages.success(request, "Coeficiente guardado correctamente.")
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Error al guardar coeficiente: {e}")
    
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def upload_cm05(request, id):
    if 'archivo_cm05' not in request.FILES:
        from django.contrib import messages
        messages.warning(request, 'No se seleccionó ningún archivo.')
        return redirect('ventas:perfil_cliente', id=id)
        
    file = request.FILES['archivo_cm05']
    if file.name == '':
        from django.contrib import messages
        messages.warning(request, 'No se seleccionó ningún archivo.')
        return redirect('ventas:perfil_cliente', id=id)
        
    if file.name.lower().endswith('.pdf'):
        import os
        from django.conf import settings
        
        ext = os.path.splitext(file.name)[1]
        filename = f"CM05_{request.user_data['enterprise_id']}_{id}{ext}"
        upload_folder = os.path.join(settings.BASE_DIR, 'static', 'uploads', 'cm05')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        rel_path = f"uploads/cm05/{filename}"
        
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE erp_terceros SET archivo_cm05_path = %s WHERE id = %s", (rel_path, id))
        
        from django.contrib import messages
        messages.success(request, "Archivo subido correctamente.")
    else:
        from django.contrib import messages
        messages.error(request, "Formato de archivo inválido. Solo PDF.")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def agregar_direccion(request, id):
    item_id = request.POST.get('item_id') # Si viene, es edición
    etiqueta = request.POST.get('etiqueta')
    calle = request.POST.get('calle')
    numero = request.POST.get('numero')
    piso = request.POST.get('piso', '')
    depto = request.POST.get('depto', '')
    localidad = request.POST.get('localidad')
    provincia = request.POST.get('provincia')
    cp = request.POST.get('cod_postal')
    es_fiscal = 1 if 'es_fiscal' in request.POST else 0
    es_entrega = 1 if 'es_entrega' in request.POST else 0
    enterprise_id = request.user_data['enterprise_id']
    
    from django.contrib import messages
    try:
        with get_db_cursor() as cursor:
            if item_id:
                cursor.execute("""
                    UPDATE erp_direcciones 
                    SET etiqueta=%s, calle=%s, numero=%s, piso=%s, depto=%s, localidad=%s, provincia=%s, cod_postal=%s, es_fiscal=%s, es_entrega=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (etiqueta, calle, numero, piso, depto, localidad, provincia, cp, es_fiscal, es_entrega, item_id, id, enterprise_id))
                messages.success(request, "Dirección actualizada.")
            else:
                cursor.execute("""
                    INSERT INTO erp_direcciones (enterprise_id, tercero_id, etiqueta, calle, numero, piso, depto, localidad, provincia, cod_postal, es_fiscal, es_entrega)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (enterprise_id, id, etiqueta, calle, numero, piso, depto, localidad, provincia, cp, es_fiscal, es_entrega))
                messages.success(request, "Dirección agregada.")
    except Exception as e:
        messages.error(request, f"Error al guardar dirección: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def agregar_contacto(request, id):
    item_id = request.POST.get('item_id')
    nombre = request.POST.get('nombre')
    puesto = request.POST.get('puesto')
    tipo = request.POST.get('tipo_contacto')
    telefono = request.POST.get('telefono')
    email = request.POST.get('email')
    es_receptor = 1 if 'es_receptor' in request.POST else 0
    direccion_id = request.POST.get('direccion_id') or None
    enterprise_id = request.user_data['enterprise_id']

    from django.contrib import messages
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Resolver puesto a ID si existe
            cursor.execute("SELECT id FROM erp_puestos WHERE nombre = %s AND enterprise_id = %s LIMIT 1", (puesto, enterprise_id))
            puesto_row = dictfetchone(cursor)
            puesto_id = puesto_row['id'] if puesto_row else None

            if item_id:
                cursor.execute("""
                    UPDATE erp_contactos SET nombre=%s, puesto_id=%s, tipo_contacto=%s, telefono=%s, email=%s, es_receptor=%s, direccion_id=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (nombre, puesto_id, tipo, telefono, email, es_receptor, direccion_id, item_id, id, enterprise_id))
                messages.success(request, "Contacto actualizado.")
            else:
                cursor.execute("""
                    INSERT INTO erp_contactos (enterprise_id, tercero_id, nombre, puesto_id, tipo_contacto, telefono, email, es_receptor, direccion_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (enterprise_id, id, nombre, puesto_id, tipo, telefono, email, es_receptor, direccion_id))
                messages.success(request, "Contacto agregado.")
    except Exception as e:
        messages.error(request, f"Error al guardar contacto: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def agregar_fiscal(request, id):
    item_id = request.POST.get('item_id')
    impuesto = request.POST.get('impuesto')
    jurisdiccion = request.POST.get('jurisdiccion')
    condicion = request.POST.get('condicion')
    alicuota_raw = request.POST.get('alicuota', 0)
    inscripcion = request.POST.get('numero_inscripcion', '')
    enterprise_id = request.user_data['enterprise_id']
    
    try: alicuota = float(alicuota_raw)
    except: alicuota = 0

    from django.contrib import messages
    try:
        with get_db_cursor() as cursor:
            if item_id:
                cursor.execute("""
                    UPDATE erp_datos_fiscales SET impuesto=%s, jurisdiccion=%s, condicion=%s, numero_inscripcion=%s, alicuota=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (impuesto, jurisdiccion, condicion, inscripcion, alicuota, item_id, id, enterprise_id))
                messages.success(request, "Dato fiscal actualizado.")
            else:
                cursor.execute("""
                    INSERT INTO erp_datos_fiscales (enterprise_id, tercero_id, impuesto, jurisdiccion, condicion, numero_inscripcion, alicuota)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (enterprise_id, id, impuesto, jurisdiccion, condicion, inscripcion, alicuota))
                messages.success(request, "Dato fiscal agregado.")
    except Exception as e:
        messages.error(request, f"Error al guardar dato fiscal: {str(e)}")
        
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def solicitar_condicion_pago(request, id):
    condicion_id = request.POST.get('condicion_id')
    enterprise_id = request.user_data['enterprise_id']
    from django.contrib import messages
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE erp_terceros 
                SET condicion_pago_pendiente_id = %s, estado_aprobacion_pago = 'PENDIENTE'
                WHERE id = %s AND enterprise_id = %s
            """, (condicion_id, id, enterprise_id))
        messages.info(request, "Solicitud de cambio de condición de pago enviada.")
    except Exception as e:
        messages.error(request, f"Error al solicitar cambio: {str(e)}")
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def aprobar_condicion_pago(request, id):
    permissions = request.user_data.get('permissions', [])
    is_gerente = ('gerente_ventas' in permissions or 'admin' in permissions or 'all' in permissions)
    if not is_gerente:
        from django.contrib import messages
        messages.error(request, "No tiene permisos para aprobar cambios de condición de pago.")
        return redirect('ventas:perfil_cliente', id=id)
        
    action = request.POST.get('action')
    enterprise_id = request.user_data['enterprise_id']
    user_id = request.user_data['id']
    
    from django.contrib import messages
    try:
        with get_db_cursor(dictionary=True) as cursor:
            if action == 'approve':
                cursor.execute("SELECT condicion_pago_pendiente_id FROM erp_terceros WHERE id = %s", (id,))
                row = dictfetchone(cursor)
                if row and row['condicion_pago_pendiente_id']:
                    cursor.execute("""
                        UPDATE erp_terceros 
                        SET condicion_pago_id = %s, condicion_pago_pendiente_id = NULL, 
                            estado_aprobacion_pago = 'APROBADO', id_gerente_aprobador = %s, 
                            fecha_aprobacion_pago = NOW()
                        WHERE id = %s
                    """, (row['condicion_pago_pendiente_id'], user_id, id))
                    messages.success(request, "Cambio de condición de pago aprobado.")
            else:
                cursor.execute("""
                    UPDATE erp_terceros 
                    SET condicion_pago_pendiente_id = NULL, estado_aprobacion_pago = 'RECHAZADO'
                    WHERE id = %s
                """, (id,))
                messages.warning(request, "Cambio de condición de pago rechazado.")
    except Exception as e:
        messages.error(request, f"Error en aprobación: {str(e)}")
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def habilitar_condiciones_pago(request, id):
    enterprise_id = request.user_data['enterprise_id']
    from django.contrib import messages
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Obtener todas las condiciones para iterar igual que en el POST
            cursor.execute("SELECT id FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s)", (enterprise_id,))
            condiciones = cursor.fetchall()
            
            for cond in condiciones:
                key = f"habilitado_{cond['id']}"
                if key in request.POST:
                    habilita = int(request.POST[key])
                    # Upsert
                    cursor.execute("""
                        INSERT INTO erp_terceros_condiciones (enterprise_id, tercero_id, condicion_pago_id, habilitado, fecha_habilitacion)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE habilitado = VALUES(habilitado), fecha_habilitacion = NOW()
                    """, (enterprise_id, id, cond['id'], habilita))
            messages.success(request, "Habilitaciones comerciales actualizadas.")
    except Exception as e:
        messages.error(request, f"Error al actualizar habilitaciones: {str(e)}")
    return redirect('ventas:perfil_cliente', id=id)

@login_required
def comprobantes(request):
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT erp_comprobantes.*, erp_terceros.nombre as cliente_nombre, 
                       sys_tipos_comprobante.letra, sys_tipos_comprobante.descripcion as tipo_nombre,
                       (SELECT COUNT(*) FROM stk_devoluciones_solicitudes  
                        WHERE stk_devoluciones_solicitudes.comprobante_origen_id = erp_comprobantes.id 
                        AND stk_devoluciones_solicitudes.estado != 'ANULADO'
                        AND stk_devoluciones_solicitudes.enterprise_id = erp_comprobantes.enterprise_id) as nc_solicitada,
                       (SELECT COUNT(*) FROM erp_comprobantes AS nc_em 
                        WHERE nc_em.referencia_comercial = CONCAT(LPAD(erp_comprobantes.punto_venta, 4, '0'), '-', LPAD(erp_comprobantes.numero, 8, '0'))
                        AND nc_em.tipo_comprobante IN ('003', '008', '013')
                        AND nc_em.enterprise_id = erp_comprobantes.enterprise_id) as nc_emitida
                FROM erp_comprobantes
                JOIN erp_terceros ON erp_comprobantes.tercero_id = erp_terceros.id
                JOIN sys_tipos_comprobante ON erp_comprobantes.tipo_comprobante = sys_tipos_comprobante.codigo
                WHERE erp_comprobantes.enterprise_id = %s 
                  AND erp_comprobantes.modulo IN ('VEN', 'VENTAS', 'VENTA')
                ORDER BY erp_comprobantes.fecha_emision DESC, erp_comprobantes.numero DESC
            """, (request.user_data['enterprise_id'],))
            lista = dictfetchall(cursor)
        return render(request, 'ventas/comprobantes.html', {'comprobantes': lista})
    except Exception as e:
        import traceback
        traceback.print_exc()
        from django.contrib import messages
        messages.error(request, f"Error al cargar listado de comprobantes: {str(e)}")
        return redirect('ventas:dashboard')

@login_required
def ver_comprobante(request, id):
    from apps.ventas.billing_service import BillingService
    from django.contrib import messages
    
    enterprise_id = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # 1. Cabecera + Cliente + Tipo
            cursor.execute("""
                SELECT c.*, t.nombre as cliente_nombre, t.cuit as cliente_cuit, t.tipo_responsable as cliente_condicion, t.email as cliente_email,
                       tc.descripcion as tipo_nombre, tc.letra,
                       d.etiqueta as entrega_etiqueta, d.calle as entrega_calle, d.numero as entrega_numero, 
                       d.localidad as entrega_localidad, d.provincia as entrega_provincia,
                       con.nombre as receptor_nombre,
                       casoc.punto_venta as asoc_punto_venta, casoc.numero as asoc_numero
                FROM erp_comprobantes c
                LEFT JOIN erp_terceros t ON c.tercero_id = t.id
                LEFT JOIN sys_tipos_comprobante tc ON c.tipo_comprobante = tc.codigo
                LEFT JOIN erp_direcciones d ON c.direccion_entrega_id = d.id
                LEFT JOIN erp_contactos con ON c.receptor_contacto_id = con.id
                LEFT JOIN erp_comprobantes casoc ON c.comprobante_asociado_id = casoc.id
                WHERE c.id = %s AND c.enterprise_id = %s
            """, (id, enterprise_id))
            comprobante = dictfetchone(cursor)
            
            if not comprobante:
                messages.error(request, "Comprobante no encontrado.")
                return redirect('ventas:comprobantes')
                
            # 2. Detalles (Pre-procesados para Django Template)
            cursor.execute("""
                SELECT * FROM erp_comprobantes_detalle WHERE comprobante_id = %s AND enterprise_id = %s
            """, (id, enterprise_id))
            detalles_raw = dictfetchall(cursor)
            detalles = []
            current_y = 296
            for d in detalles_raw:
                desc = d.get('descripcion', '')
                # Split description into lines of 45 chars
                words = desc.split()
                lines = []
                current_line = ""
                for w in words:
                    if len(current_line) + len(w) + 1 <= 45:
                        current_line += (w + " ")
                    else:
                        lines.append(current_line.strip())
                        current_line = w + " "
                if current_line:
                    lines.append(current_line.strip())
                
                if not lines: lines = [""]
                
                # First line has all data
                detalles.append({
                    'articulo_id': d.get('articulo_id'),
                    'desc_line': lines[0],
                    'cantidad': d.get('cantidad'),
                    'precio_unitario': d.get('precio_unitario'),
                    'subtotal_total': d.get('subtotal_total'),
                    'y': current_y
                })
                current_y += 14
                
                # Extra lines only have description
                for extra in lines[1:]:
                    detalles.append({
                        'desc_line': extra,
                        'y': current_y
                    })
                    current_y += 14

            # 3. Dirección del Cliente (Fiscal)
            cursor.execute("SELECT * FROM erp_direcciones WHERE tercero_id = %s AND enterprise_id = %s AND es_fiscal = 1 LIMIT 1", (comprobante['tercero_id'], enterprise_id))
            direccion = dictfetchone(cursor)

            # 3.5 Impuestos / Percepciones Dinámicas
            cursor.execute("SELECT * FROM erp_comprobantes_impuestos WHERE comprobante_id = %s AND enterprise_id = %s", (id, enterprise_id))
            impuestos_raw = dictfetchall(cursor)
            impuestos_final = []
            imp_y = 540
            for imp in impuestos_raw:
                imp_item = dict(imp)
                imp_item['y'] = imp_y
                impuestos_final.append(imp_item)
                imp_y += 12

            # 4. Datos de la Empresa (Emisor)
            cursor.execute("SELECT * FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            empresa = dictfetchone(cursor)

            # 5. Obtener Layout y Valores para el Comprobante
            layout = BillingService.get_layout(enterprise_id, cursor)
            vals = BillingService.prepare_invoice_values(comprobante, detalles, empresa, direccion, impuestos_final)

            # Enriquecer layout con valores para evitar .get en template
            for name, config in layout.items():
                config['value'] = vals.get(name, '')

            # 6. Impresora Predeterminada para impresión directa (QZ Tray)
            cursor.execute("""
                SELECT * FROM stk_impresoras_config 
                WHERE enterprise_id = %s AND es_predeterminada = 1 AND activo = 1 
                LIMIT 1
            """, (enterprise_id,))
            printer = dictfetchone(cursor)

            
            import json
            printer_json = json.dumps(printer, default=str) if printer else 'null'

            es_copia = request.GET.get('es_copia', '0') == '1'

            if es_copia:
                try:
                    cursor.execute("""
                        INSERT INTO fin_comprobantes_copias 
                        (enterprise_id, comprobante_id, user_id, fecha)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    """, (enterprise_id, id, request.user_data['id']))
                except Exception as e:
                    print(f"Error al registrar log de reimpresion: {e}")

        context = {
            'c': comprobante,
            'detalles': detalles,
            'cliente_dir': direccion,
            'impuestos': impuestos_final,
            'empresa': empresa,
            'layout': layout,
            'vals': vals,
            'printer': printer,
            'printer_json': printer_json,
            'es_copia': es_copia,
            'ejemplares': ['ORIGINAL', 'DUPLICADO', 'TRIPLICADO']
        }
        return render(request, 'ventas/comprobante_impresion.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al mostrar comprobante: {str(e)}")
        return redirect('ventas:comprobantes')


@login_required
def descargar_pdf_comprobante(request, id):
    """
    Genera y devuelve el comprobante como archivo PDF descargable.
    Reutiliza toda la lógica de datos de ver_comprobante.
    """
    from apps.ventas.billing_service import BillingService
    from apps.core.pdf_service import render_to_pdf

    enterprise_id = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # --- Misma lógica de carga de datos que ver_comprobante ---
            cursor.execute("""
                SELECT c.*, t.nombre as cliente_nombre, t.cuit as cliente_cuit,
                       t.tipo_responsable as cliente_condicion, t.email as cliente_email,
                       tc.nombre as tipo_comprobante_nombre, tc.letra as letra,
                       con.id as contacto_id,
                       casoc.punto_venta as casoc_pv, casoc.numero as casoc_num,
                       casoc.tipo_comprobante as casoc_tipo
                FROM erp_comprobantes c
                JOIN erp_terceros t ON c.tercero_id = t.id
                JOIN sys_tipos_comprobante tc ON c.tipo_comprobante = tc.codigo
                LEFT JOIN erp_contactos con ON c.receptor_contacto_id = con.id
                LEFT JOIN erp_comprobantes casoc ON c.comprobante_asociado_id = casoc.id
                WHERE c.id = %s AND c.enterprise_id = %s
            """, (id, enterprise_id))
            comprobante = dictfetchone(cursor)

            if not comprobante:
                messages.error(request, "Comprobante no encontrado.")
                return redirect('ventas:comprobantes')

            cursor.execute("""
                SELECT * FROM erp_comprobantes_detalle
                WHERE comprobante_id = %s AND enterprise_id = %s
            """, (id, enterprise_id))
            detalles_raw = dictfetchall(cursor)

            cursor.execute("""
                SELECT * FROM erp_empresas WHERE id = %s LIMIT 1
            """, (enterprise_id,))
            empresa = dictfetchone(cursor) or {}

            cursor.execute("""
                SELECT * FROM sys_tipos_comprobante_layout
                WHERE tipo_comprobante = %s AND enterprise_id IN (%s, 0)
                ORDER BY enterprise_id DESC LIMIT 1
            """, (comprobante['tipo_comprobante'], enterprise_id))
            layout_row = dictfetchone(cursor)

            import json
            layout = json.loads(layout_row['layout_json']) if layout_row and layout_row.get('layout_json') else {}

            billing = BillingService(enterprise_id)
            vals = billing.build_vals(comprobante, layout)

            # Dirección del receptor
            cursor.execute("""
                SELECT * FROM erp_terceros_direcciones
                WHERE tercero_id = %s AND principal = 1 LIMIT 1
            """, (comprobante['tercero_id'],))
            direccion = dictfetchone(cursor) or {}

            # Impuestos / Percepciones
            cursor.execute("""
                SELECT * FROM erp_comprobantes_percepciones
                WHERE comprobante_id = %s
            """, (id,))
            percepciones = dictfetchall(cursor)
            impuestos = [dict(p, y=0) for p in percepciones]

        # Simplificar detalles para el template PDF (sin coordenadas Y)
        detalles = []
        for d in detalles_raw:
            detalles.append({
                'articulo_id': d.get('articulo_id'),
                'desc_line': d.get('descripcion', ''),
                'cantidad': d.get('cantidad'),
                'precio_unitario': d.get('precio_unitario'),
                'subtotal_total': d.get('subtotal_total') or d.get('subtotal'),
            })

        # Filas de relleno para mantener tamaño de tabla (mínimo 12 líneas)
        min_rows = 12
        filler_count = max(0, min_rows - len(detalles))

        letra = comprobante.get('letra', vals.get('letra', 'B'))
        tipo_nombre = comprobante.get('tipo_comprobante_nombre', 'Comprobante')
        punto_venta = comprobante.get('punto_venta', '')
        numero = comprobante.get('numero', '')

        filename = f"{tipo_nombre}_{letra}_{str(punto_venta).zfill(5)}-{str(numero).zfill(8)}.pdf"

        context = {
            'c': comprobante,
            'detalles': detalles,
            'cliente_dir': direccion,
            'impuestos': impuestos,
            'empresa': empresa,
            'layout': layout,
            'vals': vals,
            'es_copia': False,
            'ejemplares': ['ORIGINAL'],
            'filler_rows': range(filler_count),
        }

        return render_to_pdf('ventas/comprobante_pdf.html', context, filename)

    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al generar PDF: {str(e)}")
        return redirect('ventas:comprobantes')

@login_required
def ver_remito(request, id):
    from apps.ventas.billing_service import BillingService
    from django.contrib import messages
    
    enterprise_id = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT c.*, t.nombre as cliente_nombre, t.cuit as cliente_cuit, t.tipo_responsable as cliente_condicion,
                       tc.descripcion as tipo_nombre, tc.letra,
                       d.etiqueta as entrega_etiqueta, d.calle as entrega_calle, d.numero as entrega_numero, 
                       d.localidad as entrega_localidad, d.provincia as entrega_provincia,
                       con.nombre as receptor_nombre
                FROM erp_comprobantes c
                LEFT JOIN erp_terceros t ON c.tercero_id = t.id
                LEFT JOIN sys_tipos_comprobante tc ON c.tipo_comprobante = tc.codigo
                LEFT JOIN erp_direcciones d ON c.direccion_entrega_id = d.id
                LEFT JOIN erp_contactos con ON c.receptor_contacto_id = con.id
                WHERE c.id = %s AND c.enterprise_id = %s
            """, (id, enterprise_id))
            comprobante = dictfetchone(cursor)
            if not comprobante:
                messages.error(request, "Comprobante no encontrado.")
                return redirect('ventas:comprobantes')
            
            # Clonamos y forzamos tipo remito
            c_remito = dict(comprobante)
            if not comprobante['tipo_comprobante'] in ['091', '099']:
                c_remito['tipo_comprobante'] = 'REMITO' 

            # Detalles (Pre-procesados para Django Template)
            cursor.execute("SELECT * FROM erp_comprobantes_detalle WHERE comprobante_id = %s AND enterprise_id = %s", (id, enterprise_id))
            detalles_raw = dictfetchall(cursor)
            detalles = []
            current_y = 296
            for d in detalles_raw:
                desc = d.get('descripcion', '')
                words = desc.split()
                lines = []
                current_line = ""
                for w in words:
                    if len(current_line) + len(w) + 1 <= 45:
                        current_line += (w + " ")
                    else:
                        lines.append(current_line.strip())
                        current_line = w + " "
                if current_line:
                    lines.append(current_line.strip())
                if not lines: lines = [""]
                
                detalles.append({
                    'articulo_id': d.get('articulo_id'),
                    'desc_line': lines[0],
                    'cantidad': d.get('cantidad'),
                    'precio_unitario': d.get('precio_unitario'),
                    'subtotal_total': d.get('subtotal_total'),
                    'y': current_y
                })
                current_y += 14
                for extra in lines[1:]:
                    detalles.append({'desc_line': extra, 'y': current_y})
                    current_y += 14
            
            cursor.execute("SELECT * FROM erp_direcciones WHERE tercero_id = %s AND enterprise_id = %s AND es_fiscal = 1 LIMIT 1", (comprobante['tercero_id'], enterprise_id))
            direccion = dictfetchone(cursor)

            cursor.execute("SELECT * FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            empresa = dictfetchone(cursor)

            # Impuestos (Pre-procesado)
            cursor.execute("SELECT * FROM erp_comprobantes_impuestos WHERE comprobante_id = %s AND enterprise_id = %s", (id, enterprise_id))
            impuestos_raw = dictfetchall(cursor)
            impuestos_final = []
            imp_y = 540
            for imp in impuestos_raw:
                imp_item = dict(imp)
                imp_item['y'] = imp_y
                impuestos_final.append(imp_item)
                imp_y += 12

            layout = BillingService.get_layout(enterprise_id, cursor)
            vals = BillingService.prepare_invoice_values(c_remito, detalles, empresa, direccion, impuestos_final)

            for name, config in layout.items():
                config['value'] = vals.get(name, '')

            cursor.execute("""
                SELECT * FROM stk_impresoras_config 
                WHERE enterprise_id = %s AND es_predeterminada = 1 AND activo = 1 
                LIMIT 1
            """, (enterprise_id,))
            printer = dictfetchone(cursor)

            import json
            printer_json = json.dumps(printer, default=str) if printer else 'null'

        context = {
            'c': c_remito,
            'detalles': detalles,
            'cliente_dir': direccion,
            'impuestos': impuestos_final,
            'empresa': empresa,
            'layout': layout,
            'vals': vals,
            'printer': printer,
            'printer_json': printer_json,
            'ejemplares': ['ORIGINAL', 'DUPLICADO', 'TRIPLICADO']
        }
        return render(request, 'ventas/comprobante_impresion.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al mostrar remito: {str(e)}")
        return redirect('ventas:comprobantes')

@login_required
def facturar(request):
    from apps.ventas.billing_service import BillingService
    import datetime
    enterprise_id = request.user_data['enterprise_id']
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Clientes
            cursor.execute("SELECT id, nombre, cuit, tipo_responsable FROM erp_terceros WHERE enterprise_id = %s AND es_cliente = 1 AND activo = 1", (enterprise_id,))
            clientes = dictfetchall(cursor)

            # Condición IVA Empresa
            cursor.execute("SELECT condicion_iva FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            empresa = dictfetchone(cursor)
            condicion_iva_empresa = empresa['condicion_iva'] if empresa else 'Responsable Inscripto'
            
            # Naturalezas
            try:
                cursor.execute("""
                    SELECT DISTINCT stk_tipos_articulo.naturaleza 
                    FROM stk_tipos_articulo
                    WHERE (stk_tipos_articulo.enterprise_id = 0 OR stk_tipos_articulo.enterprise_id = %s) 
                    AND stk_tipos_articulo.naturaleza IS NOT NULL AND stk_tipos_articulo.naturaleza != ''
                    ORDER BY stk_tipos_articulo.naturaleza
                """, (enterprise_id,))
                naturalezas = [row['naturaleza'] for row in dictfetchall(cursor)]
            except Exception as e:
                print(f"Error cargando naturalezas: {e}")
                naturalezas = []
            
            # Tipos de Comprobante
            allowed_codigos = BillingService.get_allowed_comprobantes(condicion_iva_empresa, '*')
            if not allowed_codigos:
                allowed_codigos = ['006', '007', '008']
            
            placeholders = ', '.join(['%s'] * len(allowed_codigos))
            cursor.execute(f"SELECT codigo, descripcion, letra FROM sys_tipos_comprobante WHERE codigo IN ({placeholders})", tuple(allowed_codigos))
            tipos = dictfetchall(cursor)
            
            # Depósitos
            cursor.execute("SELECT id, nombre FROM stk_depositos WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1", (enterprise_id,))
            depositos = dictfetchall(cursor)
     
            # Condiciones de Pago
            cursor.execute("SELECT id, nombre, dias_vencimiento, descuento_pct FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            condiciones = dictfetchall(cursor)
     
            # Medios de Pago
            cursor.execute("""
                SELECT id, nombre, recargo_pct, tipo 
                FROM fin_medios_pago 
                WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 
                AND tipo NOT IN ('RETENCION', 'PERCEPCION')
                ORDER BY nombre
            """, (enterprise_id,))
            medios_pago = dictfetchall(cursor)
            
            # Jurisdicciones
            cursor.execute("""
                SELECT jurisdiccion FROM sys_enterprises_fiscal 
                WHERE enterprise_id = %s AND activo = 1 AND tipo IN ('PERCEPCION', 'AMBOS')
            """, (enterprise_id,))
            agente_percepciones = [j['jurisdiccion'].upper() for j in dictfetchall(cursor)]

            # Transportistas
            cursor.execute("SELECT id, nombre, cuit FROM stk_logisticas WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            transportistas = dictfetchall(cursor)

        context = {
            'clientes': clientes,
            'tipos_comprobante': tipos,
            'depositos': depositos,
            'medios_pago': medios_pago,
            'condiciones': condiciones,
            'naturalezas': naturalezas,
            'condicion_iva_empresa': condicion_iva_empresa,
            'agente_percepciones': agente_percepciones,
            'agente_percepciones_json': json.dumps(agente_percepciones),
            'now': datetime.date.today().isoformat(),
            'es_nota_credito': False,
            'es_nota_credito_json': 'false',
            'items_precargados_json': '[]',
            'transportistas': transportistas,
        }
        return render(request, 'ventas/facturar.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        from django.contrib import messages
        messages.error(request, f"Error al cargar facturación: {str(e)}")
        return redirect('ventas:comprobantes')

@login_required
def nota_credito(request, factura_id):
    from apps.ventas.billing_service import BillingService
    import datetime
    import json
    from django.contrib import messages
    enterprise_id = request.user_data['enterprise_id']
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT c.*, t.nombre as tercero_nombre, cp.nombre as condicion_pago_nombre
                FROM erp_comprobantes c
                JOIN erp_terceros t ON c.tercero_id = t.id
                LEFT JOIN fin_condiciones_pago cp ON c.condicion_pago_id = cp.id
                WHERE c.id = %s AND c.enterprise_id = %s
            """, (factura_id, enterprise_id))
            factura = dictfetchone(cursor)

            if not factura:
                messages.error(request, "Comprobante no encontrado.")
                return redirect('ventas:comprobantes')

            # Condición IVA Empresa
            cursor.execute("SELECT condicion_iva FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            empresa = dictfetchone(cursor)
            condicion_iva_empresa = empresa['condicion_iva'] if empresa else 'Responsable Inscripto'

            # Detalles (Ítems precargados)
            cursor.execute("""
                SELECT erp_comprobantes_detalle.*, stk_articulos.nombre as articulo_nombre 
                FROM erp_comprobantes_detalle 
                LEFT JOIN stk_articulos ON erp_comprobantes_detalle.articulo_id = stk_articulos.id 
                WHERE erp_comprobantes_detalle.comprobante_id = %s AND erp_comprobantes_detalle.enterprise_id = %s
            """, (factura_id, enterprise_id))
            items_db = dictfetchall(cursor)
            
            items_precargados = [{
                'id': i['articulo_id'],
                'nombre': i['articulo_nombre'] or i['descripcion'],
                'cantidad': float(i['cantidad']),
                'precio': float(i['precio_unitario']),
                'iva': float(i['alicuota_iva'])
            } for i in items_db]

            # Clientes
            cursor.execute("SELECT id, nombre, cuit, tipo_responsable FROM erp_terceros WHERE (enterprise_id = 0 OR enterprise_id = %s) AND es_cliente = 1 AND activo = 1", (enterprise_id,))
            clientes = dictfetchall(cursor)

            # Tipos de NC
            nc_codigo = BillingService.get_nc_type(factura['tipo_comprobante'])
            cursor.execute("SELECT codigo, descripcion, letra FROM sys_tipos_comprobante WHERE codigo IN ('003', '008', '013')")
            tipos = dictfetchall(cursor)

            # Obtener depósito origen
            cursor.execute("""
                SELECT m.deposito_destino_id 
                FROM stk_movimientos m 
                WHERE m.comprobante_id = %s AND m.enterprise_id = %s LIMIT 1
            """, (factura_id, enterprise_id))
            mov = dictfetchone(cursor)
            deposito_sugerido = mov['deposito_destino_id'] if mov else None

            # Obtener pagos originales
            cursor.execute("""
                SELECT mc.medio_pago_id, mp.nombre as medio_nombre, mc.importe
                FROM fin_factura_cobros mc
                JOIN fin_medios_pago mp ON mc.medio_pago_id = mp.id
                WHERE mc.factura_id = %s AND mc.enterprise_id = %s
            """, (factura_id, enterprise_id))
            pagos_originales = dictfetchall(cursor)

            # Depósitos
            cursor.execute("SELECT id, nombre FROM stk_depositos WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1", (enterprise_id,))
            depositos = dictfetchall(cursor)

            # Medios de Pago
            cursor.execute("""
                SELECT id, nombre, recargo_pct, tipo 
                FROM fin_medios_pago 
                WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 
                AND tipo NOT IN ('RETENCION', 'PERCEPCION')
                ORDER BY nombre
            """, (enterprise_id,))
            medios_pago = dictfetchall(cursor)

            # Condiciones de Pago
            cursor.execute("SELECT id, nombre, dias_vencimiento, descuento_pct FROM fin_condiciones_pago WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1 ORDER BY nombre", (enterprise_id,))
            condiciones = dictfetchall(cursor)
            
            # Jurisdicciones
            cursor.execute("""
                SELECT jurisdiccion FROM sys_enterprises_fiscal 
                WHERE enterprise_id = %s AND activo = 1 AND tipo IN ('PERCEPCION', 'AMBOS')
            """, (enterprise_id,))
            agente_percepciones = [j['jurisdiccion'].upper() for j in dictfetchall(cursor)]

            # Transportistas
            cursor.execute("SELECT id, nombre FROM stk_logisticas WHERE (enterprise_id = 0 OR enterprise_id = %s) AND activo = 1", (enterprise_id,))
            transportistas = dictfetchall(cursor)

        context = {
            'es_nota_credito': True,
            'es_nota_credito_json': 'true',
            'factura': factura,
            'cliente_preseleccionado': factura['tercero_id'],
            'items_precargados': items_precargados,
            'items_precargados_json': json.dumps(items_precargados),
            'tipo_sugerido': nc_codigo,
            'clientes': clientes, 
            'naturalezas': [], 
            'tipos_comprobante': tipos, 
            'depositos': depositos, 
            'transportistas': transportistas,
            'deposito_sugerido': deposito_sugerido,
            'medios_pago': medios_pago, 
            'pagos_originales': pagos_originales,
            'condiciones': condiciones, 
            'condicion_iva_empresa': condicion_iva_empresa,
            'agente_percepciones': agente_percepciones,
            'agente_percepciones_json': json.dumps(agente_percepciones),
            'now': datetime.date.today().isoformat()
        }
        return render(request, 'ventas/devolucion_solicitud.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect('ventas:comprobantes')


@login_required
def procesar_factura(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    enterprise_id = request.user_data['enterprise_id']
    user_id = request.user_data['id']
    payload = json.loads(request.body)

    try:
        with get_db_cursor(dictionary=True) as cursor:
            # 1. Resolver numeración
            punto_venta = 1 # TO-DO: Obtener de config empresa
            tipo_comp = payload['tipo_comprobante']
            
            # Obtener letra del comprobante
            cursor.execute("SELECT letra FROM sys_tipos_comprobante WHERE codigo = %s", (tipo_comp,))
            tipo_row = dictfetchone(cursor)
            letra = tipo_row['letra'] if tipo_row else 'X'

            numero = NumerationService.get_next_number(enterprise_id, tipo_comp, punto_venta, cursor)

            # 2. Cálculos básicos
            neto = 0
            iva = 0
            total = 0
            for item in payload['items']:
                n = float(item['neto'])
                i = float(item['iva'])
                neto += n
                iva += i
                total += (n + i)

            # 3. Guardar Cabecera
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
                cursor.execute("""
                    INSERT INTO erp_comprobantes_detalle (
                        comprobante_id, articulo_id, nombre, cantidad, precio_unitario,
                        alicuota_iva, importe_neto, importe_iva, importe_total, enterprise_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (comprobante_id, item['id'], item['nombre'], item['cantidad'], item['precio'],
                      item['alic_iva'], item['neto'], item['iva'], float(item['neto']) + float(item['iva']), enterprise_id))

            # 5. Stock y Contabilidad
            _generar_asiento_contable(enterprise_id, comprobante_id, cursor)

            # 6. AFIP
            afip_res = AfipService.solicitar_cae(enterprise_id, comprobante_id, cursor)

        return JsonResponse({
            'success': True,
            'id': comprobante_id,
            'afip': afip_res
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
def devolucion_solicitar(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    enterprise_id = request.user_data['enterprise_id']
    user_id = request.user_data['id']
    payload = json.loads(request.body)

    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT tipo_comprobante FROM erp_comprobantes WHERE id = %s", (payload['factura_id'],))
            orig = dictfetchone(cursor)
            tipo_nc = BillingService.get_nc_type(orig['tipo_comprobante'])
            
            punto_venta = 1
            numero = NumerationService.get_next_number(enterprise_id, tipo_nc, punto_venta, cursor)

            total = 0
            for it in payload['items']:
                total += float(it['subtotal'] or 0)

            cursor.execute("""
                INSERT INTO erp_comprobantes (
                    enterprise_id, modulo, tercero_id, tipo_comprobante,
                    punto_venta, numero, fecha_emision, importe_total,
                    comprobante_asociado_id, estado_pago, user_id
                ) VALUES (%s, 'VENTAS', %s, %s, %s, %s, CURRENT_DATE, %s, %s, 'PAGADO', %s)
            """, (enterprise_id, payload['cliente_id'], tipo_nc, punto_venta, numero, total, payload['factura_id'], user_id))
            
            cursor.execute("SELECT LAST_INSERT_ID() as last_id")
            nc_id = dictfetchone(cursor)['last_id']

            _generar_asiento_contable(enterprise_id, nc_id, cursor)

        return JsonResponse({'success': True, 'id': nc_id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

def _generar_asiento_contable(enterprise_id, comprobante_id, cursor):
    cursor.execute("SELECT * FROM erp_comprobantes WHERE id = %s", (comprobante_id,))
    comp = dictfetchone(cursor)
    if not comp: return
    
    cursor.execute("""
        INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, comprobante_id, estado)
        VALUES (%s, %s, %s, 'VENTAS', %s, 'CONFIRMADO')
    """, (enterprise_id, comp['fecha_emision'], f"Venta Comp. {comp['tipo_comprobante']} {comp['numero']}", comprobante_id))
    
    cursor.execute("SELECT LAST_INSERT_ID() as last_id")
    asiento_id = dictfetchone(cursor)['last_id']

    cursor.execute("""
        INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
        SELECT %s, id, %s, 0, 'Deudores por Ventas' FROM cont_plan_cuentas WHERE codigo = '1.3.01' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
    """, (asiento_id, comp['importe_total'], enterprise_id))

    cursor.execute("""
        INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
        SELECT %s, id, 0, %s, 'Ventas' FROM cont_plan_cuentas WHERE codigo = '4.1' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
    """, (asiento_id, comp['importe_neto'], enterprise_id))

    if comp.get('importe_iva') and comp['importe_iva'] > 0:
        cursor.execute("""
            INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa)
            SELECT %s, id, 0, %s, 'IVA Débito Fiscal' FROM cont_plan_cuentas WHERE codigo = '2.2.01' AND (enterprise_id = 0 OR enterprise_id = %s) LIMIT 1
        """, (asiento_id, comp['importe_iva'], enterprise_id))

    cursor.execute("UPDATE erp_comprobantes SET asiento_id = %s WHERE id = %s", (asiento_id, comprobante_id))

@login_required
def reenviar_comprobante(request, id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    # Simulación de reenvío
    return JsonResponse({'success': True, 'message': f'Comprobante {id} enviado correctamente por email.'})

