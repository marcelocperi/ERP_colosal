import os
import re
import json

def migrate_template(src_path, dest_path):
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. url_for('ventas.xxx') -> {% url 'ventas:xxx' %}
    content = re.sub(r"url_for\('ventas\.([^']+)'\)", r"{% url 'ventas:\1' %}", content)
    # Handle optional arguments in url_for
    content = re.sub(r"url_for\('ventas\.([^']+)',\s*([^=]+)=([^)]+)\)", r"{% url 'ventas:\1' \3 %}", content)

    # 2. url_for('core.xxx') -> {% url 'core:\1' %}
    content = re.sub(r"url_for\('core\.([^']+)'\)", r"{% url 'core:\1' %}", content)

    # 3. Inline if: {{ "a" if cond else "b" }} -> {% if cond %}a{% else %}b{% endif %}
    # This is tricky with regex if nested, but for simple cases:
    def replace_inline_if(match):
        val_true = match.group(1).strip("'").strip('"')
        cond = match.group(2)
        val_false = match.group(3).strip("'").strip('"')
        return f"{{% if {cond} %}}{val_true}{{% else %}}{val_false}{{% endif %}}"
    
    content = re.sub(r"\{\{\s*([^|]+)\s+if\s+([^|]+)\s+else\s+([^|]+)\s*\}\}", replace_inline_if, content)

    # 4. default and tojson
    # {{ var|default(False)|tojson }}
    content = content.replace('|default (false) | tojson', '|default:False|yesno:"true,false"')
    content = content.replace('|default (False) | tojson', '|default:False|yesno:"true,false"')
    content = content.replace('|tojson', '|safe')

    # 5. g.user -> request.user_data
    content = content.replace('g.user', 'user_data')

    # 6. Static files
    content = re.sub(r"url_for\('static',\s*filename='([^']+)'\)", r"{% static '\1' %}", content)

    if '{% static' in content and '{% load static %}' not in content:
        content = "{% load static %}\n" + content

    # 7. Multi-line {{ }} with if (sometimes found in the header)
    # This regex is a bit more aggressive
    def replace_complex_inline_if(match):
        content_in = match.group(1)
        if ' if ' in content_in and ' else ' in content_in:
             parts = re.split(r'\s+if\s+|\s+else\s+', content_in)
             if len(parts) == 3:
                val_true = parts[0].strip().strip("'").strip('"')
                cond = parts[1].strip()
                val_false = parts[2].strip().strip("'").strip('"')
                return f"{{% if {cond} %}}{val_true}{{% else %}}{val_false}{{% endif %}}"
        return match.group(0)

    content = re.sub(r"\{\{\s*([\s\S]+?)\s*\}\}", replace_complex_inline_if, content)

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Migrated {src_path} -> {dest_path}")

base_src = r"c:\Users\marce\Documents\GitHub\Colosal\ventas\templates\ventas"
base_dest = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas"

files = ['facturar.html', 'devolucion_solicitud.html']

for f in files:
    src = os.path.join(base_src, f)
    dest = os.path.join(base_dest, f)
    if os.path.exists(src):
        migrate_template(src, dest)
    else:
        print(f"Source {src} does not exist.")
