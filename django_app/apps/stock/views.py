import json
import datetime
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone

logger = logging.getLogger(__name__)

@login_required
# @permission_required('view_articulos')
def dashboard(request):
    """Tablero principal de Inventario y existencias"""
    try:
        # ent_id de request.user_data (inyectado por middleware)
        ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
        search_query = request.GET.get('q', '')
        deposito_id = request.GET.get('deposito_id')
        
        with get_db_cursor() as cursor:
            # 1. Depósitos (Warehouse)
            cursor.execute("SELECT id, nombre FROM stk_depositos WHERE enterprise_id = %s AND activo = 1", (ent_id,))
            depositos = dictfetchall(cursor)
            
            # 2. Resumen de Existencias
            sql = """
                SELECT 
                    stk_articulos.nombre as articulo_nombre, stk_articulos.modelo as autor, stk_articulos.codigo as isbn, 
                    stk_depositos.nombre as deposito_nombre, 
                    stk_existencias.cantidad,
                    stk_articulos.id as articulo_id
                FROM stk_existencias
                JOIN stk_depositos ON stk_existencias.deposito_id = stk_depositos.id
                JOIN stk_articulos ON stk_existencias.articulo_id = stk_articulos.id
                WHERE stk_existencias.enterprise_id = %s
            """
            params = [ent_id]
            
            if search_query:
                sql += " AND (stk_articulos.nombre LIKE %s OR stk_articulos.codigo LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])
            
            if deposito_id:
                sql += " AND stk_existencias.deposito_id = %s"
                params.append(deposito_id)
                
            sql += " ORDER BY stk_articulos.nombre ASC"
            
            cursor.execute(sql, tuple(params))
            items = dictfetchall(cursor)
            
            # Estadísticas rápidas
            cursor.execute("SELECT SUM(cantidad) as total FROM stk_existencias WHERE enterprise_id = %s", (ent_id,))
            row_total = dictfetchone(cursor)
            total_stock = row_total['total'] if row_total and row_total['total'] else 0
    
            cursor.execute("""
                SELECT COUNT(*) as low_stock_count
                FROM (
                    SELECT stk_articulos.id
                    FROM stk_articulos
                    LEFT JOIN stk_existencias ON stk_articulos.id = stk_existencias.articulo_id AND stk_articulos.enterprise_id = stk_existencias.enterprise_id
                    WHERE stk_articulos.enterprise_id = %s
                    GROUP BY stk_articulos.id, stk_articulos.stock_minimo
                    HAVING (SELECT COALESCE(SUM(cantidad), 0) FROM stk_existencias WHERE articulo_id = stk_articulos.id AND enterprise_id = stk_articulos.enterprise_id) <= stk_articulos.stock_minimo 
                       AND stk_articulos.stock_minimo > 0
                ) as low_stock
            """, (ent_id,))
            row_low = dictfetchone(cursor)
            low_stock_count = row_low['low_stock_count'] if row_low else 0
                
        return render(request, 'stock/dashboard.html', {
            'depositos': depositos, 
            'items': items, 
            'total_stock': total_stock,
            'low_stock_count': low_stock_count,
            'current_filters': {'q': search_query, 'deposito_id': deposito_id}
        })
    except Exception as e:
        logger.error(f"Error en stock.dashboard: {e}", exc_info=True)
        messages.error(request, f"Error al cargar el dashboard de stock: {str(e)}")
        return redirect('/')

@login_required
def articulos(request):
    """Maestro de Artículos"""
    ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
    q = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    
    try:
        with get_db_cursor() as cursor:
            # Filtros y conteo
            count_sql = "SELECT COUNT(*) as total FROM stk_articulos WHERE enterprise_id = %s OR enterprise_id = 0"
            count_params = [ent_id]
            
            if q:
                count_sql += " AND (nombre LIKE %s OR codigo LIKE %s OR modelo LIKE %s OR marca LIKE %s)"
                count_params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
            
            cursor.execute(count_sql, tuple(count_params))
            total_items = dictfetchone(cursor)['total']
            total_pages = (total_items + per_page - 1) // per_page
            
            # Query principal
            # Adaptación de la lógica de metadatos JSON
            sql = """
                SELECT stk_articulos.*, 
                       stk_articulos.codigo as isbn, stk_articulos.modelo as autor,
                       stk_articulos.marca as editorial,
                       IFNULL(e.total_cantidad, 0) as stock_total
                FROM stk_articulos
                LEFT JOIN (
                    SELECT articulo_id, SUM(cantidad) as total_cantidad
                    FROM stk_existencias
                    WHERE enterprise_id = %s
                    GROUP BY articulo_id
                ) e ON stk_articulos.id = e.articulo_id
                WHERE stk_articulos.enterprise_id = %s OR stk_articulos.enterprise_id = 0
            """
            params = [ent_id, ent_id]
            
            if q:
                sql += " AND (stk_articulos.nombre LIKE %s OR stk_articulos.codigo LIKE %s OR stk_articulos.modelo LIKE %s OR stk_articulos.marca LIKE %s)"
                params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
                
            sql += " ORDER BY stk_articulos.nombre ASC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(sql, tuple(params))
            articulos_data = dictfetchall(cursor)
            
            # Obtener Tipos para modales
            cursor.execute("SELECT id, nombre, naturaleza FROM stk_tipos_articulo WHERE enterprise_id = %s OR enterprise_id = 0", (ent_id,))
            tipos = dictfetchall(cursor)
            
        return render(request, 'stock/articulos.html', {
            'articulos': articulos_data,
            'tipos': tipos,
            'page': page,
            'total_pages': total_pages,
            'total_items': total_items,
            'current_filters': {'q': q}
        })
    except Exception as e:
        logger.error(f"Error en stock.articulos: {e}", exc_info=True)
        messages.error(request, f"Error al cargar artículos: {e}")
        return redirect('stock:dashboard')

