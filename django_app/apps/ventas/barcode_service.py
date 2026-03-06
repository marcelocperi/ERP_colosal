import qrcode
import base64
from io import BytesIO
import json
from barcode import ITF
from barcode.writer import ImageWriter

class BarcodeService:
    @staticmethod
    def calculate_afip_dv(number):
        """Calcula el dígito verificador para el código de barras AFIP."""
        total_par = 0
        total_impar = 0
        for i, digit in enumerate(number):
            if (i + 1) % 2 == 0:
                total_par += int(digit)
            else:
                total_impar += int(digit)
        
        sum_total = (total_impar * 3) + total_par
        dv = (10 - (sum_total % 10)) % 10
        return str(dv)

    @staticmethod
    def generate_afip_barcode(cuit, tipo_comp, pto_vta, cae, vto_cae):
        """Genera el código de barras AFIP en formato base64."""
        if not cae or cae == '—':
            return None
            
        # Padding
        cuit = str(cuit).replace('-', '')
        tipo = str(tipo_comp).zfill(2)
        pdv = str(pto_vta).zfill(4)
        cae_str = str(cae)
        
        # Formatear vto_cae
        if hasattr(vto_cae, 'strftime'):
            vto = vto_cae.strftime('%Y%m%d')
        else:
            vto = str(vto_cae or '').replace('-', '')
        
        if not vto:
            return None

        number = cuit + tipo + pdv + cae_str + vto
        dv = BarcodeService.calculate_afip_dv(number)
        full_number = number + dv
        
        rv = BytesIO()
        ITF(full_number, writer=ImageWriter()).write(
            rv, 
            options={"module_height": 10.0, "module_width": 0.2, "quiet_zone": 1.0, "write_text": False}
        )
        return base64.b64encode(rv.getvalue()).decode('utf-8')

    @staticmethod
    def generate_afip_qr(c, empresa, cliente_dir):
        """Genera el QR de AFIP en formato base64."""
        # https://www.afip.gob.ar/fe/qr/especificaciones.asp
        
        fecha = c.get('fecha_emision')
        if hasattr(fecha, 'strftime'):
            fecha_str = fecha.strftime('%Y-%m-%d')
        else:
            fecha_str = str(fecha or '')
            
        cae = c.get('cae')
        if not cae or cae == '—':
            return None

        data = {
            "ver": 1,
            "fecha": fecha_str,
            "cuit": int(str(empresa.get('cuit', '')).replace('-', '')),
            "ptoVta": int(c.get('punto_venta', 0)),
            "tipoCmp": int(c.get('tipo_comprobante', 0)),
            "nroCmp": int(c.get('numero', 0)),
            "importe": float(c.get('importe_total', 0)),
            "moneda": "PES",
            "ctz": 1.0,
            "tipoDocRec": 80 if len(str(c.get('cliente_cuit', ''))) > 8 else 96, # 80 = CUIT, 96 = DNI
            "nroDocRec": int(str(c.get('cliente_cuit', '0')).replace('-', '')),
            "tipoCodAut": "E", # E = CAE
            "codAut": int(cae) if str(cae).isdigit() else 0
        }
        
        json_data = json.dumps(data)
        encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        url = f"https://www.afip.gob.ar/fe/qr/?p={encoded_data}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=0)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
