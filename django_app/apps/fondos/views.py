from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.core.decorators import login_required, permission_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone


@login_required
def dashboard(request):
    """Dashboard de Fondos / Tesorería."""
    ent_id = request.user_data['enterprise_id']
    kpi = {'cajas': 0, 'bancos': 0, 'aprobaciones_pendientes': 0, 'desembolsos_proximos': 0}

    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as c FROM erp_cuentas_fondos WHERE enterprise_id = %s", (ent_id,))
        row = dictfetchone(cursor)
        kpi['cajas'] = row['c'] if row else 0

        cursor.execute("SELECT COUNT(*) as c FROM fin_bancos WHERE (enterprise_id = %s OR enterprise_id = 0) AND activo = 1", (ent_id,))
        row = dictfetchone(cursor)
        kpi['bancos'] = row['c'] if row else 0

        cursor.execute("SELECT COUNT(*) as c FROM cmp_ordenes_compra WHERE estado = 'ENVIADA_TESORERIA' AND enterprise_id = %s", (ent_id,))
        row = dictfetchone(cursor)
        kpi['aprobaciones_pendientes'] = row['c'] if row else 0

        cursor.execute("""
            SELECT COUNT(*) as c FROM cmp_ordenes_compra
            WHERE estado = 'APROBADA_TESORERIA' AND enterprise_id = %s
              AND fecha_pago_estimada BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """, (ent_id,))
        row = dictfetchone(cursor)
        kpi['desembolsos_proximos'] = row['c'] if row else 0

    return render(request, 'fondos/dashboard.html', {'kpi': kpi})


@login_required
def cajas(request):
    """Maestro de cajas y cuentas de fondos."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM erp_cuentas_fondos WHERE enterprise_id = %s ORDER BY nombre", (ent_id,))
        cajas = dictfetchall(cursor)
    return render(request, 'fondos/cajas.html', {'cajas': cajas})


@login_required
def medios_pago(request):
    """ABM de medios de pago (efectivo, transferencia, cheque, etc.)."""
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with get_db_cursor() as cursor:
                if action == 'create':
                    cursor.execute("""
                        INSERT INTO fin_medios_pago
                            (enterprise_id, nombre, tipo, cuenta_contable_id, recargo_pct, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        ent_id,
                        request.POST['nombre'],
                        request.POST['tipo'],
                        request.POST.get('cuenta_contable_id') or None,
                        request.POST.get('recargo_pct', 0),
                        uid,
                    ))
                    messages.success(request, 'Medio de pago creado correctamente.')

                elif action == 'edit':
                    cursor.execute("""
                        UPDATE fin_medios_pago
                        SET nombre=%s, tipo=%s, cuenta_contable_id=%s, recargo_pct=%s, activo=%s, user_id_update=%s
                        WHERE id=%s AND enterprise_id=%s
                    """, (
                        request.POST['nombre'],
                        request.POST['tipo'],
                        request.POST.get('cuenta_contable_id') or None,
                        request.POST.get('recargo_pct', 0),
                        1 if 'activo' in request.POST else 0,
                        uid,
                        request.POST['id'],
                        ent_id,
                    ))
                    messages.success(request, 'Medio de pago actualizado.')

                elif action == 'delete':
                    cursor.execute("DELETE FROM fin_medios_pago WHERE id=%s AND enterprise_id=%s",
                                   (request.POST['id'], ent_id))
                    messages.warning(request, 'Medio de pago eliminado.')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('fondos:medios_pago')

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fin_medios_pago WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY nombre",
            (ent_id,)
        )
        medios = dictfetchall(cursor)
        cursor.execute(
            "SELECT id, codigo, nombre FROM cont_plan_cuentas WHERE tipo = 'ACTIVO' AND enterprise_id = %s ORDER BY codigo",
            (ent_id,)
        )
        cuentas = dictfetchall(cursor)

    return render(request, 'fondos/medios_pago.html', {'medios': medios, 'cuentas': cuentas})


