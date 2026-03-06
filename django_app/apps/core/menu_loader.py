import json
import logging
from pathlib import Path
from django.urls import reverse, NoReverseMatch
from django.conf import settings

logger = logging.getLogger(__name__)

def load_menu_structure():
    """Carga la estructura del menú desde el archivo JSON"""
    # Buscamos el archivo en la carpeta .agent de la raíz del proyecto
    menu_file = Path(settings.BASE_DIR).parent / '.agent' / 'menu_structure.json'
    
    try:
        with open(menu_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('menu_tree', {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error cargando menu_structure.json: {e}")
        return {}

def has_permission(permission_name, user_permissions):
    """
    Verifica si el usuario tiene un permiso específico.
    Copia fiel de la lógica de Quart.
    """
    if not user_permissions:
        return False
    
    # Marcador especial en el JSON: "permission": "all" → visible para todos
    if permission_name == 'all':
        return True
    
    # Sysadmin o admin local tiene todos los permisos
    if 'all' in user_permissions or 'sysadmin' in user_permissions:
        return True
    
    return permission_name in user_permissions

def get_filtered_menu(user_permissions):
    """
    Carga y filtra el menú según los permisos del usuario.
    Retorna la estructura lista para el template.
    """
    menu_structure = load_menu_structure()
    filtered_menu = {}
    
    for category_name, category_data in menu_structure.items():
        processed_modules = []
        for module in category_data.get('modules', []):
            module_copy = module.copy()
            module_copy['has_access'] = has_permission(module.get('permission', 'none'), user_permissions)
            
            # Convertir formato Flask/Quart 'app.route' a Django 'app:route'
            django_route = module['route'].replace('.', ':')
            module_copy['route'] = django_route
            
            try:
                # Intentar resolver la URL
                module_copy['url'] = reverse(django_route)
            except NoReverseMatch:
                # Si no existe (aún no migrado), URL nula para que el template maneje el candado
                module_copy['url'] = None
                
            processed_modules.append(module_copy)
            
        filtered_menu[category_name] = {
            **category_data,
            'modules': processed_modules
        }
    
    return filtered_menu
