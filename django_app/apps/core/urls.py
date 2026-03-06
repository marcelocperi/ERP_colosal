from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # APIs
    path('api/georef/localidades/', views.api_get_localidades, name='api_get_localidades'),
    path('api/georef/calles/', views.api_get_calles, name='api_get_calles'),
    path('api/georef/cp/', views.api_get_cp, name='api_get_cp'),
    path('api/erp/puestos/', views.api_get_puestos, name='api_get_puestos'),
    path('api/erp/areas/', views.api_get_areas, name='api_get_areas'),
]
