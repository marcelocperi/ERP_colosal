from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.core.decorators import login_required, permission_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
import json


@login_required
@permission_required('view_compras')
def dashboard(request):
    """Dashboard del módulo de Compras con KPIs de cotizaciones."""
    ent_id = request.user_data['enterprise_id']
    kpi = {'enviadas': 0, 'recibidas': 0, 'efectividad': 0,
           'items_no_provistos': 0, 'valor_no_provisto': 0}
    cotizaciones = []
    alertas = []

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) as total FROM cmp_cotizaciones WHERE estado != 'BORRADOR' AND enterprise_id = %s",
            (ent_id,)
        )
        row = dictfetchone(cursor)
        kpi['enviadas'] = row['total'] if row else 0

        cursor.execute(
            "SELECT COUNT(*) as total FROM cmp_cotizaciones WHERE estado IN ('RECIBIDA_PARCIAL','RECIBIDA_TOTAL','CONFIRMADA') AND enterprise_id = %s",
            (ent_id,)
        )
        row = dictfetchone(cursor)
        kpi['recibidas'] = row['total'] if row else 0

        if kpi['enviadas'] > 0:
            kpi['efectividad'] = round((kpi['recibidas'] / kpi['enviadas']) * 100, 1)

        cursor.execute("""
            SELECT COUNT(*) as count, SUM(cmp_items_cotizacion.cantidad * COALESCE(stk_articulos.costo, 0)) as valor
            FROM cmp_items_cotizacion
            JOIN cmp_cotizaciones ON cmp_items_cotizacion.cotizacion_id = cmp_cotizaciones.id
            JOIN stk_articulos ON cmp_items_cotizacion.articulo_id = stk_articulos.id
            WHERE cmp_cotizaciones.estado IN ('RECIBIDA_TOTAL', 'CONFIRMADA')
              AND (cmp_items_cotizacion.cantidad_ofrecida IS NULL OR cmp_items_cotizacion.cantidad_ofrecida = 0)
              AND cmp_cotizaciones.enterprise_id = %s AND cmp_items_cotizacion.enterprise_id = %s
        """, (ent_id, ent_id))
        row = dictfetchone(cursor)
        if row:
            kpi['items_no_provistos'] = row['count'] or 0
            kpi['valor_no_provisto'] = float(row['valor'] or 0)

        cursor.execute("""
            SELECT cmp_cotizaciones.*, cmp_cotizaciones.fecha_envio as fecha,
                   erp_terceros.nombre as razon_social,
                   (SELECT COUNT(*) FROM cmp_items_cotizacion
                    WHERE cotizacion_id = cmp_cotizaciones.id AND enterprise_id = %s) as items_cnt
            FROM cmp_cotizaciones
            JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
            WHERE cmp_cotizaciones.enterprise_id = %s
            ORDER BY cmp_cotizaciones.fecha_envio DESC LIMIT 10
        """, (ent_id, ent_id))
        cotizaciones = dictfetchall(cursor)

        cursor.execute("""
            SELECT cmp_items_cotizacion.*, stk_articulos.nombre as articulo, stk_articulos.codigo,
                   cmp_cotizaciones.fecha_envio as fecha, erp_terceros.nombre as razon_social
            FROM cmp_items_cotizacion
            JOIN cmp_cotizaciones ON cmp_items_cotizacion.cotizacion_id = cmp_cotizaciones.id
            JOIN stk_articulos ON cmp_items_cotizacion.articulo_id = stk_articulos.id
            JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
            WHERE cmp_cotizaciones.estado IN ('RECIBIDA_TOTAL', 'CONFIRMADA')
              AND (cmp_items_cotizacion.cantidad_ofrecida IS NULL OR cmp_items_cotizacion.cantidad_ofrecida = 0)
              AND cmp_cotizaciones.enterprise_id = %s AND cmp_items_cotizacion.enterprise_id = %s
            ORDER BY cmp_cotizaciones.fecha_envio DESC LIMIT 20
        """, (ent_id, ent_id))
        alertas = dictfetchall(cursor)

    return render(request, 'compras/dashboard.html', {
        'kpi': kpi,
        'cotizaciones': cotizaciones,
        'alertas': alertas,
    })


@login_required
def proveedores(request):
    """Listado maestro de proveedores."""
    ent_id = request.user_data['enterprise_id']
    q = request.GET.get('q', '')

    with get_db_cursor() as cursor:
        if q:
            cursor.execute("""
                SELECT erp_terceros.*, erp_direcciones.localidad, erp_direcciones.provincia
                FROM erp_terceros
                LEFT JOIN erp_direcciones ON erp_terceros.id = erp_direcciones.tercero_id AND erp_direcciones.es_fiscal = 1
                WHERE (erp_terceros.enterprise_id = %s OR erp_terceros.enterprise_id = 0)
                  AND erp_terceros.es_proveedor = 1
                  AND (erp_terceros.nombre LIKE %s OR erp_terceros.cuit LIKE %s OR erp_terceros.codigo LIKE %s)
                GROUP BY erp_terceros.id ORDER BY erp_terceros.nombre
            """, (ent_id, f'%{q}%', f'%{q}%', f'%{q}%'))
        else:
            cursor.execute("""
                SELECT erp_terceros.*, erp_direcciones.localidad, erp_direcciones.provincia
                FROM erp_terceros
                LEFT JOIN erp_direcciones ON erp_terceros.id = erp_direcciones.tercero_id AND erp_direcciones.es_fiscal = 1
                WHERE (erp_terceros.enterprise_id = %s OR erp_terceros.enterprise_id = 0)
                  AND erp_terceros.es_proveedor = 1
                GROUP BY erp_terceros.id ORDER BY erp_terceros.nombre
            """, (ent_id,))
        proveedores = dictfetchall(cursor)

    return render(request, 'compras/proveedores.html', {
        'proveedores': proveedores,
        'q': q,
    })


