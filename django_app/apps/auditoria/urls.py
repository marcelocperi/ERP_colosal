from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('permisos/', views.auditar_permisos, name='auditar_permisos'),
    path('logs/', views.logs_transaccionales, name='logs_transaccionales'),
    path('integridad/', views.integridad, name='integridad'),
]
