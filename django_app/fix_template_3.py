import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# Fix layout.items() -> layout.items (just in case)
html = html.replace("layout.items()", "layout.items")

# Fix `in` list in template
old_if = "{% if config.section in ['header', 'period', 'client', 'footer', 'totals'] %}"
new_if = "{% if config.section == 'header' or config.section == 'period' or config.section == 'client' or config.section == 'footer' or config.section == 'totals' %}"
html = html.replace(old_if, new_if)

# Fix namespace again if it survived
html = re.sub(r"{% set ns = namespace.*?%}", "", html)

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Template fixed again (3).")
