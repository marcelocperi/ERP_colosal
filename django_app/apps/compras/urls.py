from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    # Dashboard de Compras
    path('dashboard/', views.dashboard, name='dashboard'),

    # Proveedores
    path('proveedores/', views.proveedores, name='proveedores'),
    path('proveedores/nuevo/', views.nuevo_proveedor, name='nuevo_proveedor'),
    path('proveedores/editar/<int:id>/', views.editar_proveedor, name='editar_proveedor'),
    path('proveedores/perfil/<int:id>/', views.perfil_proveedor, name='perfil_proveedor'),

    # Órdenes de Compra
    path('ordenes/', views.ordenes, name='ordenes'),
    path('ordenes/nueva/', views.orden_nueva, name='orden_nueva'),
    path('ordenes/<int:id>/', views.orden_detalle, name='orden_detalle'),

    # Cotizaciones (RFQ)
    path('cotizaciones/', views.cotizaciones, name='cotizaciones'),
    path('cotizaciones/<int:id>/', views.cotizacion_detalle, name='cotizacion_detalle'),

    # Solicitudes de Reposición (NP)
    path('solicitudes/', views.solicitudes_lista, name='solicitudes_lista'),

    # Tablero de Reposición
    path('reposicion/', views.reposicion_dashboard, name='reposicion_dashboard'),

    # Comprobantes de Compra (Facturas recibidas)
    path('comprobantes/', views.comprobantes, name='comprobantes'),
    path('facturar/', views.facturar, name='facturar'),

    # Alertas
    path('alertas-detalle/', views.alertas_detalle, name='alertas_detalle'),

    # Recepción a Ciegas
    path('recepcion-ciega/', views.recepcion_ciega_list, name='recepcion_ciega_list'),

    # Aprobaciones
    path('aprobaciones/', views.aprobaciones, name='aprobaciones'),
    path('aprobaciones/<int:id>/', views.aprobar_po_detalle, name='aprobar_po_detalle'),

    # Órdenes de Pago
    path('ordenes-pago/', views.ordenes_pago, name='ordenes_pago'),
    path('pagar/', views.pagar, name='pagar'),

    # APIs
    path('api/reposicion/generar-np/', views.api_reposicion_generar_np, name='api_reposicion_generar_np'),
    path('api/reposicion/generar-cotizacion/', views.api_reposicion_generar_cotizacion, name='api_reposicion_generar_cotizacion'),
    path('api/reposicion/rechazar/', views.api_reposicion_rechazar, name='api_reposicion_rechazar'),
    path('api/proveedor/<int:id>/audit/', views.api_proveedor_audit, name='api_proveedor_audit'),
    path('api/solicitud/<int:id>/cotizar/', views.api_solicitud_cotizar, name='api_solicitud_cotizar'),

    path('proveedores/eliminar-detalle/<str:tabla>/<int:item_id>/<int:id>/', views.eliminar_detalle, name='eliminar_detalle'),
    path('proveedores/toggle-convenio/<int:id>/', views.toggle_convenio, name='toggle_convenio'),
    path('proveedores/agregar-cm05/<int:id>/', views.agregar_cm05, name='agregar_cm05'),
    path('proveedores/upload-cm05/<int:id>/', views.upload_cm05, name='upload_cm05'),
    path('proveedores/agregar-direccion/<int:id>/', views.agregar_direccion, name='agregar_direccion'),
    path('proveedores/agregar-contacto/<int:id>/', views.agregar_contacto, name='agregar_contacto'),
    path('proveedores/agregar-fiscal/<int:id>/', views.agregar_fiscal, name='agregar_fiscal'),
    path('ordenes/autorizar/<int:id>/', views.autorizar_orden, name='autorizar_orden'),
    path('ordenes/rechazar/<int:id>/', views.rechazar_orden, name='rechazar_orden'),
    path('ordenes/pdf/<int:id>/', views.pdf_orden, name='pdf_orden'),
    path('cotizaciones/aprobar/<int:id>/', views.aprobar_cotizacion, name='aprobar_cotizacion'),

]