@login_required
def nuevo_proveedor(request):
    """Formulario de alta de proveedores."""
    if request.method == 'POST':
        from django.contrib import messages
        nombre = request.POST.get('nombre', '')
        cuit = request.POST.get('cuit', '')
        email = request.POST.get('email', '')
        tipo = request.POST.get('tipo_responsable', 'RI')
        obs = request.POST.get('observaciones', '')
        ent_id = request.user_data['enterprise_id']
        uid = request.user_data['id']

        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM erp_terceros WHERE cuit = %s AND enterprise_id = %s", (cuit, ent_id))
            if dictfetchone(cursor):
                messages.error(request, f'Ya existe un proveedor con el CUIT {cuit}.')
            else:
                origen = request.POST.get('origen', 'LOCAL')
                
                if origen == 'LOCAL':
                    prefix = 'PRO-'
                else:
                    prefix = 'PEX-'
                    
                cursor.execute("""
                    SELECT CONCAT(%s, LPAD(COALESCE(MAX(CAST(SUBSTRING(codigo, 5) AS UNSIGNED)), 0) + 1, 5, '0'))
                    as next_code FROM erp_terceros WHERE enterprise_id = %s AND codigo LIKE %s
                """, (prefix, ent_id, prefix + '%'))
                row = dictfetchone(cursor)
                codigo = row['next_code'] if row else f'{prefix}00001'

                cursor.execute("""
                    INSERT INTO erp_terceros (enterprise_id, codigo, nombre, cuit, email, observaciones,
                                             es_cliente, es_proveedor, tipo_responsable, naturaleza, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (ent_id, codigo, nombre, cuit, email, obs, 0, 1, tipo, 'PRO', uid))
                # Obtener el ID insertado
                cursor.execute("SELECT LAST_INSERT_ID() as last_id")
                row = dictfetchone(cursor)
                messages.success(request, f'Proveedor {nombre} creado con código {codigo}.')
                
                url = reverse('compras:perfil_proveedor', kwargs={'id': row['last_id']})
                if hasattr(request, 'sid') and request.sid:
                    url += f'?sid={request.sid}'
                return redirect(url)

    return render(request, 'compras/proveedor_form.html', {'accion': 'nuevo'})


@login_required
def editar_proveedor(request, id):
    """Actualiza datos básicos del proveedor."""
    if request.method == 'POST':
        ent_id = request.user_data['enterprise_id']
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE erp_terceros SET nombre=%s, cuit=%s, email=%s, tipo_responsable=%s,
                       observaciones=%s, telefono=%s, user_id_update=%s
                WHERE id=%s AND enterprise_id=%s
            """, (
                request.POST.get('nombre'), request.POST.get('cuit'),
                request.POST.get('email'), request.POST.get('tipo_responsable', 'RI'),
                request.POST.get('observaciones', ''), request.POST.get('telefono', ''),
                request.user_data['id'], id, ent_id
            ))
        messages.success(request, 'Proveedor actualizado correctamente.')
        
    url = reverse('compras:perfil_proveedor', kwargs={'id': id})
    if hasattr(request, 'sid') and request.sid:
        url += f'?sid={request.sid}'
    return redirect(url)


