from apps.core.db import get_db_cursor, dictfetchall, dictfetchone
import logging

logger = logging.getLogger(__name__)

class NumerationService:
    @staticmethod
    def get_next_number(enterprise_id, entidad_tipo, entidad_codigo, punto_venta=1, cursor=None):
        """
        Calcula el próximo número para un comprobante o entidad.
        Soporta inyección de cursor para participar en transacciones.
        """
        if cursor is None:
            with get_db_cursor(dictionary=True) as new_cursor:
                return NumerationService._logic_get_next(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, new_cursor)
        return NumerationService._logic_get_next(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, cursor)

    @staticmethod
    def _logic_get_next(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, cursor):
        # 0. Verificar si el tipo es numerable
        if entidad_tipo == 'COMPROBANTE':
            cursor.execute("SELECT es_numerable FROM sys_tipos_comprobante WHERE codigo = %s", (entidad_codigo,))
            t_row = dictfetchone(cursor)
            if t_row and t_row.get('es_numerable') == 0:
                return 0

        # 1. Bloqueo de fila para serializar la obtención del número por tenant/tipo/punto
        cursor.execute("""
            SELECT ultimo_numero 
            FROM sys_enterprise_numeracion 
            WHERE enterprise_id = %s AND entidad_tipo = %s AND entidad_codigo = %s AND punto_venta = %s
            FOR UPDATE
        """, (enterprise_id, entidad_tipo, entidad_codigo, punto_venta))
        
        row_p = dictfetchone(cursor)
        base_p = row_p['ultimo_numero'] if row_p else 0

        # 2. Verificar contra comprobantes reales (solo si es el primer número o para auditoría)
        base_r = 0
        if entidad_tipo == 'COMPROBANTE':
            cursor.execute("""
                SELECT MAX(numero) as max_n 
                FROM erp_comprobantes 
                WHERE enterprise_id = %s AND tipo_comprobante = %s AND punto_venta = %s
            """, (enterprise_id, entidad_codigo, punto_venta))
            row_r = dictfetchone(cursor)
            base_r = row_r['max_n'] if row_r and row_r.get('max_n') else 0

        next_n = max(base_p, base_r) + 1
        return next_n

    @staticmethod
    def update_last_number(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, numero, cursor=None):
        """
        Actualiza el último número generado. Soporta inyección de cursor.
        """
        if cursor is None:
            with get_db_cursor() as new_cursor:
                NumerationService._logic_update(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, numero, new_cursor)
        else:
            NumerationService._logic_update(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, numero, cursor)

    @staticmethod
    def _logic_update(enterprise_id, entidad_tipo, entidad_codigo, punto_venta, numero, cursor):
        cursor.execute("""
            UPDATE sys_enterprise_numeracion 
            SET ultimo_numero = %s 
            WHERE enterprise_id = %s AND entidad_tipo = %s AND entidad_codigo = %s AND punto_venta = %s
        """, (numero, enterprise_id, entidad_tipo, entidad_codigo, punto_venta))
        
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT IGNORE INTO sys_enterprise_numeracion 
                (enterprise_id, entidad_tipo, entidad_codigo, punto_venta, ultimo_numero)
                VALUES (%s, %s, %s, %s, %s)
            """, (enterprise_id, entidad_tipo, entidad_codigo, punto_venta, numero))
