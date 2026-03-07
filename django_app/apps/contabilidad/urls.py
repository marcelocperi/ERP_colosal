from django.urls import path
from . import views

app_name = 'contabilidad'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Configuración Fiscal (Certificados AFIP)
    path('config-fiscal/', views.config_fiscal, name='config_fiscal'),

    # Libros IVA
    path('libro-iva-ventas/', views.libro_iva_ventas, name='libro_iva_ventas'),
    path('libro-iva-compras/', views.libro_iva_compras, name='libro_iva_compras'),

    # Padrones IIBB
    path('padrones-iibb/', views.padrones_iibb, name='padrones_iibb'),
    path('api/consultar-padron/<str:cuit>/', views.api_consultar_padron, name='api_consultar_padron'),
    path('importar-padron/<str:jurisdiccion>/', views.importar_padron, name='importar_padron'),

    # Exportaciones AFIP / SICORE
    path('exportar-afip/', views.exportar_afip, name='exportar_afip'),
    path('reporte-iibb/', views.reporte_iibb, name='reporte_iibb'),
    path('exportar-sicore/', views.exportar_sicore, name='exportar_sicore'),

    # Asientos y Plan de Cuentas
    path('plan-cuentas/', views.plan_cuentas, name='plan_cuentas'),
    path('libro-diario/', views.libro_diario, name='libro_diario'),
    path('asiento/<int:id>/', views.ver_asiento, name='ver_asiento'),
    path('centralizacion/', views.centralizacion, name='centralizacion'),

    # Sueldos (Nóminas Transitorias)
    path('sueldos/', views.sueldos_dashboard, name='sueldos_dashboard'),
    path('liquidar-sueldos/', views.liquidar_sueldos, name='liquidar_sueldos'),
    path('centralizar-sueldos/<int:id>/', views.centralizar_sueldos, name='centralizar_sueldos'),
]
