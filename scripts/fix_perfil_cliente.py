import os

file_path = r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\perfil_cliente.html'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Caso 1: {% if permissions ... %} multiline
    if "{% if 'gerente_ventas' in permissions or 'admin' in permissions or 'all' in" in line:
        new_lines.append(line.strip() + " permissions %}\n")
        continue
    if "permissions %}" in line and len(new_lines) > 0 and "permissions %}" in new_lines[-1]:
         # Ya lo unimos arriba
         continue
    if "permissions %}" in line and len(new_lines) > 0 and "{% if 'gerente_ventas' in permissions" in new_lines[-1]:
         # Evitar duplicar si ya se unió (aunque el strip() + " permissions %}" ya lo hace)
         continue
         
    new_lines.append(line)

# Un segundo pase para limpiar si quedó algo raro o para los otros tags
# Pero mejor hagamos un reemplazo de texto exacto de los bloques problematicos conocidos
content = "".join(lines)

# Fix 1
content = content.replace(
    "{% if 'gerente_ventas' in permissions or 'admin' in permissions or 'all' in\n                                            permissions %}",
    "{% if 'gerente_ventas' in permissions or 'admin' in permissions or 'all' in permissions %}"
).replace(
    "{% if 'gerente_ventas' in permissions or 'admin' in permissions or 'all' in\r\n                                            permissions %}",
    "{% if 'gerente_ventas' in permissions or 'admin' in permissions or 'all' in permissions %}"
)

# Fix 2
content = content.replace(
    "{% for imp in impuestos_lista %}<option value=\"{{ imp.id }}\">{{ imp.nombre }}</option>{% endfor\n                        %}",
    "{% for imp in impuestos_lista %}<option value=\"{{ imp.id }}\">{{ imp.nombre }}</option>{% endfor %}"
).replace(
    "{% for imp in impuestos_lista %}<option value=\"{{ imp.id }}\">{{ imp.nombre }}</option>{% endfor\r\n                        %}",
    "{% for imp in impuestos_lista %}<option value=\"{{ imp.id }}\">{{ imp.nombre }}</option>{% endfor %}"
)

# Fix 3
content = content.replace(
    "{% if\n                            c.id==pago_info.condicion_pago_id %}checked{% endif %}",
    "{% if c.id==pago_info.condicion_pago_id %}checked{% endif %}"
).replace(
    "{% if\r\n                            c.id==pago_info.condicion_pago_id %}checked{% endif %}",
    "{% if c.id==pago_info.condicion_pago_id %}checked{% endif %}"
)

# Fix 4 (Convenio)
content = content.replace(
    "{% if\n                                                cliente.es_convenio_multilateral %}checked{% endif %}",
    "{% if cliente.es_convenio_multilateral %}checked{% endif %}"
).replace(
    "{% if\r\n                                                cliente.es_convenio_multilateral %}checked{% endif %}",
    "{% if cliente.es_convenio_multilateral %}checked{% endif %}"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("perfil_cliente.html fixed successfully.")
