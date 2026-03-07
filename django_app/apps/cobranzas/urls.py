from django.urls import path
from . import views

app_name = 'cobranzas'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('cuenta-corriente/', views.cuenta_corriente, name='cuenta_corriente'),
    path('recibos/', views.listar_recibos, name='listar_recibos'),
    path('recibos/nuevo/', views.emitir_recibo, name='emitir_recibo'),
    path('ordenes/', views.listar_ordenes_cobro, name='listar_ordenes_cobro'),
]
