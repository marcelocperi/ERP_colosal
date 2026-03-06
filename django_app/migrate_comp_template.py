import os
import re

source = r"c:\Users\marce\Documents\GitHub\Colosal\ventas\templates\ventas\comprobante_impresion.html"
target_dir = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas"
target = os.path.join(target_dir, "comprobante_impresion.html")

os.makedirs(target_dir, exist_ok=True)

with open(source, "r", encoding="utf-8") as f:
    html = f.read()

# Replace Quart url_for pattern: {{ url_for('blueprint.view', id=1) }} to {% url 'blueprint:view' id %}
def regex_url(m):
    inner = m.group(1).strip()
    
    parts = inner.split(',')
    target = parts[0].strip().replace("'", "").replace('"', '')
    if '.' in target:
        target = target.replace('.', ':')
        
    args_list = []
    for arg in parts[1:]:
        arg = arg.strip()
        if '=' in arg:
            k, v = arg.split('=', 1)
            args_list.append(v.strip())
        else:
            args_list.append(arg)
            
    return f"{{% url '{target}' {' '.join(args_list)} %}}".strip()

# Regular expression to match {{ url_for(...) }}
html = re.sub(r'\{\{\s*url_for\(([^)]+)\)\s*\}\}', regex_url, html)

# Replace "{{ "%.2f" | format(c.importe_neto) }}" with "{{ c.importe_neto|floatformat:2 }}"
html = re.sub(r'\{\{\s*["\']%\.\d+f["\']\s*\|\s*format\(([^)]+)\)\s*\}\}', r'{{ \1|floatformat:2 }}', html)

# Replace "{{ "%05d" | format(c.punto_venta) }}" with "{{ c.punto_venta|stringformat:'05d' }}"
html = re.sub(r'\{\{\s*["\']%0?(\d+)d["\']\s*\|\s*format\(([^)]+)\)\s*\}\}', r'{{ \2|stringformat:"0\1d" }}', html)

# Replace "in ['001', '006', '011']" with explicit condition
html = html.replace("{% if c.tipo_comprobante in ['001', '006', '011'] %}", "{% if c.tipo_comprobante == '001' or c.tipo_comprobante == '006' or c.tipo_comprobante == '011' %}")

# Extra replacements if needed
html = html.replace('g.permissions', 'permissions')

with open(target, "w", encoding="utf-8") as f:
    f.write(html)
print("Template comprobantes.html copiado y migrado.")
