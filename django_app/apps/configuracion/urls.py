from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    # Dashboard / Index of Configuration
    path('', views.index, name='index'),
    
    # User Management
    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/crear/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/editar/<int:user_id>/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/reset-attempts/<int:user_id>/', views.usuario_reset_attempts, name='usuario_reset_attempts'),
    path('usuarios/reset-password/<int:user_id>/', views.usuario_reset_password, name='usuario_reset_password'),

    # Role Management
    path('roles/', views.roles, name='roles'),
    path('roles/crear/', views.role_crear, name='role_crear'),
    path('roles/eliminar/<int:role_id>/', views.role_eliminar, name='role_eliminar'),
    path('roles/actualizar-permisos/<int:role_id>/', views.role_actualizar_permisos, name='role_actualizar_permisos'),
    path('roles/revocar-permiso/', views.role_revocar_permiso, name='role_revocar_permiso'),
    path('roles/init-sod/', views.role_init_sod, name='role_init_sod'),

    # Enterprise / Fiscal Data
    path('empresa/fiscal/', views.empresa_fiscal, name='empresa_fiscal'),
    path('empresa/fiscal/guardar/', views.empresa_fiscal_guardar, name='empresa_fiscal_guardar'),

    # Areas & Positions
    path('areas/', views.areas, name='areas'),
    path('areas/crear/', views.area_crear, name='area_crear'),
    path('areas/editar/<int:area_id>/', views.area_editar, name='area_editar'),
    path('areas/eliminar/<int:area_id>/', views.area_eliminar, name='area_eliminar'),
    path('puestos/', views.puestos, name='puestos'),
    path('puestos/crear/', views.puesto_crear, name='puesto_crear'),
    path('puestos/editar/<int:puesto_id>/', views.puesto_editar, name='puesto_editar'),
    path('puestos/eliminar/<int:puesto_id>/', views.puesto_eliminar, name='puesto_eliminar'),

    # Security & Audit Logs
    path('seguridad/logs/', views.security_logs, name='security_logs'),
    path('seguridad/auditoria/permisos/', views.audit_permissions, name='audit_permissions'),
    path('seguridad/auditoria/integridad/', views.audit_integrity, name='audit_integrity'),
    path('seguridad/auditoria/certificacion/', views.audit_certification, name='audit_certification'),
    path('seguridad/auditoria/ai/', views.ai_auditor, name='ai_auditor'),

    # Numeration
    path('numeracion/', views.numeracion, name='numeracion'),
    path('numeracion/guardar/', views.numeracion_guardar, name='numeracion_guardar'),
    
    # API endpoints
    path('api/areas/', views.api_areas, name='api_areas'),
    path('api/puestos/', views.api_puestos, name='api_puestos'),
]
