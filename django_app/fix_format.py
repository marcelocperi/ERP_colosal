import re

fp = r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\compras\templates\compras\perfil_proveedor.html'
with open(fp, 'r', encoding='utf-8') as f:
    c = f.read()

# Replace format filter for CM05 coeficientes
c = re.sub(r'\{\{\s*[\'\"]%\.[0-9]+f[\'\"]\s*\|\s*format\(([^)]+)\)\s*\}\}', r'{{ \1|floatformat:4 }}', c)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(c)
