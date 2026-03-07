from django.urls import path
from . import views

app_name = 'pricing'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('lista/<int:lista_id>/', views.lista_detalle, name='lista_detalle'),
    path('reglas/guardar/', views.regla_guardar, name='regla_guardar'),
    path('lista/<int:id>/recalcular/', views.lista_recalcular, name='lista_recalcular'),
    path('lista/<int:id>/pendientes/', views.lista_pendientes, name='lista_pendientes'),
    path('propuestas/accion/', views.propuesta_accion, name='propuesta_accion'),
    path('todas_las_pendientes/', views.todas_las_pendientes, name='todas_las_pendientes'),
]
