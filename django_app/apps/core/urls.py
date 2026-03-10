from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'core'

urlpatterns = [
    path('login.html', views.login_view, name='login'),
    path('login/', RedirectView.as_view(url='/login.html', permanent=True)),
    path('logout/', views.logout_view, name='logout'),
    # APIs
    path('api/georef/localidades/', views.api_get_localidades, name='api_get_localidades'),
    path('api/georef/calles/', views.api_get_calles, name='api_get_calles'),
    path('api/georef/cp/', views.api_get_cp, name='api_get_cp'),
    path('api/erp/puestos/', views.api_get_puestos, name='api_get_puestos'),
    path('api/erp/areas/', views.api_get_areas, name='api_get_areas'),
    # Assets / Logos
    path('sysadmin/enterprises/logo/raw/<int:logo_id>', views.get_logo_raw, name='get_logo_raw'),
    # QZ Tray Auth
    path('api/qz/cert', views.api_qz_cert, name='api_qz_cert'),
    path('api/qz/sign', views.api_qz_sign, name='api_qz_sign'),
]
