import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# Replace vals.get(name, '') with config.value
html = html.replace("{{ vals.get(name, '') }}", "{{ config.value }}")

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Template fixed (4).")
