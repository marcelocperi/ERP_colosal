import os, re

quart_path = r'c:\Users\marce\Documents\GitHub\Colosal\compras_quart_backup\templates\compras\perfil_proveedor.html'
django_path = r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\compras\templates\compras\perfil_proveedor.html'

with open(quart_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace url_for calls
content = re.sub(r"\{\{\s*url_for\('compras\.([a-zA-Z0-9_]+)'(?:,\s*id=proveedor\.id)?\)\s*\}\}", r"{% url 'compras:\1' proveedor.id %}", content)
content = content.replace("url_for('compras.proveedores')", "'{% url ''compras:proveedores'' %}'")
# For the case where it shouldn't replace it inside {{ }}, let's do more explicit replacement
# Ah, the quotes are annoying. Let's do string replacement
content = content.replace("{{ url_for('compras.proveedores') }}", "{% url 'compras:proveedores' %}")

# For query parameters or similar like tabla=..., item_id=...
content = re.sub(r"\{\{\s*url_for\('compras\.([a-zA-Z0-9_]+)',\s*tabla='([^']+)',\s*item_id=([a-z]\.id),\s*id=proveedor\.id\)\s*\}\}", 
                 r"{% url 'compras:\1' tabla='\2' item_id=\3 id=proveedor.id %}", content)

# For core APIs
content = re.sub(r"\{\{\s*url_for\('core\.([a-zA-Z0-9_]+)'\)\s*\}\}", r"{% url 'core:\1' %}", content)

# For static files
content = re.sub(r"\{\{\s*url_for\('static',\s*filename=([^\)]+)\)\s*\}\}", r"{% static \1 %}", content)

for jinja_loop in ['for d in direcciones', 'for c in contactos', 'for f in fiscales', 'for coef in coeficientes_cm']:
    content = content.replace(f'{{% {jinja_loop} %}}', f'{{% {jinja_loop} %}}').replace('{% else %}', '{% empty %}').replace('{% endfor %}', '{% endfor %}')

# Let's fix loop tags to empty directly if needed
# Actually just .replace('{% else %}', '{% empty %}') works inside loops, but what if there's an IF statement with an else?
# Let's be careful. Let's do a safe targeted replace
content = content.replace("{% else %}\n                                    <tr>\n                                        <td colspan=\"5\" class=\"text-center text-muted\">No hay direcciones", "{% empty %}\n                                    <tr>\n                                        <td colspan=\"5\" class=\"text-center text-muted\">No hay direcciones")
content = content.replace("{% else %}\n                                    <tr>\n                                        <td colspan=\"5\" class=\"text-center text-muted\">No hay contactos", "{% empty %}\n                                    <tr>\n                                        <td colspan=\"5\" class=\"text-center text-muted\">No hay contactos")
content = content.replace("{% else %}\n                                    <tr>\n                                        <td colspan=\"6\" class=\"text-center text-muted\">Sin datos fiscales", "{% empty %}\n                                    <tr>\n                                        <td colspan=\"6\" class=\"text-center text-muted\">Sin datos fiscales")
content = content.replace("{% else %}\n                                                    <tr>\n                                                        <td colspan=\"4\" class=\"text-center py-4 text-muted\">\n                                                            Aún no asignaste los coeficientes", "{% empty %}\n                                                    <tr>\n                                                        <td colspan=\"4\" class=\"text-center py-4 text-muted\">\n                                                            Aún no asignaste los coeficientes")


content = content.replace('{{ d|tojson|safe }}', '{{ d|safe }}')
content = content.replace('{{ c|tojson|safe }}', '{{ c|safe }}')
content = content.replace('{{ f|tojson|safe }}', '{{ f|safe }}')
content = content.replace('{{ "%.4f"|format(coef.coeficiente) }}', '{{ coef.coeficiente|floatformat:4 }}')

# Add {% load static %} if not present
if '{% load static %}' not in content:
    content = content.replace('{% block content %}', '{% load static %}\n{% block content %}')

with open(django_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Migration done")
