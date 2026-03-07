import secrets
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from werkzeug.security import check_password_hash

from apps.core.db import get_db_cursor, dictfetchone, dictfetchall

logger = logging.getLogger(__name__)

def login_view(request):
    """
    Controlador de Login migrado de Quart.
    Mantiene la lógica de SID y selección de empresa.
    """
    # 1. Cargar lista de empresas activas
    show_master = request.GET.get('master') == '1'
    enterprises = []
    
    with get_db_cursor(dictionary=True) as cursor:
        if show_master:
            cursor.execute("SELECT id, nombre, is_saas_owner FROM sys_enterprises WHERE estado = 'activo' ORDER BY is_saas_owner DESC, id ASC")
        else:
            cursor.execute("SELECT id, nombre, is_saas_owner FROM sys_enterprises WHERE estado = 'activo' AND (is_saas_owner = 0 OR id = 0) AND id != 1 ORDER BY id ASC")
        enterprises = dictfetchall(cursor)

    if request.method == 'POST':
        enterprise_id = request.POST.get('enterprise_id')
        username = request.POST.get('username')
        password = request.POST.get('password')

        if enterprise_id == "NEW":
            return redirect('/enterprise/create/') # URL placeholder

        try:
            enterprise_id = int(enterprise_id)
            with get_db_cursor(dictionary=True) as cursor:
                # 1. Verificar si la empresa está activa
                cursor.execute("SELECT estado FROM sys_enterprises WHERE id = %s", (enterprise_id,))
                ent_status = dictfetchone(cursor)
                
                if not ent_status or ent_status['estado'].lower() != 'activo':
                    messages.error(request, "Esta empresa se encuentra inhabilitada temporalmente.")
                    return redirect('core:login')

                # 2. Buscar usuario
                cursor.execute("""
                    SELECT id, password_hash, username, must_change_password
                    FROM sys_users 
                    WHERE username = %s AND enterprise_id = %s
                """, (username, enterprise_id))
                user = dictfetchone(cursor)
                
                if user and check_password_hash(user['password_hash'], password):
                    # --- LOGIN EXITOSO ---
                    new_sid = secrets.token_hex(4)
                    
                    # Estructura de sesión Multi-Pestaña
                    if 's' not in request.session:
                        request.session['s'] = {}
                    
                    request.session['s'][new_sid] = {
                        'user_id': user['id'], 
                        'enterprise_id': enterprise_id
                    }
                    
                    # Compatibilidad con sesión clásica (opcional)
                    request.session['user_id'] = user['id']
                    request.session['enterprise_id'] = enterprise_id
                    request.session.modified = True

                    # MECANISMO DE AFINIDAD DE PESTAÑA (Handshake) - Fase 1.3
                    bind_token = secrets.token_hex(16)
                    request.session['s'][new_sid]['bind_token'] = bind_token
                    request.session.modified = True

                    # Redirigir inyectando el SID en la URL
                    target_url = f"/ventas/dashboard/?sid={new_sid}"
                    response = redirect(target_url)
                    
                    # Seteamos una cookie temporal de "vínculo" que dura 30 segundos (JS la consumirá)
                    response.set_cookie(f'bind_{new_sid}', bind_token, max_age=30, httponly=False, samesite='Lax')
                    return response
                else:
                    messages.error(request, "Usuario o contraseña incorrectos.")
                    
        except Exception as e:
            logger.error(f"Error en login: {e}")
            messages.error(request, "Ocurrió un error al procesar el ingreso.")

    return render(request, 'core/login.html', {
        'enterprises': enterprises,
        'show_master': show_master
    })

def logout_view(request):
    """Cierra la sesión de la pestaña actual."""
    sid = request.GET.get('sid')
    if sid and 's' in request.session and sid in request.session['s']:
        del request.session['s'][sid]
        request.session.modified = True
    return redirect('core:login')

from django.http import JsonResponse
from apps.core.services.georef_service import GeorefService

def api_get_localidades(request):
    provincia = request.GET.get('provincia')
    if not provincia:
        return JsonResponse([], safe=False)
    localidades = GeorefService.get_localidades(provincia)
    return JsonResponse(localidades, safe=False)

def api_get_calles(request):
    localidad = request.GET.get('localidad')
    provincia = request.GET.get('provincia')
    nombre = request.GET.get('nombre')
    
    if not nombre or not provincia:
        return JsonResponse([], safe=False)
        
    calles = GeorefService.get_calles(localidad, provincia, nombre)
    return JsonResponse(calles, safe=False)

def api_get_cp(request):
    provincia = request.GET.get('provincia')
    localidad = request.GET.get('localidad')
    if not provincia or not localidad:
        return JsonResponse([], safe=False)
    cps = GeorefService.get_cp_by_location(provincia, localidad)
    return JsonResponse(cps, safe=False)

def api_get_puestos(request):
    area = request.GET.get('area')
    enterprise_id = request.user_data.get('enterprise_id')
    with get_db_cursor(dictionary=True) as cursor:
        query = "SELECT id, nombre FROM erp_puestos WHERE enterprise_id = %s AND activo = 1"
        params = [enterprise_id]
        if area:
            query += " AND area = %s"
            params.append(area)
        query += " ORDER BY nombre"
        cursor.execute(query, params)
        return JsonResponse(dictfetchall(cursor), safe=False)

def api_get_areas(request):
    enterprise_id = request.user_data.get('enterprise_id')
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute(
            "SELECT id, nombre, color, icono FROM erp_areas WHERE (enterprise_id=%s OR enterprise_id=0) AND activo=1 ORDER BY nombre",
            (enterprise_id,)
        )
        return JsonResponse(dictfetchall(cursor), safe=False)

def home_redirect(request):
    """Redirige "/" al login.html siguiendo el requerimiento del usuario."""
    return redirect('core:login')

from django.http import HttpResponse

def get_logo_raw(request, logo_id):
    """Sirve el logo desde la base de datos (BLOB)."""
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT logo_data, mime_type FROM sys_enterprise_logos WHERE id = %s", (logo_id,))
        row = dictfetchone(cursor)
        if not row:
            return HttpResponse("Logo no encontrado", status=404)
        
        response = HttpResponse(row['logo_data'], content_type=row['mime_type'])
        response['Cache-Control'] = 'public, max-age=86400'
        return response
