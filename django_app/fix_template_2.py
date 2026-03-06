import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# Fix layout.items() -> layout.items
html = html.replace("layout.items()", "layout.items")

# Fix any remaining format or replace in items/impuestos
html = html.replace("|format(imp.base_imponible) | replace('.', ',')", "|floatformat:2")
html = html.replace("|format(imp.alicuota) | replace('.', ',')", "|floatformat:2")
html = html.replace("|format(imp.importe) | replace('.', ',')", "|floatformat:2")
html = html.replace("| replace('.', ',')", "|floatformat:2") # generic safety

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Template fixed again.")