@login_required
def perfil_proveedor(request, id):
    """Ficha completa del proveedor."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM erp_terceros WHERE id = %s AND (enterprise_id = %s OR enterprise_id = 0)", (id, ent_id))
        proveedor = dictfetchone(cursor)
        if not proveedor:
            return redirect('compras:proveedores')

        cursor.execute("SELECT * FROM erp_direcciones WHERE tercero_id = %s AND enterprise_id = %s", (id, ent_id))
        direcciones = dictfetchall(cursor)

        cursor.execute("""
            SELECT erp_contactos.*, erp_puestos.nombre as puesto_nombre
            FROM erp_contactos
            LEFT JOIN erp_puestos ON erp_contactos.puesto_id = erp_puestos.id
            WHERE erp_contactos.tercero_id = %s AND erp_contactos.enterprise_id = %s
        """, (id, ent_id))
        contactos = dictfetchall(cursor)

        # Últimas órdenes de compra
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, sys_users.username
            FROM cmp_ordenes_compra
            JOIN sys_users ON cmp_ordenes_compra.user_id = sys_users.id
            WHERE cmp_ordenes_compra.proveedor_id = %s AND cmp_ordenes_compra.enterprise_id = %s
            ORDER BY cmp_ordenes_compra.fecha DESC LIMIT 10
        """, (id, ent_id))
        ordenes = dictfetchall(cursor)

        # Artículos habituales del proveedor
        cursor.execute("""
            SELECT cmp_articulos_proveedores.*, stk_articulos.nombre as articulo_nombre, stk_articulos.codigo
            FROM cmp_articulos_proveedores
            JOIN stk_articulos ON cmp_articulos_proveedores.articulo_id = stk_articulos.id
            WHERE cmp_articulos_proveedores.proveedor_id = %s AND cmp_articulos_proveedores.enterprise_id = %s
        """, (id, ent_id))
        articulos_prov = dictfetchall(cursor)

        cursor.execute("SELECT * FROM erp_datos_fiscales WHERE tercero_id = %s AND enterprise_id = %s", (id, ent_id))
        fiscales = dictfetchall(cursor)

        # Coeficientes CM05
        cursor.execute("""
            SELECT erp_terceros_cm05.*, sys_provincias.nombre as provincia_nombre
            FROM erp_terceros_cm05
            JOIN sys_provincias ON erp_terceros_cm05.jurisdiccion_code = sys_provincias.codigo_jurisdiccion
            WHERE erp_terceros_cm05.tercero_id = %s AND erp_terceros_cm05.enterprise_id = %s
        """, (id, ent_id))
        coeficientes_cm = dictfetchall(cursor)

        # Provincias
        cursor.execute("SELECT * FROM sys_provincias ORDER BY nombre ASC")
        provincias = dictfetchall(cursor)

    return render(request, 'compras/perfil_proveedor.html', {
        'proveedor': proveedor,
        'direcciones': direcciones,
        'contactos': contactos,
        'ordenes': ordenes,
        'articulos_prov': articulos_prov,
        'fiscales': fiscales,
        'coeficientes_cm': coeficientes_cm,
        'provincias': provincias,
    })


@login_required
@permission_required('compras.gestionar_reposicion')
def reposicion_dashboard(request):
    """Tablero de faltantes agrupados por proveedor."""
    ent_id = request.user_data['enterprise_id']
    origen_id_filter = request.GET.get('origen_id', '')
    proveedor_id_filter = request.GET.get('proveedor_id', '')

    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM cmp_sourcing_origenes WHERE activo = 1 ORDER BY nombre")
        origenes = dictfetchall(cursor)

        cursor.execute(
            "SELECT id, nombre FROM erp_terceros WHERE (enterprise_id = %s OR enterprise_id = 0) AND es_proveedor = 1 ORDER BY nombre",
            (ent_id,)
        )
        proveedores_dd = dictfetchall(cursor)

        filtros_sql = ""
        params = [ent_id]
        if origen_id_filter:
            filtros_sql += " AND cmp_articulos_proveedores.origen_id = %s"
            params.append(origen_id_filter)
        if proveedor_id_filter:
            filtros_sql += " AND cmp_articulos_proveedores.proveedor_id = %s"
            params.append(proveedor_id_filter)

        cursor.execute(f"""
            SELECT t.id, t.codigo, t.nombre, t.punto_pedido, t.stock_minimo, t.cant_min_pedido,
                   t.stock_actual, t.proveedor_id, t.proveedor_nombre, t.proveedor_email,
                   t.lead_time_dias, t.es_habitual, t.es_proveedor_extranjero,
                   COALESCE(
                       CEIL(GREATEST((t.punto_pedido - t.stock_actual), 0.0001) / NULLIF(t.cant_min_pedido, 0)) * t.cant_min_pedido,
                       GREATEST((t.punto_pedido - t.stock_actual), 0)
                   ) as sugerido
            FROM (
                SELECT stk_articulos.id, stk_articulos.codigo, stk_articulos.nombre,
                       stk_articulos.punto_pedido, stk_articulos.stock_minimo, stk_articulos.cant_min_pedido,
                       (SELECT COALESCE(SUM(cantidad), 0) 
                        FROM stk_existencias 
                        WHERE articulo_id = stk_articulos.id AND enterprise_id = stk_articulos.enterprise_id
                       ) as stock_actual,
                       cmp_articulos_proveedores.proveedor_id,
                       erp_terceros.nombre as proveedor_nombre, erp_terceros.email as proveedor_email,
                       cmp_articulos_proveedores.lead_time_dias, cmp_articulos_proveedores.es_habitual,
                       erp_terceros.es_proveedor_extranjero
                FROM stk_articulos
                LEFT JOIN cmp_articulos_proveedores ON stk_articulos.id = cmp_articulos_proveedores.articulo_id
                    AND stk_articulos.enterprise_id = cmp_articulos_proveedores.enterprise_id
                    AND cmp_articulos_proveedores.es_habitual = 1
                LEFT JOIN erp_terceros ON cmp_articulos_proveedores.proveedor_id = erp_terceros.id
                WHERE stk_articulos.enterprise_id = %s AND stk_articulos.activo = 1 {filtros_sql}
            ) as t
            WHERE t.stock_actual <= t.punto_pedido AND t.punto_pedido > 0
            ORDER BY t.proveedor_nombre, (t.punto_pedido - t.stock_actual) DESC
        """, tuple(params))
        faltantes = dictfetchall(cursor)

    # Agrupar por proveedor en Python
    grupos = {}
    for f in faltantes:
        pid = f['proveedor_id'] or 0
        pnom = f['proveedor_nombre'] or 'Sin Asignar'
        if pid not in grupos:
            grupos[pid] = {
                'id': pid, 'nombre': pnom,
                'email': f.get('proveedor_email'),
                'es_extranjero': f['es_proveedor_extranjero'] == 1,
                'faltantes': []
            }
        grupos[pid]['faltantes'].append(f)

    grupos_list = sorted(grupos.values(), key=lambda x: (x['id'] == 0, x['nombre']))

    return render(request, 'compras/reposicion_dashboard.html', {
        'grupos': grupos_list,
        'origenes': origenes,
        'proveedores_dd': proveedores_dd,
        'origen_id_filter': origen_id_filter,
        'proveedor_id_filter': proveedor_id_filter,
    })


