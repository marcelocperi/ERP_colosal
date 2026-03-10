from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Articulos
    path('articulos/', views.articulos, name='articulos'),
    path('articulos/guardar/', views.articulo_guardar, name='articulo_guardar'),
    path('articulos/importar/', views.articulos_importar, name='articulos_importar'),
    path('articulos/historial/<int:articulo_id>/', views.articulo_historial, name='articulo_historial'),
    
    # Movimientos
    path('movimientos/', views.movimientos_historial, name='movimientos_historial'),
    path('movimientos/nuevo/', views.movimiento_crear, name='movimiento_crear'),
    path('movimientos/detalle/<int:movimiento_id>/', views.movimiento_detalle, name='movimiento_detalle'),
    path('transferencias/', views.transferencias, name='transferencias'),
    
    # Maestros
    path('depositos/', views.depositos, name='depositos'),
    path('depositos/guardar/', views.deposito_guardar, name='deposito_guardar'),
    path('tipos/', views.tipos_articulo, name='tipos_articulo'),
    path('tipos/guardar/', views.tipo_articulo_guardar, name='tipo_articulo_guardar'),
    
    # APIs
    path('api/seguridad/<int:articulo_id>/', views.api_articulo_seguridad, name='api_articulo_seguridad'),
    path('api/get_by_code/', views.api_get_articulo_by_code, name='get_articulo_by_code'),

    # Ajustes
    path('ajustes/pendientes/', views.ajustes_pendientes, name='ajustes_pendientes'),
    path('ajustes/procesar/', views.ajuste_procesar, name='ajuste_procesar'),
]
