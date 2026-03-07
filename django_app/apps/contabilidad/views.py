import datetime
import re
import io
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

from apps.core.decorators import login_required, permission_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone

# --- UTILITARIO PARA FORMATO AFIP CUIT ---
def format_cuit(cuit_str):
    if not cuit_str: return ''
    clean = re.sub(r'\D', '', str(cuit_str))
    if len(clean) == 11:
        return f"{clean[:2]}-{clean[2:10]}-{clean[10]}"
    return clean

# --- DASHBOARD ---
@login_required
def dashboard(request):
    """Panel de Contabilidad."""
    return render(request, 'contabilidad/dashboard.html')

# --- CONFIG FISCAL ---
@login_required
def config_fiscal(request):
    """Configuración de certificados AFIP."""
    ent_id = request.user_data['enterprise_id']
    status = None
    
    if request.method == 'POST':
        cuit = request.POST.get('cuit')
        afip_crt = request.POST.get('afip_crt')
        afip_key = request.POST.get('afip_key')
        afip_entorno = request.POST.get('afip_entorno')
        
        cuit = format_cuit(cuit)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE sys_enterprises 
                SET cuit = %s, afip_crt = %s, afip_key = %s, afip_entorno = %s 
                WHERE id = %s
            """, (cuit, afip_crt, afip_key, afip_entorno, ent_id))
        messages.success(request, "Configuración fiscal actualizada correctamente")
        return redirect('contabilidad:config_fiscal')

    with get_db_cursor() as cursor:
        cursor.execute("SELECT cuit, afip_crt, afip_key, afip_entorno FROM sys_enterprises WHERE id = %s", (ent_id,))
        enterprise = dictfetchone(cursor)
        
    # TODO: Integrar AfipService para verificar (requiere portear el servicio a Django real)
    status = {'success': False, 'message': 'Status check (Stub) - Se implementará en versión final.'}
        
    return render(request, 'contabilidad/config_fiscal.html', {'enterprise': enterprise, 'status': status})

# --- LIBROS DE IVA ---
@login_required
def libro_iva_ventas(request):
    ent_id = request.user_data['enterprise_id']
    today = datetime.date.today()
    anio = int(request.GET.get('anio', today.year))
    mes = int(request.GET.get('mes', today.month))
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                erp_comprobantes.id, erp_comprobantes.fecha_emision, erp_comprobantes.tipo_comprobante, 
                erp_comprobantes.punto_venta, erp_comprobantes.numero,
                erp_comprobantes.importe_neto, erp_comprobantes.importe_iva, erp_comprobantes.importe_total,
                erp_terceros.nombre as cliente_nombre, erp_terceros.cuit as cliente_cuit, erp_terceros.tipo_responsable,
                sys_tipos_comprobante.descripcion as tipo_desc, sys_tipos_comprobante.letra
            FROM erp_comprobantes
            JOIN erp_terceros ON erp_comprobantes.tercero_id = erp_terceros.id
            JOIN sys_tipos_comprobante ON erp_comprobantes.tipo_comprobante = sys_tipos_comprobante.codigo
            WHERE erp_comprobantes.enterprise_id = %s 
              AND erp_comprobantes.tipo_operacion = 'VENTA'
              AND YEAR(erp_comprobantes.fecha_emision) = %s 
              AND MONTH(erp_comprobantes.fecha_emision) = %s
            ORDER BY erp_comprobantes.fecha_emision ASC, erp_comprobantes.numero ASC
        """, (ent_id, anio, mes))
        comprobantes_db = dictfetchall(cursor)
        
    reporte = []
    totales = {'neto': 0.0, 'iva': 0.0, 'total': 0.0}
    
    for comp in comprobantes_db:
        es_nc = comp['tipo_comprobante'] in ['003', '008', '013']
        signo = -1 if es_nc else 1
        
        neto = float(comp['importe_neto'] or 0) * signo
        iva = float(comp['importe_iva'] or 0) * signo
        total = float(comp['importe_total'] or 0) * signo
        
        fecha = comp['fecha_emision'].strftime('%d/%m/%Y') if hasattr(comp['fecha_emision'], 'strftime') else comp['fecha_emision']
        
        reporte.append({
            'fecha': fecha,
            'tipo': f"{comp['tipo_desc']} ({comp['letra']})",
            'numero': f"{comp['punto_venta']:04d}-{comp['numero']:08d}",
            'cliente': comp['cliente_nombre'],
            'cuit': comp['cliente_cuit'],
            'condicion': comp['tipo_responsable'],
            'neto': neto, 'iva': iva, 'total': total, 'es_nc': es_nc
        })
        totales['neto'] += neto
        totales['iva'] += iva
        totales['total'] += total

    meses_nombre = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    return render(request, 'contabilidad/libro_iva_ventas.html', {
        'anio': anio, 'mes': mes, 'reporte': reporte, 'totales': totales, 'meses_nombre': meses_nombre
    })

