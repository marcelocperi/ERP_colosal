import logging
from apps.core.db import get_db_cursor

logger = logging.getLogger(__name__)

class GeorefService:
    @staticmethod
    def get_provincias():
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM sys_provincias ORDER BY nombre ASC")
            return cursor.fetchall()

    @staticmethod
    def get_localidades(provincia_nombre):
        try:
            with get_db_cursor(dictionary=True) as cursor:
                query = """
                    SELECT DISTINCT l.nombre FROM sys_localidades l
                    JOIN sys_provincias p ON l.provincia_id = p.id
                    WHERE p.nombre LIKE %s
                    ORDER BY l.nombre ASC
                """
                cursor.execute(query, (f"%{provincia_nombre}%",))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Local search error (localidades): {e}")
            return []

    @classmethod
    def get_calles(cls, localidad_nombre, provincia_nombre=None, nombre=None):
        if not nombre or len(nombre) < 3:
            return []
        
        try:
            with get_db_cursor(dictionary=True) as cursor:
                sql = """
                    SELECT DISTINCT c.nombre FROM sys_calles c
                    JOIN sys_provincias p ON c.provincia_id = p.id
                    JOIN sys_localidades l ON c.localidad_id = l.id
                    WHERE c.nombre LIKE %s
                """
                params = [f"%{nombre}%"]
                
                if localidad_nombre:
                    sql += " AND l.nombre LIKE %s"
                    params.append(f"%{localidad_nombre}%")
                
                if provincia_nombre:
                    sql += " AND p.nombre LIKE %s"
                    params.append(f"%{provincia_nombre}%")
                
                sql += " LIMIT 50"
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Local search error (calles): {e}")
            return []

    @staticmethod
    def get_cp_by_location(provincia_nombre, localidad_nombre):
        CP_BASE_MAP = {
            "Ciudad Autónoma de Buenos Aires": "1000", "Buenos Aires": "1900", "Catamarca": "4700",
            "Chaco": "3500", "Chubut": "9100", "Córdoba": "5000", "Corrientes": "3400",
            "Entre Ríos": "3100", "Formosa": "3600", "Jujuy": "4600", "La Pampa": "6300",
            "La Rioja": "5300", "Mendoza": "5500", "Misiones": "3300", "Neuquén": "8300",
            "Río Negro": "8500", "Salta": "4400", "San Juan": "5400", "San Luis": "5700",
            "Santa Cruz": "9400", "Santa Fe": "3000", "Santiago del Estero": "4200",
            "Tierra del Fuego, Antártida e Islas del Atlántico Sur": "9410", "Tucumán": "4000"
        }
        try:
            with get_db_cursor(dictionary=True) as cursor:
                query = "SELECT DISTINCT cod_postal FROM erp_direcciones WHERE provincia LIKE %s AND localidad LIKE %s LIMIT 1"
                cursor.execute(query, (f"%{provincia_nombre}%", f"%{localidad_nombre}%"))
                res = cursor.fetchone()
                if res: return [res['cod_postal']]
        except: pass
        
        for k, v in CP_BASE_MAP.items():
            if k.lower() in provincia_nombre.lower(): return [v]
        return []