@login_required
def articulo_guardar(request):
    """Guardar o actualizar artículo"""
    if request.method == 'POST':
        ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
        art_id = request.POST.get('id')
        
        # Datos básicos
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('isbn') or request.POST.get('codigo')
        modelo = request.POST.get('autor') or request.POST.get('modelo')
        marca = request.POST.get('editorial') or request.POST.get('marca')
        tipo_id = request.POST.get('tipo_articulo_id', 1)
        precio = request.POST.get('precio', 0)
        stock_min = request.POST.get('stock_minimo', 0)
        
        try:
            with get_db_cursor() as cursor:
                if art_id:
                    # Update
                    cursor.execute("""
                        UPDATE stk_articulos SET 
                            nombre=%s, codigo=%s, modelo=%s, marca=%s, 
                            tipo_articulo_id=%s, precio_venta=%s, stock_minimo=%s
                        WHERE id=%s AND (enterprise_id=%s OR enterprise_id=0)
                    """, (nombre, codigo, modelo, marca, tipo_id, precio, stock_min, art_id, ent_id))
                    messages.success(request, "Artículo actualizado correctamente.")
                else:
                    # Insert
                    cursor.execute("""
                        INSERT INTO stk_articulos (enterprise_id, nombre, codigo, modelo, marca, tipo_articulo_id, precio_venta, stock_minimo, tipo_articulo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'mercaderia')
                    """, (ent_id, nombre, codigo, modelo, marca, tipo_id, precio, stock_min))
                    messages.success(request, "Artículo creado correctamente.")
        except Exception as e:
            logger.error(f"Error guardando artículo: {e}")
            messages.error(request, f"Error al guardar: {e}")
            
    return redirect('stock:articulos')

@login_required
def movimientos_historial(request):
    """Historial de movimientos de stock"""
    ent_id = getattr(request, 'user_data', {}).get('enterprise_id', 0)
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    stk_movimientos.id, stk_movimientos.fecha, stk_motivos.nombre as motivo, stk_motivos.tipo,
                    do.nombre as origen, dd.nombre as destino,
                    sys_users.username, stk_movimientos.observaciones, erp_terceros.nombre as tercero
                FROM stk_movimientos
                JOIN stk_motivos ON stk_movimientos.motivo_id = stk_motivos.id
                LEFT JOIN stk_depositos do ON stk_movimientos.deposito_origen_id = do.id
                LEFT JOIN stk_depositos dd ON stk_movimientos.deposito_destino_id = dd.id
                LEFT JOIN sys_users ON stk_movimientos.user_id = sys_users.id
                LEFT JOIN erp_terceros ON stk_movimientos.tercero_id = erp_terceros.id
                WHERE stk_movimientos.enterprise_id = %s
                ORDER BY stk_movimientos.fecha DESC
                LIMIT 100
            """, (ent_id,))
            movimientos = dictfetchall(cursor)
        return render(request, 'stock/movimientos_historial.html', {'movimientos': movimientos})
    except Exception as e:
        messages.error(request, f"Error cargando historial: {e}")
        return redirect('stock:dashboard')

# Stubs for other views
@login_required
def transferencias(request):
    """Listado de transferencias entre depósitos."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM stk_transferencias ORDER BY fecha DESC LIMIT 100")
        transferencias = dictfetchall(cursor)
    return render(request, 'stock/transferencias.html', {'transferencias': transferencias})

@login_required
def articulo_historial(request, articulo_id): return HttpResponse("Modulo en construccion")
@login_required
def movimiento_crear(request): return HttpResponse("Modulo en construccion")
@login_required
def movimiento_detalle(request, movimiento_id): return HttpResponse("Modulo en construccion")
@login_required
def articulos_importar(request): return HttpResponse("Modulo en construccion")
@login_required
def depositos(request):
    """Maestro de depósitos."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM stk_depositos ORDER BY nombre")
        depositos = dictfetchall(cursor)
    return render(request, 'stock/depositos.html', {'depositos': depositos})

@login_required
def deposito_guardar(request): return redirect('stock:depositos')
@login_required
def tipos_articulo(request):
    """Maestro de tipos de artículo."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM stk_tipos_articulo ORDER BY nombre")
        tipos = dictfetchall(cursor)
    return render(request, 'stock/tipos_articulo.html', {'tipos': tipos})
@login_required
def tipo_articulo_guardar(request): return redirect('stock:tipos_articulo')
@login_required
def api_articulo_seguridad(request, articulo_id): return JsonResponse({'success': False, 'message': 'Stub'})