@login_required
@permission_required('compras.gestionar_reposicion')
def solicitudes_lista(request):
    """Listado de Solicitudes de Reposición (NPs)."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_solicitudes_reposicion.*, sys_users.username as solicitante_nombre,
                   (SELECT COUNT(*) FROM cmp_detalles_solicitud
                    WHERE solicitud_id = cmp_solicitudes_reposicion.id) as items_cnt
            FROM cmp_solicitudes_reposicion
            JOIN sys_users ON cmp_solicitudes_reposicion.solicitante_id = sys_users.id
            WHERE cmp_solicitudes_reposicion.enterprise_id = %s
            ORDER BY cmp_solicitudes_reposicion.fecha DESC
        """, (ent_id,))
        solicitudes = dictfetchall(cursor)
    return render(request, 'compras/solicitudes_lista.html', {'solicitudes': solicitudes})


@login_required
@permission_required('compras.ver_reportes')
def cotizaciones(request):
    """Listado de Cotizaciones (RFQs)."""
    ent_id = request.user_data['enterprise_id']
    estado = request.GET.get('estado', '')
    with get_db_cursor() as cursor:
        if estado:
            cursor.execute("""
                SELECT cmp_cotizaciones.*, erp_terceros.nombre as razon_social,
                       (SELECT COUNT(*) FROM cmp_items_cotizacion
                        WHERE cotizacion_id = cmp_cotizaciones.id AND enterprise_id = %s) as items_cnt
                FROM cmp_cotizaciones
                JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
                WHERE cmp_cotizaciones.enterprise_id = %s AND cmp_cotizaciones.estado = %s
                ORDER BY cmp_cotizaciones.fecha_envio DESC
            """, (ent_id, ent_id, estado))
        else:
            cursor.execute("""
                SELECT cmp_cotizaciones.*, erp_terceros.nombre as razon_social,
                       (SELECT COUNT(*) FROM cmp_items_cotizacion
                        WHERE cotizacion_id = cmp_cotizaciones.id AND enterprise_id = %s) as items_cnt
                FROM cmp_cotizaciones
                JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
                WHERE cmp_cotizaciones.enterprise_id = %s
                ORDER BY cmp_cotizaciones.fecha_envio DESC
            """, (ent_id, ent_id))
        rows = dictfetchall(cursor)
    return render(request, 'compras/cotizaciones_lista.html', {'cotizaciones': rows, 'estado_filtro': estado})


@login_required
@permission_required('compras.ver_reportes')
def cotizacion_detalle(request, id):
    """Detalle de Cotización y carga manual de precios."""
    from django.contrib import messages
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        if request.method == 'POST':
            for key, value in request.POST.items():
                if key.startswith('cant_'):
                    item_id = key.split('_')[1]
                    price = request.POST.get(f'price_{item_id}', 0)
                    cursor.execute("""
                        UPDATE cmp_items_cotizacion
                        SET cantidad_ofrecida = %s, precio_cotizado = %s
                        WHERE id = %s AND cotizacion_id = %s AND enterprise_id = %s
                    """, (float(value) if value else 0, float(price) if price else 0, item_id, id, ent_id))
            cursor.execute(
                "UPDATE cmp_cotizaciones SET estado = 'RESPONDIDA' WHERE id = %s AND enterprise_id = %s AND estado = 'ENVIADA'",
                (id, ent_id)
            )
            messages.success(request, 'Cotización actualizada manualmente.')
            return redirect('compras:cotizacion_detalle', id=id)

        cursor.execute("""
            SELECT cmp_cotizaciones.*, erp_terceros.nombre as razon_social,
                   erp_terceros.email as proveedor_email, erp_terceros.telefono as proveedor_tel
            FROM cmp_cotizaciones
            JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
            WHERE cmp_cotizaciones.id = %s AND cmp_cotizaciones.enterprise_id = %s
        """, (id, ent_id))
        cot = dictfetchone(cursor)
        if not cot:
            return redirect('compras:cotizaciones')

        cursor.execute("""
            SELECT cmp_items_cotizacion.*, stk_articulos.nombre as articulo_nombre,
                   stk_articulos.codigo as articulo_codigo
            FROM cmp_items_cotizacion
            JOIN stk_articulos ON cmp_items_cotizacion.articulo_id = stk_articulos.id
            WHERE cmp_items_cotizacion.cotizacion_id = %s AND cmp_items_cotizacion.enterprise_id = %s
        """, (id, ent_id))
        items = dictfetchall(cursor)

    return render(request, 'compras/cotizacion_detalle.html', {'cot': cot, 'items': items})


