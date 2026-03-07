"""
URL configuration for colosal_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from apps.core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('ventas/', include('apps.ventas.urls')),
    path('configuracion/', include('apps.configuracion.urls')),
    path('stock/', include('apps.stock.urls')),
    path('compras/', include('apps.compras.urls')),
    path('fondos/', include('apps.fondos.urls')),
    path('contabilidad/', include('apps.contabilidad.urls')),
    path('cobranzas/', include('apps.cobranzas.urls')),
    path('produccion/', include('apps.produccion.urls')),
    path('pricing/', include('apps.pricing.urls')),
    path('auditoria/', include('apps.auditoria.urls')),
    path('utilitarios/', include('apps.utilitarios.urls')),
    path('', views.home_redirect, name='home'),
]
