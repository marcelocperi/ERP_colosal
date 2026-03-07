
import os
import re

def thorough_fix(content):
    # 1. Collapse multiline tags
    content = re.sub(r'\{%(.+?)%\}', lambda m: "{% " + " ".join(m.group(1).split()) + " %}", content, flags=re.DOTALL)
    content = re.sub(r'\{\{(.+?)\}\}', lambda m: "{{ " + " ".join(m.group(1).split()) + " }}", content, flags=re.DOTALL)
    
    # 2. Add spaces around operators in {% ... %}
    # Regex to find operators not surrounded by spaces
    def add_spaces(match):
        inner = match.group(1)
        # Add spaces around ==, !=, >=, <=, >, < if missing
        inner = re.sub(r'([^=\!><\s])(==|!=|>=|<=|>|<)([^=\!><\s])', r'\1 \2 \3', inner)
        # Handle cases like x== y or x ==y
        inner = re.sub(r'([^=\!><\s])(==|!=|>=|<=|>|<)\s', r'\1 \2 ', inner)
        inner = re.sub(r'\s(==|!=|>=|<=|>|<)([^=\!><\s])', r' \1 \2', inner)
        return "{%" + inner + "%}"

    content = re.sub(r'\{%(.+?)%\}', add_spaces, content)

    # 3. Specific fix for known broken tags if they exist as literals
    # (Sometimes tags get messed up and partially rendered or interpreted as text)
    
    return content

template_dir = r'c:\Users\marce\Documents\GitHub\Colosal\django_app'

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                old_content = f.read()
            
            new_content = thorough_fix(old_content)
            
            if new_content != old_content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Fixed spaces/multiline in: {file}")

print("Template cleanup finished.")
