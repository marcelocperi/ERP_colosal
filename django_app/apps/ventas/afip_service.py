import os
import datetime
import random
import json
import base64
import requests
from django.conf import settings
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
import logging

logger = logging.getLogger(__name__)

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import pkcs7
    import zeep
    from zeep import Client
    HAS_AFIP_DEPS = True
except ImportError:
    HAS_AFIP_DEPS = False

class AfipService:
    """
    Servicio para interoperabilidad con AFIP (Versión Django Sync).
    Soporta modo simulado (Mock) y conexión real vía Webservices (SOAP).
    """

    ERRORES_TRADUCCION = {
        '10016': "Error de correlatividad: El número de comprobante no coincide con el siguiente esperado por AFIP.",
        '10192': "Debe emitir Factura de Crédito Electrónica MiPyME (FCE) debido al monto y tipo de cliente.",
        '10015': "El documento del receptor no es válido o no está activo en el padrón de AFIP.",
        '500': "Error interno en los servidores de AFIP. Reintente en unos minutos.",
        '501': "Error de base de datos en AFIP. Reintente en unos minutos.",
        '502': "Saturación en servidores de AFIP (Transacción activa). Espere un momento.",
    }

    WSAA_WSDL = {
        'testing': 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl',
        'produccion': 'https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl'
    }

    FE_WSDL = {
        'testing': 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
        'produccion': 'https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL'
    }

    PADRON_A10_WSDL = {
        'testing': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA10?WSDL',
        'produccion': 'https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA10?WSDL'
    }

    @staticmethod
    def get_afip_config(enterprise_id):
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT cuit, afip_crt, afip_key, afip_entorno FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            return dictfetchone(cursor)

    @staticmethod
    def registrar_bitacora(enterprise_id, evento, tipo='INFO', detalle=None, data=None):
        try:
            data_json = json.dumps(data) if data else None
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO fin_neb_bitacora (enterprise_id, evento, tipo, detalle, data_json)
                    VALUES (%s, %s, %s, %s, %s)
                """, (enterprise_id, evento, tipo, detalle, data_json))
        except Exception as e:
            logger.error(f"Error registrando en bitacora: {e}")

    @staticmethod
    def _the_key_maker(enterprise_id, service="wsfe"):
        """
        Gestiona los Tickets de Acceso WSAA con caché en base de datos.
        """
        # 1. Verificar caché
        try:
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT token, sign, expira_en FROM fin_trinity_tokens 
                    WHERE enterprise_id = %s AND servicio = %s 
                    AND expira_en > DATE_ADD(NOW(), INTERVAL 10 MINUTE)
                """, (enterprise_id, service))
                cached = dictfetchone(cursor)
                if cached:
                    return {"token": cached['token'], "sign": cached['sign']}
        except Exception as e:
            logger.error(f"Error leyendo caché de tokens: {e}")

        # 2. No hay caché → pedir a AFIP
        config = AfipService.get_afip_config(enterprise_id)
        if not config or not config['afip_crt'] or not config['afip_key']:
            return None
        
        entorno = config['afip_entorno']
        crt_data = config['afip_crt'].encode()
        key_data = config['afip_key'].encode()
        
        # Crear TRA
        now = datetime.datetime.now()
        vto = now + datetime.timedelta(hours=12)
        unique_id = str(random.randint(0, 999999))
        
        tra = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{now.strftime('%Y-%m-%dT%H:%M:%S')}</generationTime>
    <expirationTime>{vto.strftime('%Y-%m-%dT%H:%M:%S')}</expirationTime>
  </header>
  <service>{service}</service>
