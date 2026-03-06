import os
import re

def migrate_template(src_path, dest_path):
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. url_for('ventas.xxx') -> {% url 'ventas:xxx' %}
    content = re.sub(r"url_for\('ventas\.([^']+)'\)", r"{% url 'ventas:\1' %}", content)
    # Handle optional arguments in url_for
    content = re.sub(r"url_for\('ventas\.([^']+)',\s*([^=]+)=([^)]+)\)", r"{% url 'ventas:\1' \3 %}", content)

    # 2. url_for('core.xxx') -> {% url 'core:\1' %}
    content = re.sub(r"url_for\('core\.([^']+)'\)", r"{% url 'core:\1' %}", content)

    # 3. format filters
    # format_currency -> floatformat:2
    content = content.replace('|format_currency', '|floatformat:2')
    
    # 4. JSON
    content = content.replace('|tojson', '|safe')

    # 5. g.user -> request.user_data
    content = content.replace('g.user', 'user_data')

    # 6. Static files
    # url_for('static', filename='...') -> {% static '...' %},
    content = re.sub(r"url_for\('static',\s*filename='([^']+)'\)", r"{% static '\1' %}", content)

    # Add load static if needed
    if '{% static' in content and '{% load static %}' not in content:
        content = "{% load static %}\n" + content

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Migrated {src_path} -> {dest_path}")

base_src = r"c:\Users\marce\Documents\GitHub\Colosal\ventas\templates\ventas"
base_dest = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas"

files = ['facturar.html'] #, 'nota_credito.html'] I'll see if nota_credito exists in templates

for f in files:
    src = os.path.join(base_src, f)
    dest = os.path.join(base_dest, f)
    if os.path.exists(src):
        migrate_template(src, dest)
    else:
        print(f"Source {src} does not exist.")
