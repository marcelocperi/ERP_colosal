from django.urls import path
from . import views

app_name = 'recoleccion'

urlpatterns = [
    path('', views.index, name='index'),
    path('picking/', views.picking, name='picking'),
    path('inventario/', views.inventario, name='inventario'),
    path('campanias/', views.campanias, name='campanias'),
    path('recepcion/', views.recepcion, name='recepcion'),
    
    # APIs
    path('api/save_recuento/', views.save_recuento, name='api_save_recuento'),
    path('api/campania/<int:inv_id>/items/', views.api_get_items_campania, name='api_get_items_campania'),
    path('api/campania/<int:inv_id>/cerrar/', views.close_campania, name='api_close_campania'),
]
