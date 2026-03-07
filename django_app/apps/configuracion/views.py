from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
from apps.core.decorators import login_required, permission_required
import secrets
import datetime
import logging

logger = logging.getLogger(__name__)

@login_required
def index(request):
    """Configuration Dashboard"""
    return render(request, 'configuracion/index.html')

@login_required
@permission_required('admin_users')
def usuarios(request):
    """User Management List"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Usuarios de la empresa
            cursor.execute("""
                SELECT u.id, u.username, u.email, r.name as role_name, u.created_at, u.role_id, u.must_change_password
                FROM sys_users u
                LEFT JOIN sys_roles r ON u.role_id = r.id AND r.enterprise_id = u.enterprise_id
                WHERE u.enterprise_id = %s
                ORDER BY u.username
            """, (eid,))
            users_list = dictfetchall(cursor)
            
            # Roles para el select (filtramos adminsys si no es superadmin)
            is_sysadmin = 'sysadmin' in request.permissions
            if is_sysadmin:
                cursor.execute("SELECT id, name FROM sys_roles WHERE enterprise_id = %s ORDER BY name", (eid,))
            else:
                cursor.execute("SELECT id, name FROM sys_roles WHERE enterprise_id = %s AND LOWER(name) != 'adminsys' ORDER BY name", (eid,))
            roles_list = dictfetchall(cursor)

        return render(request, 'configuracion/usuarios.html', {
            'system_users': users_list,
            'roles': roles_list
        })
    except Exception as e:
        messages.error(request, f"Error al cargar usuarios: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def usuario_crear(request):
    """Create a new system user"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        uname = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role_id = request.POST.get('role_id') or None
        must_change = 1 if request.POST.get('must_change_password') == 'on' else 0
        
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(password)
        
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sys_users (enterprise_id, username, email, password_hash, role_id, must_change_password)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (eid, uname, email, pwd_hash, role_id, must_change))
            messages.success(request, f"Usuario '{uname}' creado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al crear usuario: {e}")
            
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:usuarios')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def usuario_editar(request, user_id):
    """Update existing user"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        uname = request.POST.get('username')
        email = request.POST.get('email')
        role_id = request.POST.get('role_id') or None
        must_change = 1 if request.POST.get('must_change_password') == 'on' else 0
        new_password = request.POST.get('password', '').strip()

        try:
            with get_db_cursor() as cursor:
                if new_password:
                    from werkzeug.security import generate_password_hash
                    pwd_hash = generate_password_hash(new_password)
                    cursor.execute("""
                        UPDATE sys_users 
                        SET username=%s, email=%s, role_id=%s, must_change_password=%s, password_hash=%s
                        WHERE id=%s AND enterprise_id=%s
                    """, (uname, email, role_id, must_change, pwd_hash, user_id, eid))
                else:
                    cursor.execute("""
                        UPDATE sys_users 
                        SET username=%s, email=%s, role_id=%s, must_change_password=%s
                        WHERE id=%s AND enterprise_id=%s
                    """, (uname, email, role_id, must_change, user_id, eid))
            messages.success(request, "Usuario actualizado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al actualizar: {e}")

    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:usuarios')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def usuario_reset_attempts(request, user_id):
    """Reset recovery attempts for a user"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        try:
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE sys_users SET recovery_attempts = 0 WHERE id = %s AND enterprise_id = %s", (user_id, eid))
            messages.success(request, "Intentos de recuperación restablecidos.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:usuarios')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def usuario_reset_password(request, user_id):
    """Force password reset to default"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        DEFAULT_PASS = "Temporal123!"
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(DEFAULT_PASS)
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE sys_users 
                    SET password_hash = %s, must_change_password = 1, recovery_attempts = 0 
                    WHERE id = %s AND enterprise_id = %s
                """, (pwd_hash, user_id, eid))
            messages.info(request, f"Contraseña restablecida a '{DEFAULT_PASS}'. El usuario deberá cambiarla al ingresar.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:usuarios')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_roles')
def roles(request):
    """Roles and Permissions Management"""
    eid = request.user_data['enterprise_id']
    selected_role_id = request.GET.get('role_id')
    if selected_role_id == '': selected_role_id = None
    
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Listado de roles
            cursor.execute("SELECT id, name, description FROM sys_roles WHERE enterprise_id = %s ORDER BY name", (eid,))
            roles_list = dictfetchall(cursor)
            
            selected_role = None
            permissions_by_category = {}
            current_role_permissions = []
            
            if selected_role_id:
                cursor.execute("SELECT id, name, description FROM sys_roles WHERE id = %s AND enterprise_id = %s", (selected_role_id, eid))
                selected_role = dictfetchone(cursor)
                
                if selected_role:
                    # Permisos disponibles (filtramos SISTEMA si no es sysadmin)
                    is_sysadmin = 'sysadmin' in request.permissions
                    if is_sysadmin:
                        cursor.execute("SELECT id, code, description, category FROM sys_permissions WHERE enterprise_id IN (0, %s) ORDER BY category", (eid,))
                    else:
                        cursor.execute("""
                            SELECT id, code, description, category FROM sys_permissions 
                            WHERE enterprise_id IN (0, %s) AND (category != 'SISTEMA' OR category IS NULL) 
                            ORDER BY category
                        """, (eid,))
                    
                    all_perms = dictfetchall(cursor)
                    for p in all_perms:
                        cat = p['category'] or 'General'
                        if cat not in permissions_by_category: permissions_by_category[cat] = []
                        permissions_by_category[cat].append(p)
                    
                    # Permisos actuales del rol
                    cursor.execute("SELECT permission_id FROM sys_role_permissions WHERE role_id = %s AND enterprise_id = %s", (selected_role_id, eid))
                    current_role_permissions = [row['permission_id'] for row in dictfetchall(cursor)]

        return render(request, 'configuracion/roles.html', {
            'roles': roles_list,
            'selected_role': selected_role,
            'permissions_by_category': permissions_by_category,
            'current_role_permissions': current_role_permissions
        })
    except Exception as e:
        logger.error(f"Error in configuration.roles: {e}", exc_info=True)
        messages.error(request, f"Error al cargar roles: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_roles')
def role_crear(request):
    """Create new role"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        uid = request.user_data['id']
        name = request.POST.get('name')
        desc = request.POST.get('description')
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sys_roles (enterprise_id, name, description, user_id) 
                    VALUES (%s, %s, %s, %s)
                """, (eid, name, desc, uid))
            messages.success(request, f"Rol '{name}' creado.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:roles')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_roles')
def role_eliminar(request, role_id):
    """Delete role"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        try:
            with get_db_cursor() as cursor:
                # Evitar borrar roles críticos si fuera necesario
                cursor.execute("DELETE FROM sys_roles WHERE id = %s AND enterprise_id = %s", (role_id, eid))
            messages.success(request, "Rol eliminado.")
        except Exception as e:
            messages.error(request, f"No se puede eliminar: {e}")
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:roles')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_roles')
def role_actualizar_permisos(request, role_id):
    """Update permissions for a specific role"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        uid = request.user_data['id']
        perms = request.POST.getlist('permissions')
        
        try:
            with get_db_cursor() as cursor:
                # 1. Limpiar permisos previos
                cursor.execute("DELETE FROM sys_role_permissions WHERE role_id = %s AND enterprise_id = %s", (role_id, eid))
                
                # 2. Insertar nuevos
                for p_id in perms:
                    cursor.execute("""
                        INSERT INTO sys_role_permissions (enterprise_id, role_id, permission_id, user_id) 
                        VALUES (%s, %s, %s, %s)
                    """, (eid, role_id, p_id, uid))
                    
            messages.success(request, "Permisos actualizados correctamente.")
        except Exception as e:
            messages.error(request, str(e))
            
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:roles')
    return redirect(f"{url}?role_id={role_id}&sid={sid}")

@login_required
@permission_required('admin_users')
def empresa_fiscal(request):
    """Enterprise Fiscal Data View"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM sys_enterprises WHERE id = %s", (eid,))
            empresa = dictfetchone(cursor)
        return render(request, 'configuracion/empresa_fiscal.html', {'empresa': empresa})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def empresa_fiscal_guardar(request):
    """Save Enterprise Fiscal Data"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        # Recolectar datos del form (simplificado, asumiendo campos coinciden con DB)
        f = request.POST
        params = [
            f.get('nombre'), f.get('cuit'), f.get('domicilio'), f.get('condicion_iva'),
            f.get('ingresos_brutos'), f.get('iibb_condicion'), f.get('email'), 
            f.get('telefono'), f.get('lema'), eid
        ]
        
        try:
            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE sys_enterprises 
                    SET nombre=%s, cuit=%s, domicilio=%s, condicion_iva=%s, 
                        ingresos_brutos=%s, iibb_condicion=%s, email=%s, telefono=%s, lema=%s
                    WHERE id=%s
                """, tuple(params))
            messages.success(request, "Datos fiscales actualizados.")
        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")
            
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:empresa_fiscal')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def areas(request):
    """List areas"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM erp_areas WHERE enterprise_id = %s OR enterprise_id = 0 ORDER BY nombre", (eid,))
            areas_list = dictfetchall(cursor)
        return render(request, 'configuracion/areas.html', {'areas_list': areas_list})
    except Exception as e:
        messages.error(request, f"Error: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def area_crear(request):
    """Create new area"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        nombre = request.POST.get('nombre')
        color = request.POST.get('color', '#4e73df')
        icono = request.POST.get('icono', 'fas fa-folder')
        try:
            with get_db_cursor() as cursor:
                cursor.execute("INSERT INTO erp_areas (enterprise_id, nombre, color, icono, activo) VALUES (%s, %s, %s, %s, 1)", 
                               (eid, nombre, color, icono))
            messages.success(request, f"Área '{nombre}' creada.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:areas')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def area_editar(request, area_id):
    """Edit area"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        nombre = request.POST.get('nombre')
        color = request.POST.get('color')
        icono = request.POST.get('icono')
        try:
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE erp_areas SET nombre=%s, color=%s, icono=%s WHERE id=%s AND enterprise_id=%s", 
                               (nombre, color, icono, area_id, eid))
            messages.success(request, "Área actualizada.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:areas')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def area_eliminar(request, area_id):
    """Delete area (soft delete or check dependencies)"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        try:
            with get_db_cursor() as cursor:
                # Check for positions using this area
                cursor.execute("SELECT COUNT(*) as count FROM erp_puestos WHERE area = %s AND enterprise_id = %s", (area_id, eid))
                count = cursor.fetchone()[0] if not isinstance(cursor.fetchone(), dict) else cursor.fetchone()['count']
                # Wait, dictcursor logic
                cursor.execute("SELECT COUNT(*) as cnt FROM erp_puestos WHERE area = %s AND enterprise_id = %s", (area_id, eid))
                res = dictfetchone(cursor)
                if res and res['cnt'] > 0:
                    messages.error(request, "No se puede eliminar el área porque tiene puestos asociados.")
                else:
                    cursor.execute("DELETE FROM erp_areas WHERE id = %s AND enterprise_id = %s", (area_id, eid))
                    messages.success(request, "Área eliminada.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:areas')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def puestos(request):
    """List positions"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT p.*, a.nombre as area_nombre 
                FROM erp_puestos p
                LEFT JOIN erp_areas a ON p.area = a.id
                WHERE p.enterprise_id = %s 
                ORDER BY a.nombre, p.nombre
            """, (eid,))
            puestos_list = dictfetchall(cursor)
            
            cursor.execute("SELECT id, nombre FROM erp_areas WHERE enterprise_id = %s OR enterprise_id = 0 ORDER BY nombre", (eid,))
            areas_list = dictfetchall(cursor)
            
        return render(request, 'configuracion/puestos.html', {
            'puestos_list': puestos_list,
            'areas_list': areas_list
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def puesto_crear(request):
    """Create new position"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        nombre = request.POST.get('nombre')
        area_id = request.POST.get('area_id')
        try:
            with get_db_cursor() as cursor:
                cursor.execute("INSERT INTO erp_puestos (enterprise_id, nombre, area, activo) VALUES (%s, %s, %s, 1)", 
                               (eid, nombre, area_id))
            messages.success(request, f"Puesto '{nombre}' creado.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:puestos')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def puesto_editar(request, puesto_id):
    """Edit position"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        nombre = request.POST.get('nombre')
        area_id = request.POST.get('area_id')
        try:
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE erp_puestos SET nombre=%s, area=%s WHERE id=%s AND enterprise_id=%s", 
                               (nombre, area_id, puesto_id, eid))
            messages.success(request, "Puesto actualizado.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:puestos')
    return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def puesto_eliminar(request, puesto_id):
    """Delete position"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        try:
            with get_db_cursor() as cursor:
                cursor.execute("DELETE FROM erp_puestos WHERE id = %s AND enterprise_id = %s", (puesto_id, eid))
                messages.success(request, "Puesto eliminado.")
        except Exception as e:
            messages.error(request, str(e))
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:puestos')
    return redirect(f"{url}?sid={sid}")
@login_required
@permission_required('admin_users')
def security_logs(request):
    """List security logs from sys_security_logs or sys_audit"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # We try sys_security_logs which is the expected table for high-level events
            cursor.execute("""
                SELECT * FROM sys_security_logs 
                WHERE enterprise_id = %s 
                ORDER BY created_at DESC LIMIT 200
            """, (eid,))
            logs = dictfetchall(cursor)
        return render(request, 'configuracion/security_logs.html', {'logs': logs})
    except Exception as e:
        # If table doesn't exist yet, return empty list instead of crashing
        logger.warning(f"Could not fetch security logs: {e}")
        return render(request, 'configuracion/security_logs.html', {'logs': []})
def audit_permissions(request): return HttpResponse("Modulo en construccion")
def audit_integrity(request): return HttpResponse("Modulo en construccion")
def audit_certification(request): return HttpResponse("Modulo en construccion")
def ai_auditor(request): return HttpResponse("Modulo en construccion")
@login_required
@permission_required('admin_users')
def numeracion(request):
    """List and manage document numbering"""
    eid = request.user_data['enterprise_id']
    try:
        with get_db_cursor(dictionary=True) as cursor:
            # Get current numbering config
            cursor.execute("SELECT * FROM sys_enterprise_numeracion WHERE enterprise_id = %s ORDER BY entidad_tipo, entidad_codigo", (eid,))
            num_list = dictfetchall(cursor)
            
            # Get available document types for the select
            cursor.execute("SELECT codigo, nombre FROM sys_tipos_comprobante WHERE es_numerable = 1 ORDER BY nombre")
            tipos_comprobante = dictfetchall(cursor)
            
        return render(request, 'configuracion/numeracion.html', {
            'numeracion_list': num_list,
            'tipos_comprobante': tipos_comprobante
        })
    except Exception as e:
        messages.error(request, f"Error: {e}")
        sid = getattr(request, 'sid', '')
        url = reverse('configuracion:index')
        return redirect(f"{url}?sid={sid}")

@login_required
@permission_required('admin_users')
def numeracion_guardar(request):
    """Update or Create numbering entry"""
    if request.method == 'POST':
        eid = request.user_data['enterprise_id']
        tipo_entidad = request.POST.get('entidad_tipo', 'COMPROBANTE')
        codigo_entidad = request.POST.get('entidad_codigo')
        punto_venta = request.POST.get('punto_venta', 1)
        ultimo_numero = request.POST.get('ultimo_numero', 0)
        
        try:
            with get_db_cursor() as cursor:
                # Use a SELECT then INSERT/UPDATE pattern since we don't have ON DUPLICATE KEY reliably across all possible backends in this context 
                # although MySQL is likely, let's be safe. Actually, the project uses INSERT IGNORE elsewhere.
                cursor.execute("""
                    SELECT id FROM sys_enterprise_numeracion 
                    WHERE enterprise_id = %s AND entidad_tipo = %s AND entidad_codigo = %s AND punto_venta = %s
                """, (eid, tipo_entidad, codigo_entidad, punto_venta))
                row = dictfetchone(cursor)
                
                if row:
                    cursor.execute("""
                        UPDATE sys_enterprise_numeracion 
                        SET ultimo_numero = %s 
                        WHERE id = %s
                    """, (ultimo_numero, row['id']))
                else:
                    cursor.execute("""
                        INSERT INTO sys_enterprise_numeracion 
                        (enterprise_id, entidad_tipo, entidad_codigo, punto_venta, ultimo_numero)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (eid, tipo_entidad, codigo_entidad, punto_venta, ultimo_numero))
                    
            messages.success(request, "Configuración de numeración actualizada.")
        except Exception as e:
            messages.error(request, str(e))
            
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:numeracion')
    return redirect(f"{url}?sid={sid}")
@login_required
def api_areas(request):
    """API endpoint for areas"""
    eid = request.user_data['enterprise_id']
    with get_db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT id, nombre, color, icono FROM erp_areas WHERE enterprise_id = %s OR enterprise_id = 0 ORDER BY nombre", (eid,))
        return JsonResponse(dictfetchall(cursor), safe=False)

@login_required
def api_puestos(request):
    """API endpoint for positions"""
    eid = request.user_data['enterprise_id']
    area_id = request.GET.get('area_id')
    with get_db_cursor(dictionary=True) as cursor:
        query = "SELECT id, nombre FROM erp_puestos WHERE enterprise_id = %s"
        params = [eid]
        if area_id:
            query += " AND area = %s"
            params.append(area_id)
        query += " ORDER BY nombre"
        cursor.execute(query, params)
        return JsonResponse(dictfetchall(cursor), safe=False)
def role_init_sod(request): 
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:roles')
    return redirect(f"{url}?sid={sid}")
def role_revocar_permiso(request): 
    sid = getattr(request, 'sid', '')
    url = reverse('configuracion:roles')
    return redirect(f"{url}?sid={sid}")
