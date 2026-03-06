import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# Replace dict.get('key') with dict.key
# e.g., vals.get('tipo_comprobante_nombre') -> vals.tipo_comprobante_nombre
# e.g., vals.get('tipo_comprobante_nombre', 'Default') -> vals.tipo_comprobante_nombre|default:'Default'

def replace_get(m):
    obj = m.group(1)
    key = m.group(2).strip("'\"")
    default_val = m.group(4)
    if default_val:
        return f"{obj}.{key}|default:{default_val.strip()}"
    return f"{obj}.{key}"

html = re.sub(r'([a-zA-Z0-9_]+)\.get\((["\'][a-zA-Z0-9_]+["\'])(,\s*([^)]+))?\)', replace_get, html)

# Also fix `loop.index` to `forloop.counter` if any
html = html.replace('loop.index', 'forloop.counter')

# Also fix `layout['empresa.color_1']` -> `layout.empresa.color_1` Wait, Django doesn't allow dots in keys?
# Actually, the python object has `layout['empresa.color_1']`. In django template, you can't access keys with dots.
# Let's see if that's a problem later.

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Fixed get()")