@login_required
@permission_required('view_proveedores')
def comprobantes(request):
    """Listado de comprobantes de compra (facturas recibidas)."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT erp_comprobantes.*, erp_terceros.nombre as proveedor_nombre,
                   sys_tipos_comprobante.letra, sys_tipos_comprobante.descripcion as tipo_nombre
            FROM erp_comprobantes
            JOIN erp_terceros ON erp_comprobantes.tercero_id = erp_terceros.id
            JOIN sys_tipos_comprobante ON erp_comprobantes.tipo_comprobante = sys_tipos_comprobante.codigo
            WHERE erp_comprobantes.enterprise_id = %s AND erp_comprobantes.tipo_operacion = 'COMPRA'
            ORDER BY erp_comprobantes.fecha_emision DESC, erp_comprobantes.numero DESC
        """, (ent_id,))
        lista = dictfetchall(cursor)
    return render(request, 'compras/comprobantes.html', {'comprobantes': lista})


@login_required
def alertas_detalle(request):
    """Listado de alertas de material no provisto."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_items_cotizacion.*, stk_articulos.nombre as articulo, stk_articulos.codigo,
                   cmp_cotizaciones.fecha_envio as fecha, erp_terceros.nombre as razon_social,
                   cmp_cotizaciones.id as cotizacion_id
            FROM cmp_items_cotizacion
            JOIN cmp_cotizaciones ON cmp_items_cotizacion.cotizacion_id = cmp_cotizaciones.id
            JOIN stk_articulos ON cmp_items_cotizacion.articulo_id = stk_articulos.id
            JOIN erp_terceros ON cmp_cotizaciones.proveedor_id = erp_terceros.id
            WHERE cmp_cotizaciones.estado IN ('RECIBIDA_TOTAL', 'CONFIRMADA')
              AND (cmp_items_cotizacion.cantidad_ofrecida IS NULL OR cmp_items_cotizacion.cantidad_ofrecida = 0)
              AND cmp_cotizaciones.enterprise_id = %s AND cmp_items_cotizacion.enterprise_id = %s
            ORDER BY cmp_cotizaciones.fecha_envio DESC
        """, (ent_id, ent_id))
        alertas = dictfetchall(cursor)
    return render(request, 'compras/alertas_detalle.html', {'alertas': alertas})


