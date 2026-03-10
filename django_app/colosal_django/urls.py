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
from apps.ventas import api_views as ventas_api

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
    path('recoleccion/', include('apps.recoleccion.urls')),
    path('', views.home_redirect, name='home'),

    # API endpoints at root level - the JS frontend calls these without /ventas/ prefix
    path('api/ventas/cliente/<int:id>/detalle', ventas_api.api_cliente_detalle, name='root_api_cliente_detalle'),
    path('api/ventas/cliente/<int:id>/logistica', ventas_api.api_cliente_logistica, name='root_api_cliente_logistica'),
    path('api/ventas/cliente/<int:id>/finanzas', ventas_api.api_cliente_finanzas, name='root_api_cliente_finanzas'),
    path('api/ventas/cliente/<int:id>/saldo', ventas_api.api_cliente_saldo, name='root_api_cliente_saldo'),
    path('api/ventas/cliente/<int:id>/condiciones', ventas_api.api_cliente_condiciones, name='root_api_cliente_condiciones'),
    path('api/ventas/articulos/buscar', ventas_api.api_articulos_buscar, name='root_api_articulos_buscar'),
    path('api/ventas/fiscal/allowed-docs', ventas_api.api_ventas_fiscal_allowed_docs, name='root_api_fiscal_allowed_docs'),
    path('api/ventas/afip/consultar/<str:cuit>', ventas_api.api_afip_consultar, name='root_api_afip_consultar'),
]