@login_required
def condiciones_pago(request):
    """ABM de condiciones de pago simples (contado, 30 días, etc.)."""
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with get_db_cursor() as cursor:
                if action == 'create':
                    cursor.execute("""
                        INSERT INTO fin_condiciones_pago
                            (enterprise_id, nombre, dias_vencimiento, descuento_pct, recargo_pct, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        ent_id,
                        request.POST['nombre'],
                        request.POST.get('dias_vencimiento', 0),
                        request.POST.get('descuento_pct', 0),
                        request.POST.get('recargo_pct', 0),
                        uid,
                    ))
                    messages.success(request, 'Condición de pago creada.')

                elif action == 'edit':
                    cursor.execute("""
                        UPDATE fin_condiciones_pago
                        SET nombre=%s, dias_vencimiento=%s, descuento_pct=%s, recargo_pct=%s, activo=%s, user_id_update=%s
                        WHERE id=%s AND enterprise_id=%s
                    """, (
                        request.POST['nombre'],
                        request.POST.get('dias_vencimiento', 0),
                        request.POST.get('descuento_pct', 0),
                        request.POST.get('recargo_pct', 0),
                        1 if 'activo' in request.POST else 0,
                        uid, request.POST['id'], ent_id,
                    ))
                    messages.success(request, 'Condición de pago actualizada.')

                elif action == 'delete':
                    cursor.execute("DELETE FROM fin_condiciones_pago WHERE id=%s AND enterprise_id=%s",
                                   (request.POST['id'], ent_id))
                    messages.warning(request, 'Condición eliminada.')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('fondos:condiciones_pago')

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fin_condiciones_pago WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY dias_vencimiento, nombre",
            (ent_id,)
        )
        condiciones = dictfetchall(cursor)

    return render(request, 'fondos/condiciones_pago.html', {'condiciones': condiciones})


@login_required
def condiciones_mixtas(request):
    """ABM de condiciones de pago mixtas (ej: 50% contado + 50% a 30 días)."""
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with get_db_cursor() as cursor:
                if action in ('create', 'edit'):
                    nombre = request.POST['nombre']
                    descripcion = request.POST.get('descripcion', '')
                    activo = 1 if 'activo' in request.POST else 0
                    condiciones_ids = request.POST.getlist('condicion_pago_id[]')
                    porcentajes = request.POST.getlist('porcentaje[]')
                    descuentos = request.POST.getlist('descuento_pct_det[]')
                    recargos = request.POST.getlist('recargo_pct_det[]')

                    if action == 'create':
                        cursor.execute("""
                            INSERT INTO fin_condiciones_pago_mixtas
                                (enterprise_id, nombre, descripcion, user_id)
                            VALUES (%s, %s, %s, %s)
                        """, (ent_id, nombre, descripcion, uid))
                        cursor.execute("SELECT LAST_INSERT_ID() as lid")
                        mixta_id = dictfetchone(cursor)['lid']
                    else:
                        mixta_id = request.POST['id']
                        cursor.execute("""
                            UPDATE fin_condiciones_pago_mixtas
                            SET nombre=%s, descripcion=%s, activo=%s, user_id_update=%s
                            WHERE id=%s AND enterprise_id=%s
                        """, (nombre, descripcion, activo, uid, mixta_id, ent_id))
                        cursor.execute(
                            "DELETE FROM fin_condiciones_pago_mixtas_detalle WHERE mixta_id=%s AND enterprise_id=%s",
                            (mixta_id, ent_id)
                        )

                    for cid, pct, desc, rec in zip(condiciones_ids, porcentajes, descuentos, recargos):
                        if cid and pct:
                            cursor.execute("""
                                INSERT INTO fin_condiciones_pago_mixtas_detalle
                                    (enterprise_id, mixta_id, condicion_pago_id, porcentaje, descuento_pct, recargo_pct, user_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (ent_id, mixta_id, cid, pct, desc or 0, rec or 0, uid))
                    messages.success(request, 'Condición mixta guardada.')

                elif action == 'delete':
                    cursor.execute("DELETE FROM fin_condiciones_pago_mixtas WHERE id=%s AND enterprise_id=%s",
                                   (request.POST['id'], ent_id))
                    messages.warning(request, 'Condición mixta eliminada.')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('fondos:condiciones_mixtas')

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fin_condiciones_pago_mixtas WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY nombre",
            (ent_id,)
        )
        mixtas = dictfetchall(cursor)
        for m in mixtas:
            cursor.execute("""
                SELECT fin_condiciones_pago_mixtas_detalle.*, fin_condiciones_pago.nombre as condicion_nombre
                FROM fin_condiciones_pago_mixtas_detalle
                JOIN fin_condiciones_pago ON fin_condiciones_pago_mixtas_detalle.condicion_pago_id = fin_condiciones_pago.id
                WHERE fin_condiciones_pago_mixtas_detalle.mixta_id = %s
                  AND (fin_condiciones_pago_mixtas_detalle.enterprise_id = %s OR fin_condiciones_pago_mixtas_detalle.enterprise_id = 0)
            """, (m['id'], ent_id))
            m['detalles'] = dictfetchall(cursor)

        cursor.execute(
            "SELECT * FROM fin_condiciones_pago WHERE (enterprise_id = %s OR enterprise_id = 0) AND activo = 1 ORDER BY nombre",
            (ent_id,)
        )
        condiciones_simples = dictfetchall(cursor)

    return render(request, 'fondos/condiciones_mixtas.html', {
        'mixtas': mixtas,
        'condiciones_simples': condiciones_simples,
    })


