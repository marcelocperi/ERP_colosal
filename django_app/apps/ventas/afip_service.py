import os
import datetime
import random
import json
import base64
import requests
from decimal import Decimal
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import pkcs7
    import zeep
    HAS_AFIP_DEPS = True
except ImportError:
    HAS_AFIP_DEPS = False

class AfipService:
    WCONSUCUIT_WSDL = {
        'testing': 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13?WSDL',
        'produccion': 'https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13?WSDL'
    }

    FE_WSDL = {
        'testing': 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL',
        'produccion': 'https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL'
    }

    @staticmethod
    def get_afip_config(enterprise_id):
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT cuit, afip_crt, afip_key, afip_entorno FROM sys_enterprises WHERE id = %s", (enterprise_id,))
            return dictfetchone(cursor)

    @staticmethod
    def solicitar_cae(enterprise_id, comprobante_id, cursor=None):
        """
        Solicita el CAE al webservice de AFIP. (Sync version for Django)
        """
        config = AfipService.get_afip_config(enterprise_id)
        if not config or not config.get('afip_crt') or not config.get('afip_key'):
            # SIMULACION SI NO HAY CERTIFICADOS
            return AfipService._simular_cae(enterprise_id, comprobante_id, cursor)

        # TO-DO: Implement real connection using zeep
        # For now, if certificates exist but we are in migration, we can still simulate or try to connect
        return AfipService._simular_cae(enterprise_id, comprobante_id, cursor)

    @staticmethod
    def _simular_cae(enterprise_id, comprobante_id, cursor=None):
        """
        Simula una respuesta exitosa de AFIP para desarrollo.
        """
        cae = "".join([str(random.randint(0, 9)) for _ in range(14)])
        vto_cae = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        
        update_sql = """
            UPDATE erp_comprobantes 
            SET cae = %s, vto_cae = %s, fecha_cae = CURRENT_TIMESTAMP 
            WHERE id = %s AND enterprise_id = %s
        """
        params = (cae, vto_cae, comprobante_id, enterprise_id)
        
        if cursor:
            cursor.execute(update_sql, params)
        else:
            with get_db_cursor() as new_cursor:
                new_cursor.execute(update_sql, params)
                
        return {
            "success": True,
            "cae": cae,
            "vto_cae": vto_cae,
            "mensaje": "CAE Simulado exitosamente (Entorno de Desarrollo)"
        }

    @staticmethod
    def consultar_padron(enterprise_id, cuit_dni):
        digits = "".join(filter(str.isdigit, str(cuit_dni)))
        config = AfipService.get_afip_config(enterprise_id)
        
        if not config or not config.get('afip_crt') or not config.get('afip_key'):
            return AfipService._simular_consultar_padron(digits)

        return AfipService._simular_consultar_padron(digits)

    @staticmethod
    def _simular_consultar_padron(digits):
        if digits == "20171634432":
            return {
                "success": True,
                "data": {
                    "cuit": "20171634432",
                    "razon_social": "MARCELO PERI",
                    "tipo_persona": "FISICA",
                    "estado": "ACTIVO",
                    "domicilio": "AV. CARABOBO 345, CABA",
                    "condicion_iva": "Monotributo",
                    "jurisdicciones": ["901 - CABA"],
                    "monotributo": True
                }
            }
        return {
            "success": True,
            "data": {
                "cuit": digits,
                "razon_social": "USUARIO TEST AFIP S.A.",
                "tipo_persona": "JURIDICA",
                "estado": "ACTIVO",
                "domicilio": "AV. LIBERTADOR 1234, CABA",
                "condicion_iva": "Responsable Inscripto",
                "jurisdicciones": ["901 - CABA", "902 - BS AS"],
                "monotributo": False
            }
        }
