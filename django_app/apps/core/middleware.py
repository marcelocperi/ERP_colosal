import time
import secrets
import logging
import threading
from django.conf import settings
from .db import get_db_cursor, dictfetchone, dictfetchall

logger = logging.getLogger(__name__)

# Cache global para permisos (similar a Quart session_service)
PERMISSION_CACHE = {}
PERMISSION_LOCK = threading.Lock()
CACHE_TTL = 300  # 5 minutos

class MultiTabSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Extraer SID
        sid = request.GET.get('sid') or request.POST.get('sid') or request.headers.get('X-SID')
        
        # 2. Inicializar atributos en request
        request.sid = sid
        request.user_data = None
        request.enterprise = None
        request.permissions = []

        # 3. Intentar cargar contexto si hay sesión
        if hasattr(request, 'session'):
            if 's' not in request.session:
                request.session['s'] = {}

            if sid and sid in request.session['s']:
                ctx = request.session['s'][sid]
                uid = ctx.get('user_id')
                eid = ctx.get('enterprise_id')
                if uid is not None and eid is not None:
                    self._load_full_context(request, uid, eid)
            elif not sid and 'user_id' in request.session and 'enterprise_id' in request.session:
                # Caso pestaña huérfana
                new_sid = secrets.token_hex(4)
                request.sid = new_sid
                request.session['s'][new_sid] = {
                    'user_id': request.session['user_id'],
                    'enterprise_id': request.session['enterprise_id']
                }
                request.session.modified = True
                self._load_full_context(request, request.session['user_id'], request.session['enterprise_id'])

        response = self.get_response(request)
        return response

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
                    return

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
                    return

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
                
                if user_lower == 'admin' or role_lower in ['admin', 'administrador'] or user_id == 1:
                    if 'all' not in request.permissions: request.permissions.append('all')

                # Guardar en Caché
                with PERMISSION_LOCK:
                    PERMISSION_CACHE[cache_key] = (now_ts, dict(request.user_data), list(request.permissions), dict(request.enterprise))

        except Exception as e:
            logger.error(f"Error loading session context: {e}")