@login_required
def impuestos(request):
    """ABM de impuestos del sistema (IVA, IIBB, Retenciones, etc.)."""
    ent_id = request.user_data['enterprise_id']

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with get_db_cursor() as cursor:
                if action == 'create':
                    cursor.execute("""
                        INSERT INTO sys_impuestos (enterprise_id, nombre, descripcion)
                        VALUES (%s, %s, %s)
                    """, (ent_id, request.POST['nombre'], request.POST.get('descripcion', '')))
                    messages.success(request, 'Impuesto creado.')

                elif action == 'edit':
                    cursor.execute("""
                        UPDATE sys_impuestos
                        SET nombre=%s, descripcion=%s, activo=%s
                        WHERE id=%s AND (enterprise_id=%s OR enterprise_id=0)
                    """, (
                        request.POST['nombre'],
                        request.POST.get('descripcion', ''),
                        1 if 'activo' in request.POST else 0,
                        request.POST['id'], ent_id,
                    ))
                    messages.success(request, 'Impuesto actualizado.')

                elif action == 'delete':
                    cursor.execute("DELETE FROM sys_impuestos WHERE id=%s AND enterprise_id=%s",
                                   (request.POST['id'], ent_id))
                    messages.warning(request, 'Impuesto eliminado.')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('fondos:impuestos')

    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM sys_impuestos WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY nombre",
            (ent_id,)
        )
        impuestos_lista = dictfetchall(cursor)

    return render(request, 'fondos/impuestos.html', {'impuestos': impuestos_lista})


