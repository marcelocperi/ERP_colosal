import traceback
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from apps.core.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone, atomic_transaction
from .services import PricingService

@login_required
def dashboard(request):
    try:
        with get_db_cursor() as cursor:
            # Get price lists with pending count
            cursor.execute("""
                SELECT stk_listas_precios.*, 
                       (SELECT COUNT(*) FROM stk_pricing_propuestas 
                        WHERE stk_pricing_propuestas.lista_id = stk_listas_precios.id AND stk_pricing_propuestas.estado = 'PENDIENTE' AND stk_pricing_propuestas.enterprise_id = %s) as pending_count
                FROM stk_listas_precios 
                WHERE stk_listas_precios.enterprise_id = %s OR stk_listas_precios.enterprise_id = 0
            """, [request.user_data['enterprise_id'], request.user_data['enterprise_id']])
            listas = dictfetchall(cursor)
            
            # Get recent price updates
            cursor.execute("""
                SELECT stk_articulos_precios.*, stk_articulos.nombre as articulo_nombre, stk_listas_precios.nombre as lista_nombre
                FROM stk_articulos_precios
                JOIN stk_articulos ON stk_articulos_precios.articulo_id = stk_articulos.id
                JOIN stk_listas_precios ON stk_articulos_precios.lista_precio_id = stk_listas_precios.id
                WHERE stk_articulos_precios.enterprise_id = %s
                ORDER BY stk_articulos_precios.fecha_inicio_vigencia DESC LIMIT 10
            """, [request.user_data['enterprise_id']])
            ultimos_precios = dictfetchall(cursor)
    
        return render(request, 'pricing/dashboard.html', {'listas': listas, 'ultimos_precios': ultimos_precios})
    except Exception as e:
        traceback.print_exc()
        messages.error(request, f"Error al cargar el dashboard de pricing: {str(e)}")
        return redirect('core:home')

@login_required
def lista_detalle(request, lista_id):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM stk_listas_precios WHERE id = %s AND (enterprise_id = %s OR enterprise_id = 0)", [lista_id, request.user_data['enterprise_id']])
        lista = dictfetchone(cursor)
        if not lista:
            messages.error(request, "Lista de precios no encontrada.")
            return redirect('pricing:dashboard')

        # Get rules for this list
        cursor.execute("""
            SELECT stk_pricing_reglas.*, stk_metodos_costeo.nombre as metodo_nombre
            FROM stk_pricing_reglas
            JOIN stk_metodos_costeo ON stk_pricing_reglas.metodo_costo_id = stk_metodos_costeo.id
            WHERE stk_pricing_reglas.lista_precio_id = %s AND stk_pricing_reglas.enterprise_id = %s
            ORDER BY stk_pricing_reglas.prioridad DESC
        """, [lista_id, request.user_data['enterprise_id']])
        reglas = dictfetchall(cursor)
        
        # Get methods for selection
        cursor.execute("SELECT * FROM stk_metodos_costeo")
        metodos = dictfetchall(cursor)
        
        # Get natures for selection
        naturalezas = ['PRODUCTO', 'SERVICIO', 'LIBRO', 'ABONO', 'COMBO']

        # Count pending proposals to control Recalculate button
        cursor.execute("""
            SELECT COUNT(*) as c FROM stk_pricing_propuestas 
            WHERE lista_id = %s AND estado = 'PENDIENTE' AND enterprise_id = %s
        """, [lista_id, request.user_data['enterprise_id']])
        pending_count = dictfetchone(cursor)['c']

    return render(request, 'pricing/lista_detalle.html', {
        'lista': lista, 
        'reglas': reglas, 
        'metodos': metodos, 
        'naturalezas': naturalezas, 
        'pending_count': pending_count
    })