@login_required
def libro_iva_compras(request):
    ent_id = request.user_data['enterprise_id']
    today = datetime.date.today()
    anio = int(request.GET.get('anio', today.year))
    mes = int(request.GET.get('mes', today.month))
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                erp_comprobantes.id, erp_comprobantes.fecha_emision, erp_comprobantes.tipo_comprobante, 
                erp_comprobantes.punto_venta, erp_comprobantes.numero,
                erp_comprobantes.importe_neto, erp_comprobantes.importe_iva, erp_comprobantes.importe_total,
                erp_terceros.nombre as proveedor_nombre, erp_terceros.cuit as proveedor_cuit, erp_terceros.tipo_responsable,
                sys_tipos_comprobante.descripcion as tipo_desc, sys_tipos_comprobante.letra
            FROM erp_comprobantes
            JOIN erp_terceros ON erp_comprobantes.tercero_id = erp_terceros.id
            JOIN sys_tipos_comprobante ON erp_comprobantes.tipo_comprobante = sys_tipos_comprobante.codigo
            WHERE erp_comprobantes.enterprise_id = %s 
              AND erp_comprobantes.tipo_operacion = 'COMPRA'
              AND YEAR(erp_comprobantes.fecha_emision) = %s 
              AND MONTH(erp_comprobantes.fecha_emision) = %s
            ORDER BY erp_comprobantes.fecha_emision ASC, erp_comprobantes.numero ASC
        """, (ent_id, anio, mes))
        comprobantes_db = dictfetchall(cursor)
        
    reporte = []
    totales = {'neto': 0.0, 'iva': 0.0, 'total': 0.0}
    
    for comp in comprobantes_db:
        es_nc = comp['tipo_comprobante'] in ['003', '008', '013']
        signo = -1 if es_nc else 1
        
        neto = float(comp['importe_neto'] or 0) * signo
        iva = float(comp['importe_iva'] or 0) * signo
        total = float(comp['importe_total'] or 0) * signo
        
        fecha = comp['fecha_emision'].strftime('%d/%m/%Y') if hasattr(comp['fecha_emision'], 'strftime') else comp['fecha_emision']
        
        reporte.append({
            'fecha': fecha,
            'tipo': f"{comp['tipo_desc']} ({comp['letra']})",
            'numero': f"{comp['punto_venta']:04d}-{comp['numero']:08d}",
            'proveedor': comp['proveedor_nombre'],
            'cuit': comp['proveedor_cuit'],
            'condicion': comp['tipo_responsable'],
            'neto': neto, 'iva': iva, 'total': total, 'es_nc': es_nc
        })
        totales['neto'] += neto
        totales['iva'] += iva
        totales['total'] += total

    meses_nombre = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    return render(request, 'contabilidad/libro_iva_compras.html', {
        'anio': anio, 'mes': mes, 'reporte': reporte, 'totales': totales, 'meses_nombre': meses_nombre
    })

# --- PADRONES IIBB ---
@login_required
def padrones_iibb(request):
    stats = {}
    logs = []
    
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as total FROM sys_padrones_iibb")
        total = dictfetchone(cursor)
        
        cursor.execute("SELECT COUNT(DISTINCT jurisdiccion) as juris_cnt FROM sys_padrones_iibb")
        juris = dictfetchone(cursor)
        
        cursor.execute("SELECT COUNT(DISTINCT cuit) as cuit_cnt FROM sys_padrones_iibb")
        cuits = dictfetchone(cursor)

        stats = {
            'total_count': total['total'] if total else 0,
            'juris_count': juris['juris_cnt'] if juris else 0,
            'cuit_count': cuits['cuit_cnt'] if cuits else 0,
            'vigente': (total['total'] if total else 0) > 0
        }

        try:
            cursor.execute("SELECT * FROM sys_padrones_logs ORDER BY fecha_ejecucion DESC LIMIT 50")
            logs = dictfetchall(cursor)
        except Exception:
            logs = []

    return render(request, 'contabilidad/padrones.html', {'stats': stats, 'logs': logs})

@login_required
def api_consultar_padron(request, cuit):
    ent_id = request.user_data['enterprise_id']
    cuit_clean = re.sub(r'\D', '', cuit)
    res = {'jurisdicciones': {}, 'afip': None}
    
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM sys_padrones_iibb WHERE cuit = %s", (cuit_clean,))
        rows = dictfetchall(cursor)
        for r in rows:
            res['jurisdicciones'][r['jurisdiccion']] = {
                'alicuota_percepcion': float(r['alicuota_percepcion'] or 0),
                'alicuota_retencion': float(r['alicuota_retencion'] or 0),
                'grupo_riesgo': r.get('grupo_riesgo', ''),
                'desde': r['desde'].strftime('%Y-%m-%d') if r.get('desde') else None,
                'hasta': r['hasta'].strftime('%Y-%m-%d') if r.get('hasta') else None,
            }
            
    # Stub: Aquí iría la carga al AfipService real
    return JsonResponse(res)

@login_required
@require_POST
def importar_padron(request, jurisdiccion):
    if 'archivo' not in request.FILES:
        messages.error(request, "No se seleccionó archivo.")
        return redirect('contabilidad:padrones_iibb')
    
    # Esta es una versión reducida. En producción usar Celery para padrones de 1M de registros.
    messages.info(request, "La importación de padrones grandes a través de HTTP ha sido bloqueada. Se requiere ejecutar mediante CLI o worker para evitar timeouts.")
    return redirect('contabilidad:padrones_iibb')

# --- EXPORTACION AFIP TXT ---
@login_required
def exportar_afip(request):
    ent_id = request.user_data['enterprise_id']
    periodo = request.GET.get('periodo') # YYYYMM
    if not periodo or len(periodo) != 6:
        return HttpResponse("Falta periodo (YYYYMM)", status=400)
    
    anio = int(periodo[:4])
    mes = int(periodo[4:])
    modulo = request.GET.get('modulo', 'VENTAS')
    tipo_archivo = request.GET.get('tipo', 'CBTE')
    
    filename = f"LIBRO_IVA_{modulo}_{tipo_archivo}_{periodo}.txt"
    output = io.StringIO()
    
    with get_db_cursor() as cursor:
        if tipo_archivo == 'CBTE':
            cursor.execute("""
                SELECT erp_comprobantes.*, erp_terceros.cuit, erp_terceros.nombre, sys_tipos_comprobante.codigo as afip_tipo
                FROM erp_comprobantes
                JOIN erp_terceros ON erp_comprobantes.tercero_id = erp_terceros.id
                JOIN sys_tipos_comprobante ON erp_comprobantes.tipo_comprobante = sys_tipos_comprobante.codigo
                WHERE erp_comprobantes.enterprise_id = %s AND erp_comprobantes.modulo = %s
                  AND YEAR(erp_comprobantes.fecha_emision) = %s AND MONTH(erp_comprobantes.fecha_emision) = %s
            """, (ent_id, modulo, anio, mes))
            
            for r in dictfetchall(cursor):
                fecha = r['fecha_emision'].strftime('%Y%m%d') if hasattr(r['fecha_emision'], 'strftime') else ''
                tipo = f"{int(r['afip_tipo']):03}"
                pv = f"{int(r['punto_venta']):05}"
                nro = f"{int(r['numero']):020}"
                cuit_sujeto = re.sub(r'\D', '', r['cuit']).rjust(20, '0')
                nombre = (r['nombre'][:30]).ljust(30)
                
                total = f"{int(round(float(r['importe_total'] or 0) * 100)):015}"
                iva = f"{int(round(float(r['importe_iva'] or 0) * 100)):015}"
                
                line = f"{fecha}{tipo}{pv}{nro}{nro}80{cuit_sujeto}{nombre}{total}{'0'*15}{'0'*15}{'0'*15}{'0'*15}{'0'*15}{iva}{'0'*15}"
                output.write(line + "\r\n")
        
        else: # ALICUOTAS
            cursor.execute("""
                SELECT d.alicuota_iva, d.subtotal_neto, d.importe_iva, 
                       c.tipo_comprobante as afip_tipo, c.punto_venta, c.numero
                FROM erp_comprobantes_detalle d
                JOIN erp_comprobantes c ON d.comprobante_id = c.id
                WHERE c.enterprise_id = %s AND c.modulo = %s
                  AND YEAR(c.fecha_emision) = %s AND MONTH(c.fecha_emision) = %s
            """, (ent_id, modulo, anio, mes))
            
            map_ali = {21.0: '0005', 10.5: '0004', 27.0: '0006', 5.0: '0008', 2.5: '0009', 0.0: '0003'}
            for r in dictfetchall(cursor):
                tipo = f"{int(r['afip_tipo']):03}"
                pv = f"{int(r['punto_venta']):05}"
                nro = f"{int(r['numero']):020}"
                neto = f"{int(round(float(r['subtotal_neto'] or 0) * 100)):015}"
                ali_code = map_ali.get(float(r['alicuota_iva']), '0005')
                iva = f"{int(round(float(r['importe_iva'] or 0) * 100)):015}"
                
                line = f"{tipo}{pv}{nro}{neto}{ali_code}{iva}"
                output.write(line + "\r\n")

    response = HttpResponse(output.getvalue(), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@login_required
def reporte_iibb(request):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT sys_jurisdicciones.codigo, sys_jurisdicciones.nombre, 
                   COALESCE(SUM(erp_comprobantes.importe_neto), 0) as base,
                   COALESCE(SUM(erp_comprobantes.importe_percepcion_iibb_arba + erp_comprobantes.importe_percepcion_iibb_agip), 0) as percepciones,
                   COALESCE((SELECT SUM(importe_retencion) FROM fin_retenciones_emitidas WHERE enterprise_id = %s AND (jurisdiccion_id = sys_jurisdicciones.codigo OR (tipo_retencion='IIBB' AND sys_jurisdicciones.codigo=902))), 0) as retenciones
            FROM sys_jurisdicciones
            LEFT JOIN erp_comprobantes ON erp_comprobantes.jurisdiccion_id = sys_jurisdicciones.codigo AND erp_comprobantes.enterprise_id = %s
            GROUP BY sys_jurisdicciones.codigo, sys_jurisdicciones.nombre
            HAVING base > 0 OR percepciones > 0 OR retenciones > 0
            ORDER BY sys_jurisdicciones.codigo
        """, (ent_id, ent_id))
        reporte = dictfetchall(cursor)
        
    totales = {'base': 0, 'percepciones': 0, 'retenciones': 0}
    for r in reporte:
        totales['base'] += float(r['base'])
        totales['percepciones'] += float(r['percepciones'])
        totales['retenciones'] += float(r['retenciones'])
        
    c_m = datetime.date.today().strftime('%Y-%m')
    return render(request, 'contabilidad/reporte_iibb.html', {'reporte': reporte, 'totales': totales, 'current_month': c_m})

