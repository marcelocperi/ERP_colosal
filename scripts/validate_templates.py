
import re

def check_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    tokens = re.findall(r'\{%(.+?)%\}', content)
    stack = []
    errors = []

    for i, token in enumerate(tokens):
        parts = token.strip().split()
        if not parts: continue
        tag = parts[0]
        
        if tag == 'if':
            stack.append(('if', i, token))
        elif tag == 'for':
            stack.append(('for', i, token))
        elif tag == 'block':
            stack.append(('block', i, token))
        elif tag == 'endif':
            if not stack or stack[-1][0] != 'if':
                errors.append(f"Unexpected endif at token {i}: {token}")
            else:
                stack.pop()
        elif tag == 'endfor':
            if not stack or stack[-1][0] != 'for':
                errors.append(f"Unexpected endfor at token {i}: {token}")
            else:
                stack.pop()
        elif tag == 'endblock':
            if not stack or stack[-1][0] != 'block':
                errors.append(f"Unexpected endblock at token {i}: {token}")
            else:
                stack.pop()

    for s in stack:
        errors.append(f"Unclosed {s[0]} starting at token {s[1]}: {s[2]}")

    if errors:
        print(f"Errors in {file_path}:")
        for e in errors:
            print(f"  {e}")
    else:
        print(f"{file_path} is balanced.")

check_file(r'c:\Users\marce\Documents\GitHub\Colosal\django_app\templates\base.html')
check_file(r'c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\templates\ventas\perfil_cliente.html')