# Stubs para vistas más complejas (se completarán en siguientes sprints)
@login_required
def ordenes(request):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, erp_terceros.nombre as proveedor_nombre, sys_users.username
            FROM cmp_ordenes_compra
            JOIN erp_terceros ON cmp_ordenes_compra.proveedor_id = erp_terceros.id
            LEFT JOIN sys_users ON cmp_ordenes_compra.user_id = sys_users.id
            WHERE cmp_ordenes_compra.enterprise_id = %s
            ORDER BY cmp_ordenes_compra.fecha DESC LIMIT 100
        """, (ent_id,))
        ordenes = dictfetchall(cursor)
    return render(request, 'compras/ordenes_lista.html', {'ordenes': ordenes})


@login_required
def orden_nueva(request):
    return render(request, 'compras/orden_nueva.html')


@login_required
def orden_detalle(request, id):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM cmp_ordenes_compra WHERE id = %s AND enterprise_id = %s", (id, ent_id))
        orden = dictfetchone(cursor)
    return render(request, 'compras/ordenes_lista.html', {'orden': orden})


@login_required
@permission_required('compras.gestionar_reposicion')
def aprobaciones(request):
    """Bandeja de órdenes pendientes de aprobación."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, erp_terceros.nombre as proveedor_nombre,
                   sys_users.username as creador_nombre
            FROM cmp_ordenes_compra
            JOIN erp_terceros ON cmp_ordenes_compra.proveedor_id = erp_terceros.id
            JOIN sys_users ON cmp_ordenes_compra.user_id = sys_users.id
            WHERE cmp_ordenes_compra.enterprise_id = %s 
              AND cmp_ordenes_compra.estado IN ('PENDIENTE_APROBACION_COMPRAS', 'ENVIADA_TESORERIA')
            ORDER BY cmp_ordenes_compra.fecha DESC
        """, (ent_id,))
        ordenes = dictfetchall(cursor)
    return render(request, 'compras/aprobaciones.html', {'ordenes': ordenes})


@login_required
def aprobar_po_detalle(request, id):
    """Detalle de una orden para su aprobación o rechazo."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, erp_terceros.nombre as proveedor_nombre,
                   erp_terceros.cuit as proveedor_cuit
            FROM cmp_ordenes_compra
            JOIN erp_terceros ON cmp_ordenes_compra.proveedor_id = erp_terceros.id
            WHERE cmp_ordenes_compra.id = %s AND cmp_ordenes_compra.enterprise_id = %s
        """, (id, ent_id))
        orden = dictfetchone(cursor)
        
        if not orden:
            return redirect('compras:aprobaciones')
            
        # Obtener ítems
        cursor.execute("""
            SELECT cmp_detalles_orden_compra.*, stk_articulos.nombre as articulo_nombre,
                   stk_articulos.codigo as articulo_codigo
            FROM cmp_detalles_orden_compra
            JOIN stk_articulos ON cmp_detalles_orden_compra.articulo_id = stk_articulos.id
            WHERE cmp_detalles_orden_compra.orden_id = %s
        """, (id,))
        items = dictfetchall(cursor)
        
    return render(request, 'compras/aprobar_po_detalle.html', {'orden': orden, 'items': items})


@login_required
def ordenes_pago(request):
    return render(request, 'compras/ordenes_pago_lista.html')


@login_required
def pagar(request):
    return render(request, 'compras/pagar.html')


@login_required
def facturar(request):
    return render(request, 'compras/facturar.html')


@login_required
def recepcion_ciega_list(request):
    return render(request, 'compras/recepcion_ciega_list.html')


# ── APIs ───────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def api_reposicion_generar_np(request):
    """Crea una Nota de Pedido a partir de una sugerencia del dashboard."""
    data = json.loads(request.body)
    articulo_id = data.get('articulo_id')
    cantidad = data.get('cantidad')
    if not articulo_id or not cantidad:
        return JsonResponse({'success': False, 'message': 'Datos incompletos.'}, status=400)

    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO cmp_solicitudes_reposicion
                (enterprise_id, fecha, solicitante_id, estado, prioridad, observaciones)
            VALUES (%s, NOW(), %s, 'PENDIENTE_AJUSTE', 2, 'Generado desde Dashboard de Reposición')
        """, (ent_id, uid))
        cursor.execute("SELECT LAST_INSERT_ID() as last_id")
        solicitud_id = dictfetchone(cursor)['last_id']

        cursor.execute("""
            INSERT INTO cmp_detalles_solicitud
                (enterprise_id, solicitud_id, articulo_id, cantidad_sugerida, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (ent_id, solicitud_id, articulo_id, cantidad, uid))

    return JsonResponse({'success': True, 'message': f'Nota de Pedido #{solicitud_id} creada.', 'solicitud_id': solicitud_id})


@login_required
@require_POST
def api_reposicion_generar_cotizacion(request):
    """Genera un RFQ con varios artículos de un proveedor."""
    data = json.loads(request.body)
    proveedor_id = data.get('proveedor_id')
    items = data.get('items', [])
    if not proveedor_id or not items:
        return JsonResponse({'success': False, 'message': 'Faltan datos.'}, status=400)

    import datetime
    fecha_vencimiento = data.get('fecha_vencimiento') or (
        datetime.datetime.now() + datetime.timedelta(days=7)
    ).strftime('%Y-%m-%d')

    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    with get_db_cursor() as cursor:
        cursor.execute("SELECT nombre, email FROM erp_terceros WHERE id = %s", (proveedor_id,))
        prov = dictfetchone(cursor)
        if not prov or not prov.get('email'):
            return JsonResponse({
                'success': False, 'error_type': 'missing_email',
                'message': 'Complete la dirección de correo del proveedor.',
                'nombre_proveedor': prov['nombre'] if prov else ''
            }, status=400)

        cursor.execute("""
            INSERT INTO cmp_cotizaciones
                (enterprise_id, proveedor_id, fecha_envio, fecha_vencimiento, estado, user_id)
            VALUES (%s, %s, NOW(), %s, 'ENVIADA', %s)
        """, (ent_id, proveedor_id, fecha_vencimiento, uid))
        cursor.execute("SELECT LAST_INSERT_ID() as last_id")
        cot_id = dictfetchone(cursor)['last_id']

        for it in items:
            cursor.execute("""
                INSERT INTO cmp_items_cotizacion
                    (enterprise_id, cotizacion_id, articulo_id, cantidad, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (ent_id, cot_id, it['articulo_id'], it['cantidad'], uid))

    return JsonResponse({'success': True, 'message': f'Cotización #{cot_id} generada.', 'cot_id': cot_id})


@login_required
@require_POST
def api_reposicion_rechazar(request):
    """Registra el rechazo de una sugerencia de reposición."""
    data = json.loads(request.body)
    if not data.get('articulo_id') or not data.get('motivo'):
        return JsonResponse({'success': False, 'message': 'Faltan datos.'}, status=400)
    return JsonResponse({'success': True, 'message': 'Rechazo registrado.'})


@login_required
@require_POST
def api_solicitud_cotizar(request, id):
    """Convierte una NP en un RFQ para un proveedor."""
    data = json.loads(request.body)
    proveedor_id = data.get('proveedor_id')
    fecha_vencimiento = data.get('fecha_vencimiento')
    if not proveedor_id or not fecha_vencimiento:
        return JsonResponse({'success': False, 'message': 'Proveedor y fecha son requeridos.'}, status=400)

    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM cmp_detalles_solicitud WHERE solicitud_id = %s AND enterprise_id = %s",
            (id, ent_id)
        )
        items = dictfetchall(cursor)
        if not items:
            return JsonResponse({'success': False, 'message': 'La solicitud no tiene ítems.'}, status=400)

        cursor.execute("""
            INSERT INTO cmp_cotizaciones
                (enterprise_id, proveedor_id, fecha_envio, fecha_vencimiento, estado, user_id)
            VALUES (%s, %s, NOW(), %s, 'ENVIADA', %s)
        """, (ent_id, proveedor_id, fecha_vencimiento, uid))
        cursor.execute("SELECT LAST_INSERT_ID() as last_id")
        cot_id = dictfetchone(cursor)['last_id']

        for it in items:
            cursor.execute("""
                INSERT INTO cmp_items_cotizacion
                    (enterprise_id, cotizacion_id, articulo_id, cantidad, user_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (ent_id, cot_id, it['articulo_id'], it['cantidad_sugerida'], uid))

        cursor.execute(
            "UPDATE cmp_solicitudes_reposicion SET estado = 'COTIZANDO' WHERE id = %s",
            (id,)
        )

    return JsonResponse({'success': True, 'message': f'Cotización #{cot_id} generada desde NP #{id}.', 'cot_id': cot_id})


@login_required
@require_POST
def api_proveedor_audit(request, id):
    """Stub - Auditoría AFIP del proveedor (pendiente integración AfipService)."""
    return JsonResponse({'success': True, 'status': 'PENDING', 'message': 'Auditoría en desarrollo.'})


@login_required
def eliminar_detalle(request, tabla, item_id, id):
    tablas_permitidas = ['erp_direcciones', 'erp_contactos', 'erp_datos_fiscales', 'erp_terceros_cm05']
    if tabla not in tablas_permitidas:
        from django.contrib import messages
        messages.error(request, "Operación no permitida.")
        return redirect('compras:perfil_proveedor', id=id)

    ent_id = request.user_data['enterprise_id']
    from django.contrib import messages

    try:
        with get_db_cursor() as cursor:
            cursor.execute(f"DELETE FROM {tabla} WHERE id = %s AND tercero_id = %s AND enterprise_id = %s", (item_id, id, ent_id))
        messages.info(request, "Registro eliminado.")
    except Exception as e:
        messages.error(request, f"Error al eliminar registro: {str(e)}")
        
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def toggle_convenio(request, id):
    es_convenio = 1 if 'es_convenio' in request.POST else 0
    with get_db_cursor() as cursor:
        cursor.execute("UPDATE erp_terceros SET es_convenio_multilateral = %s WHERE id = %s AND enterprise_id = %s", (es_convenio, id, request.user_data['enterprise_id']))
    from django.contrib import messages
    messages.success(request, "Configuración de convenio multilateral actualizada.")
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def agregar_cm05(request, id):
    jurisdiccion = request.POST.get('jurisdiccion_code')
    periodo_anio = request.POST.get('periodo_anio')
    coeficiente = request.POST.get('coeficiente')

    try:
        from apps.ventas.services import CM05Service
        CM05Service.upsert_coeficiente(request.user_data['enterprise_id'], id, jurisdiccion, periodo_anio, coeficiente, request.user_data['id'])
        from django.contrib import messages
        messages.success(request, "Coeficiente guardado correctamente.")
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f"Error al guardar coeficiente: {e}")
    
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def upload_cm05(request, id):
    if 'archivo_cm05' not in request.FILES:
        from django.contrib import messages
        messages.warning(request, 'No se seleccionó ningún archivo.')
        return redirect('compras:perfil_proveedor', id=id)
        
    file = request.FILES['archivo_cm05']
    if file.name == '':
        from django.contrib import messages
        messages.warning(request, 'No se seleccionó ningún archivo.')
        return redirect('compras:perfil_proveedor', id=id)
        
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
        
    return redirect('compras:perfil_proveedor', id=id)

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
    ent_id = request.user_data['enterprise_id']
    
    from django.contrib import messages
    try:
        with get_db_cursor() as cursor:
            if item_id:
                cursor.execute("""
                    UPDATE erp_direcciones 
                    SET etiqueta=%s, calle=%s, numero=%s, piso=%s, depto=%s, localidad=%s, provincia=%s, cod_postal=%s, es_fiscal=%s, es_entrega=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (etiqueta, calle, numero, piso, depto, localidad, provincia, cp, es_fiscal, es_entrega, item_id, id, ent_id))
                messages.success(request, "Dirección actualizada.")
            else:
                cursor.execute("""
                    INSERT INTO erp_direcciones (enterprise_id, tercero_id, etiqueta, calle, numero, piso, depto, localidad, provincia, cod_postal, es_fiscal, es_entrega)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (ent_id, id, etiqueta, calle, numero, piso, depto, localidad, provincia, cp, es_fiscal, es_entrega))
                messages.success(request, "Dirección agregada.")
    except Exception as e:
        messages.error(request, f"Error al guardar dirección: {str(e)}")
        
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def agregar_contacto(request, id):
    item_id = request.POST.get('item_id')
    nombre = request.POST.get('nombre')
    puesto = request.POST.get('puesto')
    tipo = request.POST.get('tipo_contacto')
    telefono = request.POST.get('telefono')
    email = request.POST.get('email')
    es_receptor = 1 if 'es_receptor' in request.POST else 0
    ent_id = request.user_data['enterprise_id']

    from django.contrib import messages
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Resolver puesto a ID si existe
            cursor.execute("SELECT id FROM erp_puestos WHERE nombre = %s AND enterprise_id = %s LIMIT 1", (puesto, ent_id))
            puesto_row = dictfetchone(cursor)
            puesto_id = puesto_row['id'] if puesto_row else None

            if item_id:
                cursor.execute("""
                    UPDATE erp_contactos SET nombre=%s, puesto_id=%s, tipo_contacto=%s, telefono=%s, email=%s, es_receptor=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (nombre, puesto_id, tipo, telefono, email, es_receptor, item_id, id, ent_id))
                messages.success(request, "Contacto actualizado.")
            else:
                cursor.execute("""
                    INSERT INTO erp_contactos (enterprise_id, tercero_id, nombre, puesto_id, tipo_contacto, telefono, email, es_receptor)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (ent_id, id, nombre, puesto_id, tipo, telefono, email, es_receptor))
                messages.success(request, "Contacto agregado.")
    except Exception as e:
        messages.error(request, f"Error al guardar contacto: {str(e)}")
        
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def agregar_fiscal(request, id):
    item_id = request.POST.get('item_id')
    impuesto = request.POST.get('impuesto')
    jurisdiccion = request.POST.get('jurisdiccion')
    condicion = request.POST.get('condicion')
    alicuota_raw = request.POST.get('alicuota', 0)
    inscripcion = request.POST.get('numero_inscripcion', '')
    ent_id = request.user_data['enterprise_id']
    
    try: alicuota = float(alicuota_raw)
    except: alicuota = 0

    from django.contrib import messages
    try:
        with get_db_cursor() as cursor:
            if item_id:
                cursor.execute("""
                    UPDATE erp_datos_fiscales SET impuesto=%s, jurisdiccion=%s, condicion=%s, numero_inscripcion=%s, alicuota=%s
                    WHERE id=%s AND tercero_id=%s AND enterprise_id=%s
                """, (impuesto, jurisdiccion, condicion, inscripcion, alicuota, item_id, id, ent_id))
                messages.success(request, "Dato fiscal actualizado.")
            else:
                cursor.execute("""
                    INSERT INTO erp_datos_fiscales (enterprise_id, tercero_id, impuesto, jurisdiccion, condicion, numero_inscripcion, alicuota)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (ent_id, id, impuesto, jurisdiccion, condicion, inscripcion, alicuota))
                messages.success(request, "Dato fiscal agregado.")
    except Exception as e:
        messages.error(request, f"Error al guardar dato fiscal: {str(e)}")
        
    return redirect('compras:perfil_proveedor', id=id)

