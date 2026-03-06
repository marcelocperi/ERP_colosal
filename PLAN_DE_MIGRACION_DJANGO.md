# Plan de Migración de Quart a Django - Proyecto Colosal

## 1. Refactorización de SQL (core/routes.py)

Se han revisado todas las consultas en `core/routes.py` para cumplir con la directiva de **nombres completos** y **sin alias de tabla** (ej: `sys_users` en lugar de `u`).

- Consultas de Usuarios, Roles y Permisos actualizadas.
- Registros de Seguridad y Auditoría actualizados.
- Se mantienen alias descriptivos solo en casos de *self-join* indispensables (ej: `sys_users_actor`).

## 2. Migración a Django (App Ventas - Módulo de Facturación)

### Perfil de Cliente
- **Template:** Migrado a `django_app/apps/ventas/templates/ventas/perfil_cliente.html`.
  - Implementación de **tabs horizontales** de alto rendimiento.
  - Integración de modales para todas las secciones (Ficha, Sedes, Contactos, Fiscal, CM05, Pago, Cta Cte).
- **Vistas:** Migradas a `django_app/apps/ventas/views.py`.
  - Soporte completo para persistencia (Edit, Delete, Add, Upload).

### Facturación y Notas de Crédito
- **Emisión de Comprobantes:** Migradas las vistas `facturar` y `procesar_factura`.
  - Soporte para Facturas A, B, C y Notas de Crédito correspondientes.
  - Resolución automática de tipos de comprobante vía `BillingService.get_nc_type`.
  - Integración con Cta. Cte. y límites de crédito dinámicos.
- **Visualización e Impresión (Direct Print):**
  - Implementación de `ver_comprobante` y `ver_remito` con diseño premium.
  - Cálculo de coordenadas `y` dinámicas para evitar desbordes en layouts A4 fijos.
  - Integración de **QZ Tray** para impresión directa a USB.
- **Servicios Fiscales (AFIP):**
  - `AfipService`: Adaptado para Django con soporte para simulación de CAE en desarrollo.
  - `BarcodeService`: Generación de **Códigos QR de AFIP** y **Códigos de Barras ITF** (base64).
  - `NumerationService`: Resolución concurrente de números de comprobante.

## 3. Infraestructura Core (Django)

- **Middleware:** `MultiTabSessionMiddleware` implementado para soportar múltiples pestañas con SIDs independientes.
- **Context Processors:** Inyección global de `current_user`, `enterprise`, `permissions`, `sid` y `menu_structure`.
- **APIs:** Implementación de endpoints en `core/views.py` para Localidades, Calles, CP, Puestos y Áreas.

## 4. Estado de la Migración y Próximos Pasos

### Finalizado ✅
- [X] Migrar Perfil de Cliente completo.
- [X] Migrar Listado de Comprobantes de Ventas con filtros avanzados.
- [X] Implementar Emisión de Facturas y Notas de Crédito (Lógica Billing + AFIP).
- [X] Generación de Códigos QR y Barras de AFIP.
- [X] Layouts de Impresión (Factura, Remito) con coordenadas dinámicas.

### Pendiente ⏳
- [ ] **Generación de PDFs en Servidor:** Implementar visualización/descarga de PDF real (.pdf) usando `xhtml2pdf` o `reportlab`.
- [ ] **Certificados de AFIP Reales:** Configurar conexión zeep para producción/homologación real una vez estabilizada la app.
- [ ] **Módulo de Stock:** Migrar ingresos, egresos, ajustes y consultas de stock.
- [ ] **Módulo de Compras:** Migrar carga de facturas de proveedores y órdenes de compra.
- [ ] **Tesorería y Finanzas:** Migrar gestión de cobros (Recibos), pagos y cajas.
- [ ] **Dashboard Principal:** Migrar estadísticas y gráficos de ventas/compras.
