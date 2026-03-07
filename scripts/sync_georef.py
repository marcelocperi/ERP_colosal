#!/usr/bin/env python
"""
Cron Job: Sincronización Georef (Django)
Uso: python scripts/sync_georef.py

Ejecuta la sincronización completa de provincias, localidades y calles
desde la API de Georef de Argentina hacia las tablas locales.
"""

import os
import sys
import datetime
import logging

# Configurar Django antes de importar cualquier app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
django_app_dir = os.path.join(project_root, 'django_app')
sys.path.insert(0, django_app_dir)
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colosal_django.settings')

import django
django.setup()

from apps.core.services.georef_service import GeorefService
from apps.core.db import get_db_cursor, dictfetchone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def main():
    cron_name = "Sincronización Completa Georef"
    start_time = datetime.datetime.now()
    log_id = None
    cron_id = None

    try:
        # 1. Identificar el CRON y crear log
        with get_db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM sys_crons WHERE nombre = %s", (cron_name,))
            cron = dictfetchone(cursor)
            if cron:
                cron_id = cron['id']
                cursor.execute("""
                    INSERT INTO sys_crons_logs (cron_id, fecha_inicio, status, resultado)
                    VALUES (%s, %s, %s, %s)
                """, (cron_id, start_time, 'exito', 'Sincronización en curso...'))
                cursor.execute("SELECT LAST_INSERT_ID() as lid")
                log_id = dictfetchone(cursor)['lid']

        logger.info(f"Iniciando tarea programada: {cron_name}...")
        
        # Ejecución real (síncrona)
        GeorefService.sync_full()
        
        # 2. Finalizar con éxito
        if log_id:
            end_time = datetime.datetime.now()
            proxima = None
            with get_db_cursor(dictionary=True) as cursor:
                cursor.execute("SELECT frecuencia, planificacion FROM sys_crons WHERE id = %s", (cron_id,))
                cron_row = dictfetchone(cursor)

            if cron_row:
                try:
                    from apps.core.services.cron_utils import calcular_proxima_ejecucion
                    proxima = calcular_proxima_ejecucion(cron_row['frecuencia'], cron_row['planificacion'])
                except ImportError:
                    proxima = end_time + datetime.timedelta(days=1)

            with get_db_cursor() as cursor:
                cursor.execute("""
                    UPDATE sys_crons_logs 
                    SET fecha_fin = %s, status = %s, resultado = %s
                    WHERE id = %s
                """, (end_time, 'exito', 'Sincronización completada exitosamente.', log_id))
                cursor.execute(
                    "UPDATE sys_crons SET ultima_ejecucion = %s, proxima_ejecucion = %s WHERE id = %s",
                    (end_time, proxima, cron_id)
                )
        
        logger.info("Sincronización Georef completada exitosamente.")

    except Exception as e:
        error_msg = f"Error fatal en la sincronización Georef: {str(e)}"
        logger.error(error_msg)
        
        if log_id:
            try:
                with get_db_cursor() as cursor:
                    cursor.execute("""
                        UPDATE sys_crons_logs 
                        SET fecha_fin = %s, status = %s, resultado = %s
                        WHERE id = %s
                    """, (datetime.datetime.now(), 'error', error_msg, log_id))
            except: pass
        sys.exit(1)

if __name__ == "__main__":
    main()
