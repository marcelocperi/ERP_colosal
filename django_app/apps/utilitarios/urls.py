from django.urls import path
from . import views

app_name = 'utilitarios'

urlpatterns = [
    path('crons/', views.gestor_crons, name='gestor_crons'),
    path('crons/run/<int:cron_id>/', views.run_cron, name='run_cron'),
    path('crons/api/logs/<int:cron_id>/', views.get_cron_logs, name='get_cron_logs'),
    path('crons/save/', views.save_cron, name='save_cron'),
    path('crons/delete/<int:cron_id>/', views.delete_cron, name='delete_cron'),
]
