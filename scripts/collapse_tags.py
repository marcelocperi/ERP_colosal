
import os
import re

def fix_split_tags(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match tags that start and end but might have newlines inside
    # We want to collapse them into a single line
    new_content = re.sub(r'\{%(.+?)%\}', lambda m: "{% " + " ".join(m.group(1).split()) + " %}", content, flags=re.DOTALL)
    new_content = re.sub(r'\{\{(.+?)\}\}', lambda m: "{{ " + " ".join(m.group(1).split()) + " }}", new_content, flags=re.DOTALL)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

template_dir = r'c:\Users\marce\Documents\GitHub\Colosal\django_app'
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            if fix_split_tags(os.path.join(root, file)):
                print(f"Fixed split tags in: {file}")
