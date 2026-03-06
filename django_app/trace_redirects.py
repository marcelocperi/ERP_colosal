import requests

session = requests.Session()
response = session.get('http://127.0.0.1:8000/', allow_redirects=False)
print("GET / ->", response.status_code, response.headers.get('Location'))

response2 = session.get('http://127.0.0.1:8000/login/', allow_redirects=False)
print("GET /login/ ->", response2.status_code, response2.headers.get('Location'))

# let's try to post login
data = {
    'enterprise_id': '0',
    'username': 'superadmin',
    'password': '1'  # or maybe something else? 
    # we can see what the DB says
}
response3 = session.post('http://127.0.0.1:8000/login/', data=data, allow_redirects=False)
print("POST /login/ ->", response3.status_code, response3.headers.get('Location'))
