from django.urls import path
from . import views

app_name = 'produccion'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('overhead-templates/', views.overhead_templates, name='overhead_templates'),
    path('overhead-templates/api/save/', views.api_save_overhead_template, name='api_save_overhead_template'),
    path('overhead-templates/<int:template_id>/api/detalles/', views.api_get_overhead_details, name='api_get_overhead_details'),
    path('documentos/', views.documentos, name='documentos'),
    path('proyectos/', views.proyectos, name='proyectos'),
    path('bandeja-costos/', views.bandeja_costos, name='bandeja_costos'),
    path('api/costeo/<int:propuesta_id>/aprobar/', views.api_aprobar_costeo, name='api_aprobar_costeo'),
    path('api/costeo/<int:propuesta_id>/rechazar/', views.api_rechazar_costeo, name='api_rechazar_costeo'),
]
