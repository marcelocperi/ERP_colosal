import datetime
from django.conf import settings

def inject_globals(request):
    """
    Equivalente al @app.context_processor inject_globals de Quart.
    Inyecta variables globales en el contexto de todos los templates.
    """
    # Los valores ahora vienen poblados por MultiTabSessionMiddleware
    user_data = getattr(request, 'user_data', None)
    permissions = getattr(request, 'permissions', [])
    enterprise = getattr(request, 'enterprise', None)
    sid = getattr(request, 'sid', '')
    
    # Carga dinámica del menú filtrado por permisos
    from .menu_loader import get_filtered_menu
    menu_structure = get_filtered_menu(permissions)
    
    return {
        'current_user': user_data,
        'enterprise': enterprise,
        'permissions': permissions,
        # 'csrf_token' lo maneja Django automáticamente, no lo inyectamos manualmente para evitar conflictos

        'sid': sid,
        'now': datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        'menu_structure': menu_structure,
        'settings': settings,
    }
