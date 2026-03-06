import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colosal_django.settings')
django.setup()

from django.test import Client

client = Client()

# get login
r1 = client.get('/login/')
print("GET /login/ ->", r1.status_code)

# Get valid user from DB
from apps.core.db import get_db_cursor
with get_db_cursor() as c:
    c.execute("SELECT id, username, enterprise_id FROM sys_users LIMIT 1")
    row = c.fetchone()
    print("Test user:", row)

# Use arbitrary valid password logic? Oh wait, we don't know the password.
# Let's bypass login to directly set session!
session = client.session
session['user_id'] = 31
session['enterprise_id'] = 0
session['s'] = {'TESTSID': {'user_id': 31, 'enterprise_id': 0}}
session.save()

# now try to access dashboard WITH sid
r2 = client.get('/ventas/comprobantes/?sid=TESTSID')
print("GET /ventas/comprobantes/?sid=TESTSID ->", r2.status_code)

if r2.status_code == 200:
    import re
    m = re.search(r'/ventas/comprobante/ver/(\d+)/', r2.content.decode('utf-8'))
    if m:
        comp_id = m.group(1)
        r3 = client.get(f'/ventas/comprobante/ver/{comp_id}/?sid=TESTSID')
        print(f"GET /ventas/comprobante/ver/{comp_id}/?sid=TESTSID ->", r3.status_code)
        
        r4 = client.get(f'/ventas/remito/ver/{comp_id}/?sid=TESTSID')
        print(f"GET /ventas/remito/ver/{comp_id}/?sid=TESTSID ->", r4.status_code)
if r2.status_code in (301, 302):
    print("Redirect to:", r2.url)
    
# follow redirects manually
while r2.status_code in (301, 302):
    r2 = client.get(r2.url)
    print("GET", r2.request['PATH_INFO'], "->", r2.status_code)
    if r2.status_code in (301, 302):
        print("Redirect to:", r2.url)
