import re

target = r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\comprobante_impresion.html"
with open(target, "r", encoding="utf-8") as f:
    html = f.read()

# Fix impuestos loop and layout
start_imp = html.find("{% for imp in impuestos %}")
end_imp = html.find("{% endfor %}", start_imp) + len("{% endfor %}")

imp_block = """{% for imp in impuestos %}
                <div class="field" style="left: 20pt; top: {{ imp.y }}pt; font-size: 7.5pt;">Percepción de Ingresos Brutos</div>
                <div class="field" style="left: 180pt; top: {{ imp.y }}pt; font-size: 7.5pt; text-align: right; width: 100pt;">{{ imp.jurisdiccion }}</div>
                <div class="field" style="left: 300pt; top: {{ imp.y }}pt; font-size: 7.5pt; text-align: right; width: 80pt;">{{ imp.base_imponible|floatformat:2 }}</div>
                <div class="field" style="left: 390pt; top: {{ imp.y }}pt; font-size: 7.5pt; text-align: right; width: 50pt;">{{ imp.alicuota|floatformat:2 }} %</div>
                <div class="field" style="left: 480pt; top: {{ imp.y }}pt; font-size: 7.5pt; text-align: right; width: 100pt;">{{ imp.importe|floatformat:2 }}</div>
                {% endfor %}"""

if start_imp != -1 and end_imp != -1:
    html = html[:start_imp] + imp_block + html[end_imp:]

with open(target, "w", encoding="utf-8") as f:
    f.write(html)

print("Template fixed (5).")
