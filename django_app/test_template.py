import os
import django
from django.template.loader import render_to_string
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colosal_django.settings")
django.setup()

try:
    context = {
        'enterprise': {'nombre': 'Test'},
        'current_user': {'role_name': 'Admin', 'username': 'admin'},
        'request': type('MockRequest', (), {'path': '/ventas/dashboard/', 'session': {}})(),
        'permissions': ['all'],
        'messages': []
    }
    html = render_to_string('ventas/dashboard.html', context)
    print("SUCCESS, template rendered correctly!")
except Exception as e:
    import traceback
    traceback.print_exc()
