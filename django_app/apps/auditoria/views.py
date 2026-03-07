from django.shortcuts import render, redirect
from django.contrib import messages
from apps.core.decorators import login_required
from apps.core.db import get_db_cursor, dictfetchall

@login_required
def dashboard(request):
    """
    Dashboard principal de Seguridad y Auditoría.
    Muestra KPIs sobre estado de permisos de rol, últimos logs de seguridad y alertas de AFIP.
    """
    try:
        with get_db_cursor() as cursor:
            # Stats Generales
            cursor.execute("SELECT count(*) as roles_count FROM sys_roles WHERE enterprise_id = %s OR enterprise_id = 0", [request.user_data['enterprise_id']])
            roles_count = dictfetchall(cursor)[0]['roles_count']
            
            cursor.execute("SELECT count(*) as users_count FROM sys_users WHERE enterprise_id = %s OR enterprise_id = 0", [request.user_data['enterprise_id']])
            users_count = dictfetchall(cursor)[0]['users_count']
            
            # Obtener logs recientes (Si existiera la tabla de logs de usuarios, asumimos por ahora 'system_stats' o fall back)
            # Primero chequear si existe la vista o tabla de logs:
            try:
                cursor.execute("""
                    SELECT * FROM sys_activity_logs 
                    WHERE enterprise_id = %s 
                    ORDER BY id DESC LIMIT 10
                """, [request.user_data['enterprise_id']])
                recent_logs = dictfetchall(cursor)
            except Exception:
                recent_logs = [] # Failsafe si no está la tabla aún
            
        return render(request, 'auditoria/dashboard.html', {
            'roles_count': roles_count,
            'users_count': users_count,
            'recent_logs': recent_logs
        })
    except Exception as e:
        messages.error(request, f"Error cargando Auditoría: {e}")
        return redirect('core:home')

@login_required
def auditar_permisos(request):
    """
    Vista detallada de la matriz de Roles Vs. Permisos para revisar posibles escaladas de privilegios indeseadas (SoD).
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT p.code, p.description, p.module, 
                       GROUP_CONCAT(r.name) as roles_assigned
                FROM sys_permissions p
                LEFT JOIN sys_role_permissions rp ON p.id = rp.permission_id
                LEFT JOIN sys_roles r ON rp.role_id = r.id AND (r.enterprise_id = %s OR r.enterprise_id = 0)
                GROUP BY p.id
                ORDER BY p.module, p.code
            """, [request.user_data['enterprise_id']])
            matriz_permisos = dictfetchall(cursor)
            
            for perm in matriz_permisos:
                if perm['roles_assigned']:
                    perm['roles_list'] = perm['roles_assigned'].split(',')
                else:
                    perm['roles_list'] = []
            
        return render(request, 'auditoria/auditar_permisos.html', {'matriz_permisos': matriz_permisos})
    except Exception as e:
        messages.error(request, f"Error consultando permisos: {e}")
        return redirect('auditoria:dashboard')

@login_required
def logs_transaccionales(request):
    """
    Listado en bruto de todos los logs generados en el sistema (por ej: Errores 500 y Logs de login fallido).
    """
    try:
        with get_db_cursor() as cursor:
            # Se usa una tabla dummy si no existe, o crearemos la de sys_activity_logs luego
            cursor.execute("""
                SELECT 1
            """)
            logs = []
            
        return render(request, 'auditoria/logs_transaccionales.html', {'logs': logs})
    except Exception as e:
        messages.error(request, f"Error de bitácora: {e}")
        return redirect('auditoria:dashboard')

@login_required
def integridad(request):
    """
    Auditoría de consistencia de base de datos (AI auditor simulado por ahora o comprobación manual básica).
    """
    return render(request, 'auditoria/integridad.html')