@login_required
def bancos(request):
    """ABM de entidades bancarias (CBU y CVU). Integra datos BCRA."""
    ent_id = request.user_data['enterprise_id']

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with get_db_cursor() as cursor:
                if action == 'create':
                    cursor.execute("""
                        INSERT INTO fin_bancos
                            (enterprise_id, tipo_entidad, numero_cuenta, nombre, tipo,
                             cuit, bic, telefono, web, direccion, origen, activo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'MANUAL', 1)
                    """, (
                        ent_id,
                        request.POST.get('tipo_entidad', 'CBU'),
                        request.POST.get('numero_cuenta') or None,
                        request.POST['nombre'],
                        request.POST.get('tipo', ''),
                        request.POST.get('cuit') or None,
                        request.POST.get('bic') or None,
                        request.POST.get('telefono') or None,
                        request.POST.get('web') or None,
                        request.POST.get('direccion') or None,
                    ))
                    messages.success(request, f"Banco \"{request.POST['nombre']}\" creado correctamente.")

                elif action == 'edit':
                    bid = request.POST['id']
                    cursor.execute("""
                        UPDATE fin_bancos
                        SET nombre=%s, tipo_entidad=%s, tipo=%s, cuit=%s, bic=%s,
                            telefono=%s, web=%s, direccion=%s, activo=%s,
                            numero_cuenta=COALESCE(%s, numero_cuenta)
                        WHERE id=%s AND (enterprise_id=%s OR enterprise_id=0)
                    """, (
                        request.POST['nombre'],
                        request.POST.get('tipo_entidad', 'CBU'),
                        request.POST.get('tipo', ''),
                        request.POST.get('cuit') or None,
                        request.POST.get('bic') or None,
                        request.POST.get('telefono') or None,
                        request.POST.get('web') or None,
                        request.POST.get('direccion') or None,
                        1 if 'activo' in request.POST else 0,
                        request.POST.get('numero_cuenta') or None,
                        bid, ent_id,
                    ))
                    messages.success(request, 'Banco actualizado.')

                elif action == 'delete':
                    bid = request.POST['id']
                    cursor.execute("SELECT enterprise_id, origen FROM fin_bancos WHERE id=%s", (bid,))
                    row = dictfetchone(cursor)
                    if row:
                        if row['enterprise_id'] == 0 or row.get('origen') == 'BCRA':
                            cursor.execute("UPDATE fin_bancos SET activo=0 WHERE id=%s", (bid,))
                            messages.warning(request, 'Banco desactivado (dato maestro BCRA).')
                        else:
                            cursor.execute("DELETE FROM fin_bancos WHERE id=%s AND enterprise_id=%s", (bid, ent_id))
                            messages.warning(request, 'Banco eliminado.')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('fondos:bancos')

    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT fin_bancos.*,
                   cont_plan_cuentas.codigo AS cuenta_codigo,
                   cont_plan_cuentas.nombre AS cuenta_nombre
            FROM fin_bancos
            LEFT JOIN cont_plan_cuentas ON fin_bancos.cuenta_contable_id = cont_plan_cuentas.id
            WHERE (fin_bancos.enterprise_id = %s OR fin_bancos.enterprise_id = 0)
            ORDER BY fin_bancos.tipo_entidad, fin_bancos.nombre ASC
        """, (ent_id,))
        bancos_lista = dictfetchall(cursor)

    total = len(bancos_lista)
    activos = sum(1 for b in bancos_lista if b.get('activo'))
    cbu_count = sum(1 for b in bancos_lista if b.get('tipo_entidad') == 'CBU')
    cvu_count = sum(1 for b in bancos_lista if b.get('tipo_entidad') == 'CVU')
    bcra_count = sum(1 for b in bancos_lista if b.get('origen') == 'BCRA')

    return render(request, 'fondos/bancos.html', {
        'bancos': bancos_lista,
        'total': total, 'activos': activos,
        'cbu_count': cbu_count, 'cvu_count': cvu_count, 'bcra_count': bcra_count,
    })


@login_required
@require_POST
def bancos_sincronizar_bcra(request):
    """Sincroniza entidades CBU desde la API del BCRA (stub — requiere BCRAService)."""
    messages.info(request, 'Sincronización BCRA: servicio se integrará en Sprint 2.')
    return redirect('fondos:bancos')


@login_required
@require_POST
def bancos_sincronizar_billeteras(request):
    """Sincroniza billeteras CVU desde la API del BCRA (stub)."""
    messages.info(request, 'Sincronización CVU: servicio se integrará en Sprint 2.')
    return redirect('fondos:bancos')


@login_required
def bancos_api_buscar(request):
    """API JSON para búsqueda de bancos (Select2 / autocomplete)."""
    q = request.GET.get('q', '').strip()
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, nombre, tipo, cuit, bic
            FROM fin_bancos
            WHERE (enterprise_id = %s OR enterprise_id = 0)
              AND activo = 1 AND nombre LIKE %s
            ORDER BY nombre ASC LIMIT 30
        """, (ent_id, f'%{q}%'))
        results = dictfetchall(cursor)
    return JsonResponse(results, safe=False)