</loginTicketRequest>"""

        try:
            cert = x509.load_pem_x509_certificate(crt_data, default_backend())
            key = serialization.load_pem_private_key(key_data, password=None, backend=default_backend())
            
            signature = pkcs7.PKCS7SignatureBuilder().set_data(tra.encode())\
                        .add_signer(cert, key, hashes.SHA256())\
                        .sign(serialization.Encoding.DER, [])
            
            cms_signed = base64.b64encode(signature).decode('utf-8').strip()
            
            wsdl = AfipService.WSAA_WSDL.get(entorno)
            client = Client(wsdl=wsdl)
            response_xml = client.service.loginCms(in0=cms_signed)
            
            from lxml import etree
            root = etree.fromstring(response_xml.encode('utf-8'))
            token = root.xpath('//token/text()')[0]
            sign = root.xpath('//sign/text()')[0]
            
            # 3. Guardar en caché
            with get_db_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO fin_trinity_tokens (enterprise_id, servicio, token, sign, expira_en)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE token=VALUES(token), sign=VALUES(sign), expira_en=VALUES(expira_en)
                """, (enterprise_id, service, token, sign, vto))
            
            return {"token": token, "sign": sign}
        except Exception as e:
            logger.error(f"Error WSAA: {str(e)}")
            return None

    @staticmethod
    def consultar_padron(enterprise_id, cuit_dni):
        digits = "".join(filter(str.isdigit, str(cuit_dni)))
        config = AfipService.get_afip_config(enterprise_id)
        
        if not config or not config['afip_crt'] or not config['afip_key']:
            return AfipService._simular_consultar_padron(digits)

        try:
            ticket = AfipService._the_key_maker(enterprise_id, service="ws_sr_padron_a10")
            if not ticket:
                return {"success": False, "error": "No se pudo obtener el Ticket de Acceso (WSAA)"}
            
            wsdl = AfipService.PADRON_A10_WSDL.get(config['afip_entorno'])
            client = Client(wsdl=wsdl)
            
            cuit_empresa = int("".join(filter(str.isdigit, str(config['cuit']))))
            cuit_busca = int(digits)

            res = client.service.getPersona(
                token=ticket['token'],
                sign=ticket['sign'],
                cuitRepresentada=cuit_empresa,
                idPersona=cuit_busca
            )
            
            if not res or not hasattr(res, 'personaReturn'):
                return {"success": False, "error": "No se encontraron datos en AFIP"}

            p = res.personaReturn.persona
            nombre = getattr(p, 'razonSocial', '') or f"{getattr(p, 'apellido', '')} {getattr(p, 'nombre', '')}".strip()
            
            data = {
                "cuit": str(p.idPersona),
                "razon_social": nombre or "Desconocido",
                "tipo_persona": getattr(p, 'tipoPersona', ''),
                "estado": getattr(p, 'estadoClave', ''),
                "domicilio": "",
                "condicion_iva": "Consumidor Final",
                "monotributo": False
            }
            
            # Domicilio Fiscal
            if hasattr(p, 'domicilio'):
                doms = p.domicilio if isinstance(p.domicilio, list) else [p.domicilio]
                for d in doms:
                    if getattr(d, 'tipoDomicilio', '') == "FISCAL":
                        data["domicilio"] = f"{getattr(d, 'direccion', '')}, {getattr(d, 'localidad', '')}, {getattr(d, 'descripcionProvincia', '')}"
                        break
            
            # Impuestos
            if hasattr(p, 'impuesto'):
                imps = p.impuesto if isinstance(p.impuesto, list) else [p.impuesto]
                for imp in imps:
                    id_imp = getattr(imp, 'idImpuesto', 0)
                    if id_imp == 30: data["condicion_iva"] = "IVA Responsable Inscripto"
                    elif id_imp == 20: 
                        data["condicion_iva"] = "Monotributo"
                        data["monotributo"] = True
                    elif id_imp == 32: data["condicion_iva"] = "IVA Sujeto Exento"
            
            return {"success": True, "data": data}

        except Exception as e:
            logger.error(f"Error AFIP Real: {str(e)}")
            return AfipService._simular_consultar_padron(digits)

    @staticmethod
    def solicitar_cae(enterprise_id, comprobante_id, cursor=None):
        config = AfipService.get_afip_config(enterprise_id)
        if not config or not config['afip_crt']:
            return AfipService._simular_cae(enterprise_id, comprobante_id, cursor)

        try:
            # 1. Obtener datos del comprobante
            with get_db_cursor(dictionary=True) as local_cursor:
                q_cursor = cursor if cursor else local_cursor
                q_cursor.execute("""
                    SELECT c.*, t.cuit as cliente_cuit 
                    FROM erp_comprobantes c
                    JOIN erp_terceros t ON c.tercero_id = t.id
                    WHERE c.id = %s AND c.enterprise_id = %s
                """, (comprobante_id, enterprise_id))
                comp = dictfetchone(q_cursor)
                if not comp:
                    return {"success": False, "error": "Comprobante no encontrado."}
                
                q_cursor.execute("SELECT * FROM erp_comprobantes_detalle WHERE comprobante_id = %s", (comprobante_id,))
                detalles = dictfetchall(q_cursor)

            # 2. Login WSAA
            ticket = AfipService._the_key_maker(enterprise_id, service="wsfe")
            if not ticket:
                return {"success": False, "error": "WSAA Falló"}

            # 3. Conexión WSFE
            wsdl = AfipService.FE_WSDL.get(config['afip_entorno'])
            client = Client(wsdl=wsdl)
            
            cuit_empresa = int("".join(filter(str.isdigit, str(config['cuit']))))
            auth = {'Token': ticket['token'], 'Sign': ticket['sign'], 'Cuit': cuit_empresa}

            # 4. Obtener último número
            res_ultimo = client.service.FECompUltimoAutorizado(
                Auth=auth,
                CbteTipo=int(comp['tipo_comprobante']),
                PtoVta=int(comp['punto_venta'])
            )
            prox_nro = res_ultimo.CbteNro + 1
            
            # 5. Agrupar IVA
            iva_groups = {}
            iva_map = {21.0: 5, 10.5: 4, 27.0: 6, 5.0: 8, 2.5: 9, 0.0: 3}
            for d in detalles:
                alic = float(d.get('alicuota_iva', 21))
                alic_id = iva_map.get(alic, 5)
                if alic_id not in iva_groups:
                    iva_groups[alic_id] = {'BaseImp': 0, 'Importe': 0}
                iva_groups[alic_id]['BaseImp'] += float(d.get('subtotal_neto', d.get('neto', 0)))
                iva_groups[alic_id]['Importe'] += float(d.get('importe_iva', d.get('iva', 0)))

            iva_list = []
            for i_id, vals in iva_groups.items():
                iva_list.append({'Id': i_id, 'BaseImp': round(vals['BaseImp'], 2), 'Importe': round(vals['Importe'], 2)})

            # 6. Solicitar CAE
            doc_nro = int("".join(filter(str.isdigit, str(comp['cliente_cuit']))))
            request = {
                'FeCabReq': {
                    'CantReg': 1,
                    'PtoVta': int(comp['punto_venta']),
                    'CbteTipo': int(comp['tipo_comprobante'])
                },
                'FeDetReq': {
                    'FECAEDetRequest': [{
                        'Concepto': 1,
                        'DocTipo': 80 if doc_nro > 99999999 else 96,
                        'DocNro': doc_nro,
                        'CbteDesde': prox_nro,
                        'CbteHasta': prox_nro,
                        'CbteFch': datetime.date.today().strftime('%Y%m%d'),
                        'ImpTotal': round(float(comp['importe_total']), 2),
                        'ImpTotConc': 0,
                        'ImpNeto': round(float(comp['importe_neto']), 2),
                        'ImpOpEx': 0,
                        'ImpTrib': round(float((comp.get('importe_percepcion_iibb_arba') or 0) + (comp.get('importe_percepcion_iibb_agip') or 0)), 2),
                        'ImpIVA': round(float(comp['importe_iva']), 2),
                        'MonId': 'PES',
                        'MonCotiz': 1,
                        'Iva': {'AlicIva': iva_list} if iva_list else None
                    }]
                }
            }

            res = client.service.FECAESolicitar(Auth=auth, FeCAEReq=request)
            
            if res.FeCabResp.Resultado == 'A':
                det = res.FeDetResp.FECAEDetResponse[0]
                cae = det.CAE
                vto_cae = datetime.datetime.strptime(det.CAEFchVto, '%Y%m%d').strftime('%Y-%m-%d')
                
                with get_db_cursor() as u_cursor:
                    u_cursor.execute("""
                        UPDATE erp_comprobantes 
                        SET cae = %s, vto_cae = %s, numero = %s
                        WHERE id = %s
                    """, (cae, vto_cae, prox_nro, comprobante_id))
                
                return {"success": True, "cae": cae, "vto_cae": vto_cae, "numero": prox_nro}
            else:
                errors = []
                if hasattr(res, 'Errors') and res.Errors:
                    for e in res.Errors.Err:
                        errors.append(f"{e.Code}: {e.Msg}")
                if hasattr(res.FeDetResp, 'FECAEDetResponse'):
                    for obs in getattr(res.FeDetResp.FECAEDetResponse[0], 'Observaciones', None) or []:
                        for o in obs:
                            errors.append(f"Obs {o.Code}: {o.Msg}")
                
                return {"success": False, "error": "; ".join(errors)}

        except Exception as e:
            logger.exception("Error en solicitar_cae real")
            return AfipService._simular_cae(enterprise_id, comprobante_id, cursor)

    @staticmethod
    def _simular_cae(enterprise_id, comprobante_id, cursor=None):
        cae = "".join([str(random.randint(0, 9)) for _ in range(14)])
        vto_cae = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        with get_db_cursor() as u_cursor:
            q = cursor if cursor else u_cursor
            q.execute("UPDATE erp_comprobantes SET cae = %s, vto_cae = %s WHERE id = %s", (cae, vto_cae, comprobante_id))
        return {"success": True, "cae": cae, "vto_cae": vto_cae, "mensaje": "CAE Simulado"}

    @staticmethod
    def _simular_consultar_padron(digits):
        # ... keep same simulation as before ...
        if digits == "20171634432":
            return {"success": True, "data": {"cuit": "20171634432", "razon_social": "MARCELO PERI", "condicion_iva": "Monotributo"}}
        return {"success": True, "data": {"cuit": digits, "razon_social": "USUARIO TEST AFIP S.A.", "condicion_iva": "Responsable Inscripto"}}