@login_required
def exportar_sicore(request):
    ent_id = request.user_data['enterprise_id']
    periodo = request.GET.get('periodo', datetime.date.today().strftime('%Y%m'))
    tipo = request.GET.get('tipo', 'SICORE')
    
    output = io.StringIO()
    filename = f"SICORE_{periodo}.txt"
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT fin_retenciones_emitidas.*, erp_terceros.cuit as sujeto_cuit
            FROM fin_retenciones_emitidas
            JOIN erp_terceros ON fin_retenciones_emitidas.tercero_id = erp_terceros.id
            WHERE fin_retenciones_emitidas.enterprise_id = %s 
              AND DATE_FORMAT(fin_retenciones_emitidas.fecha, '%%Y%%m') = %s
        """, (ent_id, periodo))
        
        for r in dictfetchall(cursor):
            fecha_str = r['fecha'].strftime('%d/%m/%Y') if hasattr(r['fecha'], 'strftime') else ''
            cuit_sujeto = re.sub(r'\D', '', r['sujeto_cuit']).rjust(11, '0')
            monto = f"{float(r['importe_retencion']):15.2f}".replace('.', ',').strip().rjust(15, '0')
            
            if tipo == 'SICORE':
                line = f"030775{fecha_str}{cuit_sujeto}{monto}"
            else:
                line = f"902{fecha_str}{cuit_sujeto}{monto}"
            output.write(line + "\r\n")
            
    response = HttpResponse(output.getvalue(), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response

# --- ASIENTOS CONTABLES ---
@login_required
def plan_cuentas(request):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM cont_plan_cuentas WHERE enterprise_id = %s ORDER BY codigo", (ent_id,))
        cuentas = dictfetchall(cursor)
    return render(request, 'contabilidad/plan_cuentas.html', {'cuentas': cuentas})

@login_required
def libro_diario(request):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cont_asientos.*, 
                   (SELECT SUM(debe) FROM cont_asientos_detalle WHERE asiento_id = cont_asientos.id) as total_debe,
                   (SELECT SUM(haber) FROM cont_asientos_detalle WHERE asiento_id = cont_asientos.id) as total_haber
            FROM cont_asientos 
            WHERE cont_asientos.enterprise_id = %s 
            ORDER BY cont_asientos.fecha DESC, cont_asientos.id DESC
        """, (ent_id,))
        asientos = dictfetchall(cursor)
    return render(request, 'contabilidad/libro_diario.html', {'asientos': asientos})

