import re

with open(r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\views.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("cursor.fetchone()", "dictfetchone(cursor)")

with open(r"c:\Users\marce\Documents\GitHub\Colosal\django_app\apps\ventas\views.py", "w", encoding="utf-8") as f:
    f.write(text)
    
print("replaced!")
