import time
import secrets
import logging
import threading
import asyncio
from django.conf import settings
from django.utils.decorators import sync_and_async_middleware
from asgiref.sync import sync_to_async
from .db import get_db_cursor, dictfetchone, dictfetchall

logger = logging.getLogger(__name__)

# Cache global para permisos (similar a Quart session_service)
PERMISSION_CACHE = {}
PERMISSION_LOCK = threading.Lock()
CACHE_TTL = 300  # 5 minutos

class MultiTabSessionMiddleware:
    sync_capable = True
    async_capable = False
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._prepare_request(request)
        self._sync_load_session(request)
        
        logger.info(f"Path: {request.path} | SID: {request.sid} | Logged: {bool(request.user_data)}")
        response = self.get_response(request)
            
        self._inject_handshake(request, response)
        return response

    def _prepare_request(self, request):
        sid = request.GET.get('sid') or request.POST.get('sid') or request.headers.get('X-SID')
        request.sid = sid
        request.user_data = None
        request.enterprise = None
        request.permissions = []

    def _sync_load_session(self, request):
        if hasattr(request, 'session'):
            if 's' not in request.session:
                request.session['s'] = {}
            sid = request.sid
            if not sid:
                active_sids = list(request.session['s'].keys())
                if len(active_sids) == 1:
                    sid = active_sids[0]
                    request.sid = sid

            if sid:
                if sid in request.session['s']:
                    ctx = request.session['s'][sid]
                    uid = ctx.get('user_id')
                    eid = ctx.get('enterprise_id')
                    if uid is not None and eid is not None:
                        if self._load_full_context(request, uid, eid):
                             pass
                        else:
                            request.login_reason = 'db_not_found'
                    else:
                        request.login_reason = 'invalid_ctx'
                else:
                    request.login_reason = 'sid_expired'
            else:
                if request.session['s']:
                    request.login_reason = 'missing_sid'
                else:
                    request.login_reason = 'no_active_sessions'

    def _inject_handshake(self, request, response):
        # 5. Inyectar Cookie de Handshake si se generó un SID nuevo
        handshake = getattr(request, '_new_sid_handshake', None)
        if handshake:
            sid_val, token_val = handshake
            response.set_cookie(f'bind_{sid_val}', token_val, max_age=30, httponly=False, samesite='Lax')

    def _load_full_context(self, request, user_id, ent_id):
        now_ts = time.time()
        cache_key = (ent_id, user_id)

        # 1. Cache Layer
        with PERMISSION_LOCK:
            if cache_key in PERMISSION_CACHE:
                ts, cached_user, cached_perms, cached_ent = PERMISSION_CACHE[cache_key]
                if now_ts - ts < CACHE_TTL:
                    request.user_data = dict(cached_user)
                    request.permissions = list(cached_perms)
                    request.enterprise = dict(cached_ent)
                    return True

        # 2. Database Layer
        try:
            with get_db_cursor(dictionary=True) as cursor:
                # Carga de Usuario y Rol
                cursor.execute("""
                    SELECT sys_users.id, sys_users.username, sys_roles.name as role_name, sys_users.role_id
                    FROM sys_users 
                    LEFT JOIN sys_roles ON sys_users.role_id = sys_roles.id AND sys_roles.enterprise_id = sys_users.enterprise_id
                    WHERE sys_users.id = %s AND sys_users.enterprise_id = %s
                """, (user_id, ent_id))
                user_row = dictfetchone(cursor)
                
                if not user_row:
                    return False

                role_clean = (user_row['role_name'] or 'Sin Rol').strip()
                request.user_data = {
                    'id': user_row['id'],
                    'username': user_row['username'],
                    'role_name': role_clean,
                    'role_id': user_row['role_id'],
                    'enterprise_id': ent_id
                }

                # Carga de Datos de Empresa
                cursor.execute("SELECT nombre, logo_path, lema FROM sys_enterprises WHERE id = %s", (ent_id,))
                ent_row = dictfetchone(cursor)
                request.enterprise = ent_row if ent_row else {'nombre': 'Colosal ERP', 'logo_path': None}

                # Carga de Permisos
                cursor.execute("""
                    SELECT DISTINCT sys_permissions.code 
                    FROM sys_permissions
                    JOIN sys_role_permissions ON sys_permissions.id = sys_role_permissions.permission_id
                    WHERE sys_role_permissions.role_id = %s AND sys_role_permissions.enterprise_id = %s
                """, (user_row['role_id'], ent_id))
                request.permissions = [str(row['code']).lower().strip() for row in dictfetchall(cursor)]

                # SysAdmin/Admin Bypasses
                user_lower = str(user_row['username']).lower()
                role_lower = role_clean.lower()
                if user_lower == 'superadmin' or role_lower == 'adminsys':
                    if 'all' not in request.permissions: request.permissions.append('all')
                    if 'sysadmin' not in request.permissions: request.permissions.append('sysadmin')
                    logger.info(f"SuperAdmin Bypass for {user_lower}")
                elif user_lower == 'admin' or role_lower in ['admin', 'administrador'] or user_id == 1:
                    if 'all' not in request.permissions: request.permissions.append('all')
                    logger.info(f"Admin Bypass for {user_lower}")

                logger.info(f"Permissions for {user_lower}: {request.permissions}")

                # Guardar en Caché
                with PERMISSION_LOCK:
                    PERMISSION_CACHE[cache_key] = (now_ts, request.user_data, request.permissions, request.enterprise)
                
                return True
        except Exception as e:
            logger.error(f"Error loading full context: {e}")
            return False

class LoginEnforcerMiddleware:
    sync_capable = True
    async_capable = False
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect(request):
            return self._get_redirect(request)
            
        return self.get_response(request)

    def _should_redirect(self, request):
        # 1. Permitir archivos estáticos y media
        static_url = getattr(settings, 'STATIC_URL', '/static/')
        if not static_url.startswith('/'):
            static_url = '/' + static_url
            
        if request.path.startswith(static_url) or '/static/' in request.path:
            return False

        # 2. Rutas exentas de login (exactas)
        exempt_paths = [
            '/login.html',
            '/logout/',
            '/favicon.ico',
        ]
        
        # 3. Verificar si el usuario está logueado (cargado por MultiTabSessionMiddleware)
        if request.path not in exempt_paths:
            if not getattr(request, 'user_data', None):
                return True
        return False

    def _get_redirect(self, request):
        # Si no está logueado, redirigir a login.html
        # Intentamos usar reverse para flexibilidad, pero con fallback a string literal
        try:
            from django.urls import reverse
            target_url = reverse('core:login')
        except:
            target_url = '/login.html'
            
        reason = getattr(request, 'login_reason', 'unknown')
        logger.warning(f"Redirecting to login. Path: {request.path} | Reason: {reason} | SID: {request.sid}")
        
        from django.shortcuts import redirect
        # Pasamos la razón como query param para que el usuario pueda verla si quiere debuggear
        return redirect(f"{target_url}?reason={reason}")