@login_required
def ver_asiento(request, id):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM cont_asientos WHERE id = %s AND enterprise_id = %s", (id, ent_id))
        asiento = dictfetchone(cursor)
        if not asiento:
            messages.error(request, "Asiento no encontrado")
            return redirect('contabilidad:libro_diario')
        
        cursor.execute("""
            SELECT cont_asientos_detalle.*, cont_plan_cuentas.codigo as cuenta_codigo, cont_plan_cuentas.nombre as cuenta_nombre
            FROM cont_asientos_detalle
            JOIN cont_plan_cuentas ON cont_asientos_detalle.cuenta_id = cont_plan_cuentas.id
            WHERE cont_asientos_detalle.asiento_id = %s
        """, (id,))
        detalles = dictfetchall(cursor)
    return render(request, 'contabilidad/ver_asiento.html', {'asiento': asiento, 'detalles': detalles})

# --- FUNCION INTERNA PARA OBTENER CÓDIGO DE CUENTA ---
def _get_cuenta_id(cursor, enterprise_id, codigo):
    cursor.execute("SELECT id FROM cont_plan_cuentas WHERE enterprise_id = %s AND codigo = %s", (enterprise_id, codigo))
    res = dictfetchone(cursor)
    if not res:
        cursor.execute("SELECT id FROM cont_plan_cuentas WHERE (enterprise_id = 0 OR enterprise_id = 1) AND codigo = %s LIMIT 1", (codigo,))
        res = dictfetchone(cursor)
    return res['id'] if res else None

