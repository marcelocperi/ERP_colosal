import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Remove set ejemplares
html = re.sub(r"{% set ejemplares = \[.*?\] %}", "", html)

# 2. Hardcode headers
headers_html = """        <div class="field" style="left: 15pt; top: 279pt; width: 40pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Código</div>
        <div class="field" style="left: 55pt; top: 279pt; width: 141pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Producto / Servicio</div>
        <div class="field" style="left: 196pt; top: 279pt; width: 65pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Cantidad</div>
        <div class="field" style="left: 261pt; top: 279pt; width: 43pt; text-align: center; font-weight: bold; font-size: 7.5pt;">U. Medida</div>
        <div class="field" style="left: 304pt; top: 279pt; width: 80pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Precio Unit.</div>
        <div class="field" style="left: 384pt; top: 279pt; width: 32pt; text-align: center; font-weight: bold; font-size: 7.5pt;">% Bonif</div>
        <div class="field" style="left: 416pt; top: 279pt; width: 73pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Imp. Bonif.</div>
        <div class="field" style="left: 489pt; top: 279pt; width: 92pt; text-align: center; font-weight: bold; font-size: 7.5pt;">Subtotal</div>"""

html = re.sub(r"{% set headers = \[.*?\] %}\s*{% for h in headers %}.*?{% endfor %}", headers_html, html, flags=re.DOTALL)

# 3. Replace items logic
start_items = html.find("<!-- ITEMS DETALLE -->")
end_items = html.find("<!-- OTROS TRIBUTOS")

items_block = """<!-- ITEMS DETALLE -->
        {% for d in detalles %}
        <div class="field" style="left: 15pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 40pt; text-align: center;">
            {{ d.articulo_id|default:forloop.counter }}
        </div>
        <div class="field" style="left: 57pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 138pt; overflow: hidden; white-space: nowrap;">
            {{ d.desc_line }}
        </div>
        {% if d.cantidad %}
        <div class="field" style="left: 196pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 65pt; text-align: right; padding-right: 5pt;">
            {{ d.cantidad|floatformat:2 }}
        </div>
        <div class="field" style="left: 261pt; top: {{ d.y }}pt; font-size: 7pt; width: 43pt; text-align: center;">
            unidades
        </div>
        <div class="field" style="left: 304pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 80pt; text-align: right; padding-right: 5pt;">
            {{ d.precio_unitario|floatformat:2 }}
        </div>
        <div class="field" style="left: 384pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 32pt; text-align: center;">
            0.00
        </div>
        <div class="field" style="left: 416pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 73pt; text-align: right; padding-right: 5pt;">
            0.00
        </div>
        <div class="field" style="left: 489pt; top: {{ d.y }}pt; font-size: 7.5pt; width: 92pt; text-align: right; padding-right: 5pt; font-weight: bold; z-index: 50;">
            {{ d.subtotal_total|floatformat:2 }}
        </div>
        {% endif %}
        {% endfor %}
"""

if start_items != -1 and end_items != -1:
    html = html[:start_items] + items_block + html[end_items:]

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Template fixed.")
