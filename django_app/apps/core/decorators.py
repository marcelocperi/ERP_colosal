import json
import logging
from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from apps.core.db import get_db_cursor

logger = logging.getLogger(__name__)

def _is_ajax_or_fetch(request):
    """Detecta si la petición viene de fetch() o AJAX y espera JSON."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept:
        return True
        
    content_type = request.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        return True
        
    # Heurística para fetch()
    if 'text/html' not in accept and accept != '':
        return True
    return False

def _unauthorized_response(request, message="Sesión expirada o inválida. Recargue la página."):
    """Respuesta apropiada para cuando el usuario no está autenticado."""
    # En Django, manejamos los logs de forma síncrona o vía señales/middleware.
    # Por ahora replicamos el log básico si es necesario, o lo dejamos para la fase de auditoría.
    
    if _is_ajax_or_fetch(request):
        return JsonResponse({
            "error": message, 
            "redirect": reverse('core:login')
        }, status=401)
    
    # Inyectar sid en el redirect si existe
    sid = getattr(request, 'sid', None)
    login_url = reverse('core:login')
    if sid:
        login_url += f"?sid={sid}"
        
    messages.error(request, message)
    return redirect(login_url)

def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not getattr(request, 'user_data', None):
            return _unauthorized_response(request)
        return view_func(request, *args, **kwargs)
    return wrapped_view

def permission_required(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not getattr(request, 'user_data', None):
                return _unauthorized_response(request)
            
            user_data = request.user_data
            user_permissions = getattr(request, 'permissions', [])

            # Superadmin bypass (username hardcoded como en Quart)
            if str(user_data.get('username', '')).lower() == 'superadmin':
                return view_func(request, *args, **kwargs)

            # Sysadmin check
            if permission_code == 'sysadmin':
                if 'sysadmin' not in user_permissions:
                    msg = "Acceso Denegado. Se requiere nivel Super Administrador."
                    if _is_ajax_or_fetch(request):
                        return JsonResponse({"error": msg}, status=403)
                    messages.error(request, msg)
                    return redirect('ventas:dashboard')
                return view_func(request, *args, **kwargs)

            # Wildcard 'all' check
            if 'all' in user_permissions:
                return view_func(request, *args, **kwargs)
            
            # Specific permission check
            if permission_code not in user_permissions:
                msg = f"Acceso Denegado: Se requiere permiso '{permission_code}'"
                if _is_ajax_or_fetch(request):
                    return JsonResponse({"error": msg}, status=403)
                messages.error(request, msg)
                return redirect('ventas:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator
