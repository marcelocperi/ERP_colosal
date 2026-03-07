from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/nuevo/', views.nuevo_cliente, name='nuevo_cliente'),
    path('clientes/perfil/<int:id>/', views.perfil_cliente, name='perfil_cliente'),
    path('clientes/editar/<int:id>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar-detalle/<str:tabla>/<int:item_id>/<int:cliente_id>/', views.eliminar_detalle, name='eliminar_detalle'),
    path('clientes/solicitar-cta-cte/<int:id>/', views.solicitar_cta_cte, name='solicitar_cta_cte'),
    path('clientes/aprobar-cta-cte/<int:id>/', views.aprobar_cta_cte, name='aprobar_cta_cte'),
    path('clientes/toggle-convenio/<int:id>/', views.toggle_convenio, name='toggle_convenio'),
    path('clientes/agregar-cm05/<int:id>/', views.agregar_cm05, name='agregar_cm05'),
    path('clientes/upload-cm05/<int:id>/', views.upload_cm05, name='upload_cm05'),
    path('clientes/agregar-direccion/<int:id>/', views.agregar_direccion, name='agregar_direccion'),
    path('clientes/agregar-contacto/<int:id>/', views.agregar_contacto, name='agregar_contacto'),
    path('clientes/agregar-fiscal/<int:id>/', views.agregar_fiscal, name='agregar_fiscal'),
    path('clientes/solicitar-condicion-pago/<int:id>/', views.solicitar_condicion_pago, name='solicitar_condicion_pago'),
    path('clientes/aprobar-condicion-pago/<int:id>/', views.aprobar_condicion_pago, name='aprobar_condicion_pago'),
    path('clientes/habilitar-condiciones-pago/<int:id>/', views.habilitar_condiciones_pago, name='habilitar_condiciones_pago'),
    path('comprobantes/', views.comprobantes, name='comprobantes'),
    path('facturar/', views.facturar, name='facturar'),
    path('procesar-factura/', views.procesar_factura, name='procesar_factura'),
    path('comprobante/ver/<int:id>/', views.ver_comprobante, name='ver_comprobante'),
    path('comprobante/<int:id>/pdf/', views.descargar_pdf_comprobante, name='comprobante_pdf'),
    path('remito/ver/<int:id>/', views.ver_remito, name='ver_remito'),
    path('nota_credito/<int:factura_id>/', views.nota_credito, name='nota_credito'),
    path('devolucion-solicitar/', views.devolucion_solicitar, name='devolucion_solicitar'),
    path('comprobante/<int:id>/reenviar/', views.reenviar_comprobante, name='reenviar_comprobante'),
]