@login_required
def autorizar_orden(request, id):
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']
    from django.contrib import messages

    with get_db_cursor() as cursor:
        cursor.execute("SELECT estado FROM cmp_ordenes_compra WHERE id = %s AND enterprise_id = %s", (id, ent_id))
        row = dictfetchone(cursor)
        if not row:
            messages.error(request, "Orden no encontrada.")
            return redirect('compras:ordenes')

        current_state = row['estado']
        new_state = None

        if current_state == 'BORRADOR':
            new_state = 'PENDIENTE_APROBACION_COMPRAS'
        elif current_state == 'PENDIENTE_APROBACION_COMPRAS':
            new_state = 'APROBADA_COMPRAS'
        elif current_state == 'APROBADA_COMPRAS':
            new_state = 'ENVIADA_TESORERIA'
        elif current_state == 'ENVIADA_TESORERIA':
            new_state = 'APROBADA_TESORERIA'
        elif current_state == 'APROBADA_TESORERIA':
            new_state = 'CONFIRMADA'

        if new_state:
            cursor.execute("""
                UPDATE cmp_ordenes_compra 
                SET estado = %s, user_id_update = %s, updated_at = NOW()
                WHERE id = %s AND enterprise_id = %s
            """, (new_state, uid, id, ent_id))
            messages.success(request, f"Orden #{id} movida a estado {new_state}.")
        else:
            messages.warning(request, "La orden ya está en su estado final o requiere otra acción.")

    return redirect('compras:ordenes')

@login_required
def rechazar_orden(request, id):
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']
    motivo = request.POST.get('motivo', 'Rechazado por usuario.')
    from django.contrib import messages

    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE cmp_ordenes_compra 
            SET estado = 'RECHAZADA_COMPRAS', observaciones_rechazo = %s, user_id_update = %s
            WHERE id = %s AND enterprise_id = %s
        """, (motivo, uid, id, ent_id))
        messages.warning(request, f"Orden #{id} rechazada.")

    return redirect('compras:ordenes')

@login_required
def pdf_orden(request, id):
    # TODO: Integrar con servicio de PDF. Por ahora redirigir.
    return redirect('compras:orden_detalle', id=id)

@login_required
def aprobar_cotizacion(request, id):
    ent_id = request.user_data['enterprise_id']
    from django.contrib import messages

    with get_db_cursor() as cursor:
        cursor.execute("UPDATE cmp_cotizaciones SET estado = 'GANADORA' WHERE id = %s AND enterprise_id = %s", (id, ent_id))
        messages.success(request, f"Cotización #{id} marcada como GANADORA.")
    
    return redirect('compras:cotizaciones')
