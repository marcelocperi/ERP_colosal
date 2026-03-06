import os
import re

def fix_django_template(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix the broken {% if %} replacements from previous script
    # e.g. {% if es_nota_credito %}bg-danger' if es_nota_credito else 'bg-gradient-primary' }}
    content = re.sub(r"\{% if ([^%]+) %\}([^']*)' if \1 else '([^']*)' \}\}", r"{% if \1 %}\2{% else %}\3{% endif %}", content)

    # Fix: {{ 'val_true' if cond else 'val_false' }}
    # Pattern: {{ '([^']+)' if ([^ ]+) else '([^']+)' }}
    content = re.sub(r"\{\{\s*'([^']+)'\s+if\s+([^\s}]+)\s+else\s+'([^']+)'\s*\}\}", r"{% if \2 %}\1{% else %}\3{% endif %}", content)
    
    # Fix: {{ "val_true" if cond else "val_false" }}
    content = re.sub(r'\{\{\s*"([^"]+)"\s+if\s+([^\s}]+)\s+else\s+"([^"]+)"\s*\}\}', r"{% if \2 %}\1{% else %}\3{% endif %}", content)

    # Fix: {{ 'selected' if item.id == other.id }}
    content = re.sub(r"\{\{\s*'selected'\s+if\s+([^ ]+)\s*==\s*([^ }]+)\s*\}\}", r"{% if \1 == \2 %}selected{% endif %}", content)

    # Fix format filter: {{ "%04d-%08d"|format(a, b) }}
    # Simple replacement for this specific one:
    content = re.sub(r'\{\{\s*"%04d-%08d"\|format\(([^,]+),\s*([^)]+)\)\s*\}\}', r"\1|stringformat:'04d'-\2|stringformat:'08d'", content)
    # Actually Django doesn't have a direct equivalent for multiline format like that easily.
    # Better: {{ a|stringformat:"04d" }}-{{ b|stringformat:"08d" }}
    content = re.sub(r'\{\{\s*"%04d-%08d"\|format\(([^,]+),\s*([^)]+)\)\s*\}\}', r'{{ \1|stringformat:"04d" }}-{{ \2|stringformat:"08d" }}', content)

    # Fix: {{ "%.2f"|format(pago.importe) }}
    content = re.sub(r'\{\{\s*"%.2f"\|format\(([^)]+)\)\s*\}\}', r'{{ \1|floatformat:2 }}', content)

    # Fix tojson
    content = content.replace('| tojson', '|safe')
    content = content.replace('|tojson', '|safe')

    # Fix the weird URL replacements: {{ {% url ... %} }}
    content = content.replace('{{ {% url', '{% url')
    content = content.replace('%} }}', '%}')

    # Fix some specific weirdness in facturar.html
    # class="card-header {% if es_nota_credito %}bg-danger' if es_nota_credito else 'bg-gradient-primary' }}
    # The first regex should have caught it, but if not:
    content = content.replace("bg-danger' if es_nota_credito else 'bg-gradient-primary' }}", "bg-danger{% else %}bg-gradient-primary{% endif %}")

    # Fix Nueva Nota de Crédito block
    # {{ 'Nueva Nota de Crédito (Devolución){% else %}Nueva Factura de Venta' }}
    content = content.replace("{{ 'Nueva Nota de Crédito (Devolución){% else %}Nueva Factura de Venta' }}", "{% if es_nota_credito %}Nueva Nota de Crédito (Devolución){% else %}Nueva Factura de Venta{% endif %}")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed {file_path}")

files = [
    r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\facturar.html",
    r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\devolucion_solicitud.html"
]

for f in files:
    fix_django_template(f)
