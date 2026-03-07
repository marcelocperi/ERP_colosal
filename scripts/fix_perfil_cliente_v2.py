
import os
import re

file_path = r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\perfil_cliente.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

def fix_all_multiline_tags(text):
    # Fix {% ... %} tags
    # regex matches {% followed by anything (including newlines) until %}, non-greedy
    text = re.sub(r'\{%(.+?)%\}', lambda m: "{% " + " ".join(m.group(1).split()) + " %}", text, flags=re.DOTALL)
    
    # Fix {{ ... }} tags
    text = re.sub(r'\{\{(.+?)\}\}', lambda m: "{{ " + " ".join(m.group(1).split()) + " }}", text, flags=re.DOTALL)
    
    return text

fixed_content = fix_all_multiline_tags(content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("perfil_cliente.html has been fully scrubbed of multiline tags.")