@login_required
def configuracion_global(request):
    """Vista unificada de todos los parámetros financieros globales."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fin_medios_pago WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY nombre", (ent_id,)
        )
        medios = dictfetchall(cursor)
        cursor.execute(
            "SELECT * FROM fin_condiciones_pago WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY dias_vencimiento, nombre",
            (ent_id,)
        )
        condiciones = dictfetchall(cursor)
        cursor.execute(
            "SELECT * FROM fin_condiciones_pago_mixtas WHERE (enterprise_id = %s OR enterprise_id = 0) ORDER BY nombre",
            (ent_id,)
        )
        mixtas = dictfetchall(cursor)
        cursor.execute(
            "SELECT * FROM sys_impuestos WHERE (enterprise_id = %s OR enterprise_id = 0) AND activo = 1 ORDER BY nombre",
            (ent_id,)
        )
        impuestos_maestros = dictfetchall(cursor)

    return render(request, 'fondos/configuracion_global.html', {
        'medios': medios,
        'condiciones': condiciones,
        'mixtas': mixtas,
        'impuestos_maestros': impuestos_maestros,
    })


@login_required
def aprobaciones(request):
    """Listado de OCs enviadas a Tesorería para aprobación de fondos."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, erp_terceros.nombre as proveedor_nombre
            FROM cmp_ordenes_compra
            JOIN erp_terceros ON cmp_ordenes_compra.proveedor_id = erp_terceros.id
            WHERE cmp_ordenes_compra.estado = 'ENVIADA_TESORERIA'
              AND cmp_ordenes_compra.enterprise_id = %s
            ORDER BY cmp_ordenes_compra.fecha_aprobacion_compras ASC
        """, (ent_id,))
        ordenes = dictfetchall(cursor)
    return render(request, 'fondos/aprobaciones_po.html', {'ordenes': ordenes})


@login_required
def aprobar_po_detalle(request, id):
    """Detalle de OC para aprobación de Tesorería."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT cmp_ordenes_compra.*, erp_terceros.nombre as proveedor_nombre
            FROM cmp_ordenes_compra
            JOIN erp_terceros ON cmp_ordenes_compra.proveedor_id = erp_terceros.id
            WHERE cmp_ordenes_compra.id = %s AND cmp_ordenes_compra.enterprise_id = %s
        """, (id, ent_id))
        po = dictfetchone(cursor)
        if not po:
            messages.error(request, 'Orden no encontrada.')
            return redirect('fondos:aprobaciones')

        cursor.execute("""
            SELECT cmp_detalles_orden.*,
                   cmp_detalles_orden.cantidad_solicitada as cantidad,
                   (cmp_detalles_orden.cantidad_solicitada * cmp_detalles_orden.precio_unitario) as importe,
                   stk_articulos.nombre as articulo_nombre,
                   stk_articulos.codigo as articulo_codigo
            FROM cmp_detalles_orden
            JOIN stk_articulos ON cmp_detalles_orden.articulo_id = stk_articulos.id
            WHERE cmp_detalles_orden.orden_id = %s AND cmp_detalles_orden.enterprise_id = %s
        """, (id, ent_id))
        items = dictfetchall(cursor)

    return render(request, 'fondos/aprobar_po_detalle.html', {'po': po, 'items': items})


@login_required
@require_POST
def post_aprobacion_po(request, id):
    """Procesa aprobación o rechazo de una OC desde Tesorería."""
    ent_id = request.user_data['enterprise_id']
    uid = request.user_data['id']
    action = request.POST.get('action')
    fecha_pago = request.POST.get('fecha_pago_estimada')
    observaciones = request.POST.get('observaciones', '')

    with get_db_cursor() as cursor:
        if action == 'approve':
            cursor.execute("""
                UPDATE cmp_ordenes_compra
                SET estado = 'APROBADA_TESORERIA',
                    fecha_pago_estimada = %s,
                    aprobador_tesoreria_id = %s,
                    fecha_aprobacion_tesoreria = NOW()
                WHERE id = %s AND enterprise_id = %s
            """, (fecha_pago, uid, id, ent_id))
            messages.success(request, f'Fondos aprobados para OC #{id}. Pago estimado: {fecha_pago}')

        elif action == 'reject':
            cursor.execute("""
                UPDATE cmp_ordenes_compra
                SET estado = 'RECHAZADA_TESORERIA',
                    observaciones_rechazo = %s
                WHERE id = %s AND enterprise_id = %s
            """, (observaciones, id, ent_id))
            messages.warning(request, f'OC #{id} devuelta a Compras para revisión.')

    return redirect('fondos:aprobaciones')


@login_required
def kpi_desembolsos(request):
    """KPI de compromisos de fondos por fecha."""
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT fecha_pago_estimada,
                   SUM(total_estimado) as monto_total,
                   COUNT(*) as po_count
            FROM cmp_ordenes_compra
            WHERE estado = 'APROBADA_TESORERIA' AND enterprise_id = %s
              AND fecha_pago_estimada >= CURDATE()
            GROUP BY fecha_pago_estimada
            ORDER BY fecha_pago_estimada ASC
        """, (ent_id,))
        calendario = dictfetchall(cursor)
        
    total_programado = sum((c['monto_total'] or 0) for c in calendario)
    return render(request, 'fondos/kpi_desembolsos.html', {'calendario': calendario, 'total_programado': total_programado})