@login_required
def regla_guardar(request):
    if request.method == 'POST':
        try:
            rid = request.POST.get('id')
            lista_id = request.POST.get('lista_id')
            naturaleza = request.POST.get('naturaleza')
            metodo_id = request.POST.get('metodo_id')
            markup = request.POST.get('markup')
            prioridad = request.POST.get('prioridad', 0)
            
            with get_db_cursor() as cursor:
                if rid:
                    cursor.execute("""
                        UPDATE stk_pricing_reglas 
                        SET naturaleza=%s, metodo_costo_id=%s, coeficiente_markup=%s, prioridad=%s
                        WHERE id=%s AND enterprise_id=%s
                    """, [naturaleza, metodo_id, markup, prioridad, rid, request.user_data['enterprise_id']])
                    messages.success(request, "Regla actualizada")
                else:
                    cursor.execute("""
                        INSERT INTO stk_pricing_reglas (enterprise_id, lista_precio_id, naturaleza, metodo_costo_id, coeficiente_markup, prioridad)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [request.user_data['enterprise_id'], lista_id, naturaleza, metodo_id, markup, prioridad])
                    messages.success(request, "Regla creada")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('pricing:lista_detalle', lista_id=lista_id)

@login_required
def lista_recalcular(request, id):
    if request.method == 'POST':
        try:
            count = PricingService.calculate_list_prices(request.user_data['enterprise_id'], id, request.user_data['id'])
            messages.info(request, f"Se han generado {count} propuestas de precio. Esperando aprobación de Cost Accounting.")
        except Exception as e:
            messages.error(request, f"Error al generar propuestas: {e}")
        return redirect('pricing:lista_detalle', lista_id=id)

@login_required
def lista_pendientes(request, id):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM stk_listas_precios WHERE id = %s", [id])
        lista = dictfetchone(cursor)
        
        cursor.execute("""
            SELECT stk_pricing_propuestas.*, stk_articulos.nombre as articulo_nombre, stk_articulos.codigo as articulo_codigo, stk_metodos_costeo.nombre as metodo_nombre
            FROM stk_pricing_propuestas
            JOIN stk_articulos ON stk_pricing_propuestas.articulo_id = stk_articulos.id
            LEFT JOIN stk_metodos_costeo ON stk_pricing_propuestas.metodo_costeo_id = stk_metodos_costeo.id
            WHERE stk_pricing_propuestas.lista_id = %s AND stk_pricing_propuestas.estado = 'PENDIENTE' AND stk_pricing_propuestas.enterprise_id = %s
        """, [id, request.user_data['enterprise_id']])
        propuestas = dictfetchall(cursor)
        
    return render(request, 'pricing/lista_pendientes.html', {'lista': lista, 'propuestas': propuestas})

@login_required
def propuesta_accion(request):
    if request.method == 'POST':
        lista_id = request.POST.get('lista_id')
        try:
            propuesta_ids = request.POST.getlist('propuesta_ids')
            accion = request.POST.get('accion') # 'APROBADO' o 'RECHAZADO'
            motivo = request.POST.get('motivo', '')
            
            if not propuesta_ids:
                messages.warning(request, "Debe seleccionar al menos un artículo.")
                if not lista_id:
                    return redirect('pricing:todas_las_pendientes')
                return redirect('pricing:lista_pendientes', id=lista_id)
                
            count = PricingService.procesar_aprobacion(request.user_data['enterprise_id'], propuesta_ids, accion, motivo, request.user_data['id'])
            messages.success(request, f"{count} propuestas procesadas con éxito ({accion}).")
        except Exception as e:
            messages.error(request, f"Error al procesar: {e}")
        
        if request.POST.get('from_global') == '1':
            return redirect('pricing:todas_las_pendientes')
        
        if lista_id:
            return redirect('pricing:lista_pendientes', id=lista_id)
        return redirect('pricing:todas_las_pendientes')

@login_required
def todas_las_pendientes(request):
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT stk_pricing_propuestas.*, stk_articulos.nombre as articulo_nombre, stk_articulos.codigo as articulo_codigo, 
                   stk_metodos_costeo.nombre as metodo_nombre,
                   stk_listas_precios.nombre as lista_nombre
            FROM stk_pricing_propuestas
            JOIN stk_articulos ON stk_pricing_propuestas.articulo_id = stk_articulos.id
            LEFT JOIN stk_metodos_costeo ON stk_pricing_propuestas.metodo_costeo_id = stk_metodos_costeo.id
            LEFT JOIN stk_listas_precios ON stk_pricing_propuestas.lista_id = stk_listas_precios.id
            WHERE stk_pricing_propuestas.estado = 'PENDIENTE' AND stk_pricing_propuestas.enterprise_id = %s
            ORDER BY stk_pricing_propuestas.fecha_propuesta DESC
        """, [request.user_data['enterprise_id']])
        propuestas = dictfetchall(cursor)
        
    return render(request, 'pricing/pendientes_globales.html', {'propuestas': propuestas})