# --- CENTRALIZACION (Core de Contabilidad) ---
@login_required
def centralizacion(request):
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']
    today = datetime.date.today()
    meses_nombre = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    if request.method == 'POST':
        modulo = request.POST.get('modulo')
        mes = int(request.POST.get('mes'))
        anio = int(request.POST.get('anio'))
        
        try:
            res_id = _generar_asiento_resumen(cursor_ext=None, modulo=modulo, mes=mes, anio=anio, ent_id=ent_id, uid=uid)
            if res_id:
                messages.success(request, f"Centralización de {modulo} realizada con éxito. Asiento #{res_id}")
            else:
                messages.warning(request, f"No hay comprobantes pendientes de centralizar para {modulo} en {mes}/{anio}")
        except Exception as e:
            messages.error(request, f"Error en centralización: {str(e)}")
        
        return redirect('contabilidad:centralizacion')

    pendientes = []
    with get_db_cursor() as cursor:
        cursor.execute("SELECT 'VENTAS' as modulo, COUNT(*) as cantidad, SUM(importe_total) as total FROM erp_comprobantes WHERE enterprise_id = %s AND modulo = 'VENTAS' AND asiento_id IS NULL", (ent_id,))
        pendientes.append(dictfetchone(cursor))
        
        cursor.execute("SELECT 'COMPRAS' as modulo, COUNT(*) as cantidad, SUM(importe_total) as total FROM erp_comprobantes WHERE enterprise_id = %s AND modulo = 'COMPRAS' AND asiento_id IS NULL", (ent_id,))
        pendientes.append(dictfetchone(cursor))

        cursor.execute("SELECT 'FONDOS' as modulo, COUNT(*) as cantidad, SUM(importe) as total FROM erp_movimientos_fondos WHERE enterprise_id = %s AND asiento_id IS NULL", (ent_id,))
        pendientes.append(dictfetchone(cursor))
        
        cursor.execute("SELECT 'SUELDOS' as modulo, COUNT(*) as cantidad, SUM(total_neto) as total FROM fin_nominas WHERE enterprise_id = %s AND asiento_id IS NULL", (ent_id,))
        pendientes.append(dictfetchone(cursor))

    return render(request, 'contabilidad/centralizacion.html', {
        'meses_nombre': meses_nombre, 'today_mes': today.month, 'today_anio': today.year, 'pendientes': pendientes
    })

