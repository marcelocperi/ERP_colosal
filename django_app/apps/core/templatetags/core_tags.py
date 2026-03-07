from django import template
import json
from decimal import Decimal
from datetime import datetime, date

register = template.Library()

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

from django.urls import reverse
from django.templatetags.static import static

@register.simple_tag
def url_for(endpoint, **kwargs):
    try:
        # Manejar rutas estáticas
        if endpoint == 'static':
            return static(kwargs.get('filename', ''))
            
        # Convertir 'ventas.index' -> 'ventas:index'
        if '.' in endpoint:
            endpoint = endpoint.replace('.', ':')
        return reverse(endpoint, kwargs=kwargs)
    except Exception:
        return ""

@register.filter(name='tojson')
def tojson(value):
    return json.dumps(value, cls=CustomJSONEncoder)

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='replace_underscore')
def replace_underscore(value):
    if not isinstance(value, str):
        return value
    return value.replace('_', ' ')

@register.filter(name='percentage')
def percentage(value, arg):
    try:
        if float(arg) == 0:
            return 0
        return ((float(value) - float(arg)) / float(arg)) * 100
    except (ValueError, TypeError):
        return 0
