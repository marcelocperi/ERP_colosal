from django.urls import path
from . import views

app_name = 'fondos'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Cajas y Tesorería
    path('cajas/', views.cajas, name='cajas'),
    path('kpi-desembolsos/', views.kpi_desembolsos, name='kpi_desembolsos'),

    # Medios de Pago
    path('medios-pago/', views.medios_pago, name='medios_pago'),

    # Condiciones de Pago
    path('condiciones-pago/', views.condiciones_pago, name='condiciones_pago'),
    path('condiciones-mixtas/', views.condiciones_mixtas, name='condiciones_mixtas'),

    # Impuestos
    path('impuestos/', views.impuestos, name='impuestos'),

    # Bancos / Entidades
    path('bancos/', views.bancos, name='bancos'),
    path('bancos/sincronizar-bcra/', views.bancos_sincronizar_bcra, name='bancos_sincronizar_bcra'),
    path('bancos/sincronizar-billeteras/', views.bancos_sincronizar_billeteras, name='bancos_sincronizar_billeteras'),
    path('bancos/api/buscar/', views.bancos_api_buscar, name='bancos_api_buscar'),

    # Configuración Global Financiera
    path('configuracion/', views.configuracion_global, name='configuracion_global'),

    # Aprobaciones de OC para Tesorería
    path('aprobaciones/', views.aprobaciones, name='aprobaciones'),
    path('aprobaciones/<int:id>/', views.aprobar_po_detalle, name='aprobar_po_detalle'),
    path('aprobaciones/<int:id>/procesar/', views.post_aprobacion_po, name='post_aprobacion_po'),
]
