from apps.ventas.barcode_service import BarcodeService
import datetime

c = {
    'fecha_emision': datetime.date.today(),
    'punto_venta': 1,
    'tipo_comprobante': 1,
    'numero': 123,
    'importe_total': 1000.50,
    'cliente_cuit': '20171634432',
    'cae': '12345678901234'
}

empresa = {
    'cuit': '30000000007'
}

cliente_dir = {}

try:
    qr = BarcodeService.generate_afip_qr(c, empresa, cliente_dir)
    print(f"QR generated: {len(qr)} bytes")
    
    bc = BarcodeService.generate_afip_barcode(empresa['cuit'], c['tipo_comprobante'], c['punto_venta'], c['cae'], datetime.date.today())
    print(f"Barcode generated: {len(bc)} bytes")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
