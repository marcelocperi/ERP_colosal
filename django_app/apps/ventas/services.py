import re
from apps.core.db import get_db_cursor, dictfetchall, dictfetchone

class TerceroService:
    @staticmethod
    def generar_siguiente_codigo(enterprise_id, prefijo="C"):
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT MAX(codigo) as max_code 
                FROM erp_terceros 
                WHERE enterprise_id = %s AND codigo LIKE %s
            """, (enterprise_id, f"{prefijo}%"))
            result = dictfetchone(cursor)
            
            if not result or not result['max_code']:
                return f"{prefijo}0001"
            
            try:
                # Extraer números del string
                nums = re.findall(r'\d+', result['max_code'])
                if nums:
                    next_num = int(nums[-1]) + 1
                    # Pad to 4 digits if < 10000, or more if needed
                    return f"{prefijo}{str(next_num).zfill(4)}"
                else:
                    return f"{prefijo}0001"
            except:
                return f"{prefijo}0001"

    @staticmethod
    def get_terceros_generales(enterprise_id):
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM erp_terceros WHERE enterprise_id = %s", (enterprise_id,))
            return dictfetchall(cursor)

class CM05Service:
    @staticmethod
    def log_action(cursor, enterprise_id, tercero_id, jurisdiccion, periodo_anio, coeficiente, user_id, action_id, es_cliente, es_proveedor, old_data_json):
        # action_id: 0 = insert, 2 = update, 3 = delete/deshabilitar
        cursor.execute("""
            INSERT INTO log_erp_terceros_cm05 (id_action, fecha_efectiva, user_action, tercero_id, es_cliente, es_proveedor, jurisdiccion_code, periodo_anio, coeficiente, RECORD_JSON)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
        """, (action_id, user_id, tercero_id, es_cliente, es_proveedor, jurisdiccion, periodo_anio, coeficiente, old_data_json))

    @staticmethod
    def upsert_coeficiente(enterprise_id, tercero_id, jurisdiccion, periodo_anio, coeficiente, user_id):
        import json
        with get_db_cursor(dictionary=True) as cursor:
            # Check if exists
            cursor.execute("SELECT id, coeficiente FROM erp_terceros_cm05 WHERE tercero_id = %s AND enterprise_id = %s AND jurisdiccion_code = %s AND periodo_anio = %s", (tercero_id, enterprise_id, jurisdiccion, periodo_anio))
            exists = dictfetchone(cursor)
            
            # Identify if client or supplier
            cursor.execute("SELECT es_cliente, es_proveedor FROM erp_terceros WHERE id = %s", (tercero_id,))
            tercero = dictfetchone(cursor)
            es_cliente = tercero['es_cliente'] if tercero else 0
            es_proveedor = tercero['es_proveedor'] if tercero else 0
            
            if exists:
                old_data_json = json.dumps(exists, default=str)
                # Apply Update
                cursor.execute("""
                    UPDATE erp_terceros_cm05 
                    SET coeficiente = %s, user_id_update = %s, date_update = NOW()
                    WHERE id = %s
                """, (coeficiente, user_id, exists['id']))
                # Action 2 = update
                CM05Service.log_action(cursor, enterprise_id, tercero_id, jurisdiccion, periodo_anio, coeficiente, user_id, 2, es_cliente, es_proveedor, old_data_json)
            else:
                # Apply Insert
                cursor.execute("""
                    INSERT INTO erp_terceros_cm05 (enterprise_id, tercero_id, jurisdiccion_code, periodo_anio, coeficiente, user_id, date_insert)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (enterprise_id, tercero_id, jurisdiccion, periodo_anio, coeficiente, user_id))
                # Action 0 = insert
                CM05Service.log_action(cursor, enterprise_id, tercero_id, jurisdiccion, periodo_anio, coeficiente, user_id, 0, es_cliente, es_proveedor, "{}")

    @staticmethod
    def delete_coeficiente(enterprise_id, item_id, user_id):
        import json
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM erp_terceros_cm05 WHERE id = %s AND enterprise_id = %s", (item_id, enterprise_id))
            exists = dictfetchone(cursor)
            if not exists: return
            
            cursor.execute("SELECT es_cliente, es_proveedor FROM erp_terceros WHERE id = %s", (exists['tercero_id'],))
            tercero = dictfetchone(cursor)
            es_cliente = tercero['es_cliente'] if tercero else 0
            es_proveedor = tercero['es_proveedor'] if tercero else 0
            
            old_data_json = json.dumps(exists, default=str)
            
            # Delete 
            cursor.execute("DELETE FROM erp_terceros_cm05 WHERE id = %s", (item_id,))
            
            # Action 3 = delete/deshabilitar
            CM05Service.log_action(cursor, enterprise_id, exists['tercero_id'], exists['jurisdiccion_code'], exists['periodo_anio'], exists['coeficiente'], user_id, 3, es_cliente, es_proveedor, old_data_json)
