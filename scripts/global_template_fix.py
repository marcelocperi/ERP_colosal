
import os
import re

def fix_all_multiline_tags(text):
    # Fix {% ... %} tags
    text = re.sub(r'\{%(.+?)%\}', lambda m: "{% " + " ".join(m.group(1).split()) + " %}", text, flags=re.DOTALL)
    # Fix {{ ... }} tags
    text = re.sub(r'\{\{(.+?)\}\}', lambda m: "{{ " + " ".join(m.group(1).split()) + " }}", text, flags=re.DOTALL)
    return text

template_dir = r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas'

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            fixed_content = fix_all_multiline_tags(content)
            
            if fixed_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print(f"Fixed: {file}")
            else:
                print(f"No changes needed: {file}")

print("Global template scrub completed.")
