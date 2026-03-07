import json
import traceback
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from apps.core.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone, atomic_transaction

def has_permission(user, perm): return True

@login_required
# @permission_required('produccion.dashboard') # Will implement RBAC later or use decorators inside views
def dashboard(request):
    """Tablero Principal de Producción."""
    try:
        if not has_permission(request.user_data, 'produccion.dashboard'):
            messages.error(request, "Acceso denegado (produccion.dashboard)")
            return redirect('core:home')
            
        return render(request, 'produccion/dashboard.html')
    except Exception as e:
        traceback.print_exc()
        messages.error(request, f"Error al cargar el dashboard de producción: {str(e)}")
        return redirect('core:home')

@login_required
def overhead_templates(request):
    """Listado de Plantillas de Costos Indirectos."""
    if not has_permission(request.user_data, 'produccion.admin'):
        messages.error(request, "Acceso denegado")
        return redirect('produccion:dashboard')
        
    ent_id = request.user_data['enterprise_id']
    templates = []
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT id, nombre, descripcion, activo, created_at 
            FROM cmp_overhead_templates 
            WHERE enterprise_id = %s
            ORDER BY nombre ASC
        ''', [ent_id])
        templates = dictfetchall(cursor)
        
        for t in templates:
            cursor.execute('''
                SELECT 
                    COUNT(*) as qty_items, 
                    SUM(monto_estimado) as total_estimado 
                FROM cmp_overhead_templates_detalle 
                WHERE template_id = %s
            ''', [t['id']])
            stats = dictfetchone(cursor)
            t['detalles_count'] = stats['qty_items'] or 0
            t['suma_estimada'] = float(stats['total_estimado'] or 0.0)

    return render(request, 'produccion/overhead_templates.html', {'templates': templates})

@login_required
def api_save_overhead_template(request):
    if not has_permission(request.user_data, 'produccion.admin'):
        return JsonResponse({'success': False, 'message': 'Acceso denegado'}, status=403)
        
    ent_id = request.user_data['enterprise_id']
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre')
        descripcion = data.get('descripcion', '')
        detalles = data.get('detalles', [])
        
        if not nombre:
            return JsonResponse({'success': False, 'message': 'El nombre es obligatorio'}, status=400)
            
        with get_db_cursor() as cursor:
            cursor.execute('''
                INSERT INTO cmp_overhead_templates 
                (enterprise_id, nombre, descripcion, user_id)
                VALUES (%s, %s, %s, %s)
            ''', [ent_id, nombre, descripcion, request.user_data['id']])
            
            cursor.execute("SELECT LAST_INSERT_ID() as new_id")
            template_id = dictfetchone(cursor)['new_id']
            
            for det in detalles:
                cursor.execute('''
                    INSERT INTO cmp_overhead_templates_detalle
                    (template_id, enterprise_id, tipo_gasto, descripcion, monto_estimado, base_calculo, cantidad_batch, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', [template_id, ent_id, det['tipo_gasto'], det['descripcion'], det['monto_estimado'], det['base_calculo'], det.get('cantidad_batch', 1), request.user_data['id']])
        
        return JsonResponse({'success': True, 'message': 'Plantilla guardada exitosamente.', 'template_id': template_id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error guardando plantilla: {str(e)}'}, status=500)

@login_required
def api_get_overhead_details(request, template_id):
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT tipo_gasto, descripcion, monto_estimado, base_calculo, cantidad_batch
            FROM cmp_overhead_templates_detalle
            WHERE template_id = %s AND enterprise_id = %s
        ''', [template_id, ent_id])
        detalles = dictfetchall(cursor)
        
        # Convert Decimals
        for d in detalles:
            if 'monto_estimado' in d and d['monto_estimado'] is not None:
                d['monto_estimado'] = float(d['monto_estimado'])
            if 'cantidad_batch' in d and d['cantidad_batch'] is not None:
                d['cantidad_batch'] = float(d['cantidad_batch'])
                
    return JsonResponse({'success': True, 'detalles': detalles})

@login_required
def documentos(request):
    if not has_permission(request.user_data, 'produccion.view'):
        messages.error(request, "Acceso denegado")
        return redirect('produccion:dashboard')
        
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT sys_documentos_adjuntos.*, 
                CASE 
                    WHEN entidad_tipo = 'ARTICULO' THEN (SELECT nombre FROM stk_articulos WHERE id = sys_documentos_adjuntos.entidad_id)
                    WHEN entidad_tipo = 'PROVEEDOR' THEN (SELECT nombre FROM erp_terceros WHERE id = sys_documentos_adjuntos.entidad_id)
                    ELSE 'N/A' 
                END as entidad_nombre
            FROM sys_documentos_adjuntos
            WHERE sys_documentos_adjuntos.enterprise_id = %s
            ORDER BY sys_documentos_adjuntos.fecha_vencimiento ASC
        ''', [ent_id])
        documentos = dictfetchall(cursor)
    return render(request, 'produccion/documentos.html', {'documentos': documentos})

@login_required
def proyectos(request):
    if not has_permission(request.user_data, 'produccion.admin'):
        messages.error(request, "Acceso denegado")
        return redirect('produccion:dashboard')
        
    ent_id = request.user_data['enterprise_id']
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT prd_proyectos_desarrollo.*, stk_articulos.nombre as producto_nombre
            FROM prd_proyectos_desarrollo
            LEFT JOIN stk_articulos ON prd_proyectos_desarrollo.articulo_objetivo_id = stk_articulos.id
            WHERE prd_proyectos_desarrollo.enterprise_id = %s
            ORDER BY prd_proyectos_desarrollo.fecha_inicio DESC
        ''', [ent_id])
        proyectos = dictfetchall(cursor)
    return render(request, 'produccion/proyectos.html', {'proyectos': proyectos})

@login_required
def bandeja_costos(request):
    """Bandeja Global de Costos."""
    if not has_permission(request.user_data, 'cost_accounting') and not has_permission(request.user_data, 'produccion.admin'):
        messages.error(request, "Acceso denegado")
        return redirect('produccion:dashboard')
        
    with get_db_cursor() as cursor:
        cursor.execute('''
            SELECT stk_pricing_propuestas.*, stk_articulos.nombre as articulo_nombre, stk_articulos.codigo as articulo_codigo, 
                   stk_metodos_costeo.nombre as metodo_nombre,
                    stk_listas_precios.nombre as lista_nombre
            FROM stk_pricing_propuestas
            JOIN stk_articulos ON stk_pricing_propuestas.articulo_id = stk_articulos.id
            LEFT JOIN stk_metodos_costeo ON stk_pricing_propuestas.metodo_costeo_id = stk_metodos_costeo.id
            LEFT JOIN stk_listas_precios ON stk_pricing_propuestas.lista_id = stk_listas_precios.id
            WHERE stk_pricing_propuestas.estado = 'PENDIENTE' AND stk_pricing_propuestas.enterprise_id = %s
            ORDER BY stk_pricing_propuestas.fecha_propuesta DESC
        ''', [request.user_data['enterprise_id']])
        propuestas = dictfetchall(cursor)
    return render(request, 'produccion/bandeja_costos.html', {'propuestas': propuestas})

@login_required
def api_aprobar_costeo(request, propuesta_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método inválido'}, status=405)
        
    if not has_permission(request.user_data, 'cost_accounting'):
        return JsonResponse({'success': False, 'message': 'Acceso denegado'}, status=403)
        
    ent_id = request.user_data['enterprise_id']
    try:
        with get_db_cursor() as cursor:
            # 1. Obtener datos de la propuesta
            cursor.execute("SELECT articulo_id, costo_propuesto FROM stk_pricing_propuestas WHERE id = %s AND enterprise_id = %s AND estado = 'PENDIENTE'", [propuesta_id, ent_id])
            p = dictfetchone(cursor)
            if not p: return JsonResponse({'success': False, 'message': 'Propuesta no encontrada o ya procesada.'}, status=404)
            articulo_id, costo_propuesto = p['articulo_id'], p['costo_propuesto']
            
            # 2. Aprobar
            cursor.execute("UPDATE stk_pricing_propuestas SET estado = 'APROBADO', user_id_update = %s, updated_at = NOW() WHERE id = %s", [request.user_data['id'], propuesta_id])
            
            # 3. Impactar en el artículo (costo_reposicion)
            cursor.execute("UPDATE stk_articulos SET costo_reposicion = %s, costo_ultima_compra = %s WHERE id = %s AND enterprise_id = %s", [costo_propuesto, costo_propuesto, articulo_id, ent_id])
            
        return JsonResponse({'success': True, 'message': 'Costeo impactado exitosamente.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
def api_rechazar_costeo(request, propuesta_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método inválido'}, status=405)
        
    if not has_permission(request.user_data, 'cost_accounting'):
        return JsonResponse({'success': False, 'message': 'Acceso denegado'}, status=403)
        
    ent_id = request.user_data['enterprise_id']
    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE stk_pricing_propuestas SET estado = 'RECHAZADO', user_id_update = %s, updated_at = NOW() WHERE id = %s AND enterprise_id = %s", [request.user_data['id'], propuesta_id, ent_id])
        return JsonResponse({'success': True, 'message': 'Costeo rechazado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
