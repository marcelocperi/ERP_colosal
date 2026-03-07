import os
import re

def migrate_template(content):
    # 1. Convert {{ url_for('app.route', arg=val) }} to {% url 'app:route' val %}
    def replace_url_for(match):
        inner = match.group(1).strip()
        parts = inner.split(',', 1)
        route = parts[0].strip().strip("'").strip('"')
        django_route = route.replace('.', ':')
        
        args = ""
        if len(parts) > 1:
            arg_content = parts[1].strip()
            # Convert key=val to val or just keep key=val
            # Django expects arg=val or just val. 
            # In many cases it's id=... which works as positional if we just take val
            arg_content = re.sub(r'\w+\s*=\s*', r'', arg_content)
            args = " " + arg_content
            
        return f"{{% url '{django_route}'{args} %}}"

    content = re.sub(r"\{\{\s*url_for\((.*?)\)\s*\}\}", replace_url_for, content)

    # 2. Convert {{ url 'app:route' }} to {% url 'app:route' %}
    content = re.sub(r"\{\{\s*url\s+(['\"].*?['\"])\s*\}\}", r"{% url \1 %}", content)

    # 3. Handle Ternary: {{ A if B else C }}
    def replace_ternary(m):
        val1 = m.group(1).strip().strip("'").strip('"')
        cond = m.group(2).strip()
        val2 = m.group(3).strip().strip("'").strip('"')
        return f"{{% if {cond} %}}{val1}{{% else %}}{val2}{{% endif %}}"

    content = re.sub(r"\{\{\s*(['\"].*?['\"]|[^'\"{}]*?)\s+if\s+(.*?)\s+else\s+(['\"].*?['\"]|[^'\"{}]*?)\s*\}\}", replace_ternary, content)

    # 4. Global object g
    content = content.replace('g.user', 'current_user')
    content = content.replace('g.permissions', 'permissions')
    content = content.replace('g.enterprise', 'enterprise')
    content = re.sub(r'\bg\.', '', content)

    # 5. Math and Safe (common in this codebase for indentation)
    content = re.sub(r"\{\{.*?'&nbsp;'.*?\}\}", " ", content)

    # 6. .strftime
    content = re.sub(r"\.strftime\(['\"](.*?)['\"]\)", r"|date:'\1'", content)

    # 7. dict.get('key') -> dict.key
    content = re.sub(r"\.get\(['\"](\w+)['\"]\)", r".\1", content)
    
    # 8. .items() -> .items
    content = content.replace('.items()', '.items')

    return content

def process_dir(directory):
    if not os.path.exists(directory):
        return
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = migrate_template(content)
                    
                    if new_content != content:
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"Migrated: {path}")
                except Exception as e:
                    print(f"Error in {path}: {e}")

if __name__ == '__main__':
    # Apps templates
    process_dir('django_app/apps')
    # Core templates
    process_dir('django_app/templates')