def _generar_asiento_resumen(cursor_ext, modulo, mes, anio, ent_id, uid):
    # Usamos nuestro propio cursor para asegurar transaccionalidad si no fue provisto
    def execute_logic(cursor):
        if modulo == 'VENTAS':
            cursor.execute("""
                SELECT id, importe_neto, importe_iva, importe_total, tipo_comprobante
                FROM erp_comprobantes 
                WHERE enterprise_id = %s AND modulo = 'VENTAS' AND asiento_id IS NULL
                AND MONTH(fecha_emision) = %s AND YEAR(fecha_emision) = %s
            """, (ent_id, mes, anio))
            comprobantes = dictfetchall(cursor)
            if not comprobantes: return None
            
            t_neto, t_iva, t_total, ids = 0, 0, 0, []
            for c in comprobantes:
                signo = -1 if c['tipo_comprobante'] in ['003', '008', '013'] else 1
                t_neto += float(c['importe_neto'] or 0) * signo
                t_iva += float(c['importe_iva'] or 0) * signo
                t_total += float(c['importe_total'] or 0) * signo
                ids.append(c['id'])
                
            fecha_asiento = datetime.date(anio, 12, 31) if mes == 12 else datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)
            
            cursor.execute("INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, user_id) VALUES (%s, %s, %s, %s, %s)",
                           (ent_id, fecha_asiento, f"Centralización Ventas {mes}/{anio}", 'VENTAS', uid))
            cursor.execute("SELECT LAST_INSERT_ID() as lid")
            asiento_id = dictfetchone(cursor)['lid']
            
            cta_deudores = _get_cuenta_id(cursor, ent_id, '1.3.01')
            cta_ventas = _get_cuenta_id(cursor, ent_id, '4.1')
            cta_iva_db = _get_cuenta_id(cursor, ent_id, '2.2.01')
            
            # DEBE
            cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (asiento_id, cta_deudores, t_total if t_total > 0 else 0, abs(t_total) if t_total < 0 else 0, "Deudores por Ventas", ent_id, uid))
            # HABER Ventas
            cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (asiento_id, cta_ventas, abs(t_neto) if t_neto < 0 else 0, t_neto if t_neto > 0 else 0, "Ventas del periodo", ent_id, uid))
            # HABER IVA
            if t_iva != 0:
                cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (asiento_id, cta_iva_db, abs(t_iva) if t_iva < 0 else 0, t_iva if t_iva > 0 else 0, "IVA Débito Fiscal", ent_id, uid))
            
            format_strings = ','.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE erp_comprobantes SET asiento_id = %s WHERE id IN ({format_strings})", [asiento_id] + ids)
            return asiento_id

        elif modulo == 'COMPRAS':
            cursor.execute("""
                SELECT id, importe_neto, importe_iva, importe_total, tipo_comprobante
                FROM erp_comprobantes 
                WHERE enterprise_id = %s AND modulo = 'COMPRAS' AND asiento_id IS NULL
                AND MONTH(fecha_emision) = %s AND YEAR(fecha_emision) = %s
            """, (ent_id, mes, anio))
            comprobantes = dictfetchall(cursor)
            if not comprobantes: return None
            
            t_neto, t_iva, t_total, ids = 0, 0, 0, []
            for c in comprobantes:
                signo = -1 if c['tipo_comprobante'] in ['003', '008', '013'] else 1
                t_neto += float(c['importe_neto'] or 0) * signo
                t_iva += float(c['importe_iva'] or 0) * signo
                t_total += float(c['importe_total'] or 0) * signo
                ids.append(c['id'])

            fecha_asiento = datetime.date(anio, 12, 31) if mes == 12 else datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)
            cursor.execute("INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, user_id) VALUES (%s, %s, %s, %s, %s)",
                           (ent_id, fecha_asiento, f"Centralización Compras {mes}/{anio}", 'COMPRAS', uid))
            cursor.execute("SELECT LAST_INSERT_ID() as lid")
            asiento_id = dictfetchone(cursor)['lid']
            
            cta_gastos = _get_cuenta_id(cursor, ent_id, '5.2') 
            cta_iva_cr = _get_cuenta_id(cursor, ent_id, '1.5.01') or _get_cuenta_id(cursor, ent_id, '2.2.01')
            cta_proveedores = _get_cuenta_id(cursor, ent_id, '2.1.01')
            
            cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (asiento_id, cta_proveedores, abs(t_total) if t_total < 0 else 0, t_total if t_total > 0 else 0, "Proveedores (Acreedores)", ent_id, uid))
            cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (asiento_id, cta_gastos, t_neto if t_neto > 0 else 0, abs(t_neto) if t_neto < 0 else 0, "Compras de Bienes/Servicios", ent_id, uid))
            if t_iva != 0:
                cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                               (asiento_id, cta_iva_cr, t_iva if t_iva > 0 else 0, abs(t_iva) if t_iva < 0 else 0, "IVA Crédito Fiscal", ent_id, uid))
            
            format_strings = ','.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE erp_comprobantes SET asiento_id = %s WHERE id IN ({format_strings})", [asiento_id] + ids)
            return asiento_id

        elif modulo == 'FONDOS':
            cursor.execute("""
                SELECT m.*, cf.cuenta_contable_id
                FROM erp_movimientos_fondos m
                JOIN erp_cuentas_fondos cf ON m.cuenta_fondo_id = cf.id
                WHERE m.enterprise_id = %s AND m.asiento_id IS NULL
                AND MONTH(m.fecha) = %s AND YEAR(m.fecha) = %s
            """, (ent_id, mes, anio))
            movimientos = dictfetchall(cursor)
            if not movimenti: return None

            saldos = {}
            ids = []
            cta_deudores = _get_cuenta_id(cursor, ent_id, '1.3.01')
            cta_proveedores = _get_cuenta_id(cursor, ent_id, '2.1.01')
            
            for m in movimientos:
                importe = float(m['importe'])
                ctid = m['cuenta_contable_id']
                ids.append(m['id'])
                if ctid not in saldos: saldos[ctid] = {'debe': 0, 'haber': 0}
                
                if m['tipo'] == 'INGRESO':
                    saldos[ctid]['debe'] += importe
                    if cta_deudores not in saldos: saldos[cta_deudores] = {'debe': 0, 'haber': 0}
                    saldos[cta_deudores]['haber'] += importe
                else:
                    saldos[ctid]['haber'] += importe
                    if cta_proveedores not in saldos: saldos[cta_proveedores] = {'debe': 0, 'haber': 0}
                    saldos[cta_proveedores]['debe'] += importe

            fecha_asiento = datetime.date(anio, 12, 31) if mes == 12 else datetime.date(anio, mes + 1, 1) - datetime.timedelta(days=1)
            cursor.execute("INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, user_id) VALUES (%s, %s, %s, %s, %s)",
                           (ent_id, fecha_asiento, f"Centralización Tesorería {mes}/{anio}", 'FONDOS', uid))
            cursor.execute("SELECT LAST_INSERT_ID() as lid")
            asiento_id = dictfetchone(cursor)['lid']
            
            for ctid, values in saldos.items():
                if values['debe'] != 0 or values['haber'] != 0:
                    cursor.execute("""
                        INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (asiento_id, ctid, values['debe'], values['haber'], "Movimientos de Tesorería", ent_id, uid))
            
            format_strings = ','.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE erp_movimientos_fondos SET asiento_id = %s WHERE id IN ({format_strings})", [asiento_id] + ids)
            return asiento_id

        return None

    if cursor_ext:
        return execute_logic(cursor_ext)
    else:
        with get_db_cursor() as cursor:
            return execute_logic(cursor)

# --- SUELDOS ---
@login_required
def sueldos_dashboard(request):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM fin_nominas WHERE enterprise_id = %s ORDER BY periodo DESC", (ent_id,))
        nominas = dictfetchall(cursor)
    return render(request, 'contabilidad/sueldos.html', {'nominas': nominas})

@login_required
@require_POST
def liquidar_sueldos(request):
    ent_id = request.user_data['enterprise_id']
    periodo = request.POST.get('periodo') # YYYY-MM
    descripcion = request.POST.get('descripcion', f"Liquidación {periodo}")
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO fin_nominas (enterprise_id, periodo, descripcion, estado)
            VALUES (%s, %s, %s, 'LIQUIDADO')
        """, (ent_id, periodo, descripcion))
        cursor.execute("SELECT LAST_INSERT_ID() as lid")
        nomina_id = dictfetchone(cursor)['lid']
        
        cursor.execute("SELECT id FROM sys_users WHERE enterprise_id = %s", (ent_id,))
        empleados = dictfetchall(cursor)
        
        total_bruto = 0
        total_neto = 0
        
        for emp in empleados:
            bruto = 100000.0
            retenciones = bruto * 0.17
            neto = bruto - retenciones
            cursor.execute("""
                INSERT INTO fin_liquidaciones (enterprise_id, nomina_id, usuario_id, sueldo_bruto, retenciones, neto_a_cobrar)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (ent_id, nomina_id, emp['id'], bruto, retenciones, neto))
            total_bruto += bruto
            total_neto += neto
            
        cursor.execute("UPDATE fin_nominas SET total_bruto = %s, total_neto = %s WHERE id = %s", (total_bruto, total_neto, nomina_id))
    
    messages.success(request, f"Nómina de {periodo} generada correctamente para {len(empleados)} empleados.")
    return redirect('contabilidad:sueldos_dashboard')

@login_required
@require_POST
def centralizar_sueldos(request, id):
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM fin_nominas WHERE id = %s AND enterprise_id = %s AND asiento_id IS NULL", (id, ent_id))
        nomina = dictfetchone(cursor)
        
        if not nomina:
            messages.warning(request, "Nómina no encontrada o ya centralizada.")
            return redirect('contabilidad:sueldos_dashboard')
        
        cta_sueldos_gasto = _get_cuenta_id(cursor, ent_id, '5.2.01')
        cta_sueldos_pagar = _get_cuenta_id(cursor, ent_id, '2.1.01')
        
        cursor.execute("""
            INSERT INTO cont_asientos (enterprise_id, fecha, concepto, modulo_origen, user_id)
            VALUES (%s, NOW(), %s, 'SUELDOS', %s)
        """, (ent_id, f"Asiento Sueldos {nomina['periodo']}", uid))
        cursor.execute("SELECT LAST_INSERT_ID() as lid")
        asiento_id = dictfetchone(cursor)['lid']
        
        cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (asiento_id, cta_sueldos_gasto, nomina['total_bruto'], 0, "Sueldos Brutos Periodo", ent_id, uid))
        
        cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                       (asiento_id, cta_sueldos_pagar, 0, nomina['total_neto'], "Sueldos a Pagar (Neto)", ent_id, uid))
        
        ret_val = float(nomina['total_bruto']) - float(nomina['total_neto'])
        if ret_val > 0:
            cta_retenciones = _get_cuenta_id(cursor, ent_id, '2.2.02')
            cursor.execute("INSERT INTO cont_asientos_detalle (asiento_id, cuenta_id, debe, haber, glosa, enterprise_id, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (asiento_id, cta_retenciones, 0, ret_val, "Aportes y Contribuciones a Pagar", ent_id, uid))
        
        cursor.execute("UPDATE fin_nominas SET asiento_id = %s, estado = 'CONTABILIZADO' WHERE id = %s", (asiento_id, id))
        
    messages.success(request, f"Nómina centralizada con Asiento #{asiento_id}")
    return redirect('contabilidad:sueldos_dashboard')
