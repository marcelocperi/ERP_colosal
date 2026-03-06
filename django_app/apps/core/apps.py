from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        """
        Lógica de inicialización al arrancar Django.
        Equivalente al @app.before_serving de Quart.
        """
        # Evitamos ejecutar esto durante migraciones o comandos de gestión
        import sys
        if 'manage.py' in sys.argv and ('makemigrations' in sys.argv or 'migrate' in sys.argv):
            return

        try:
            from django.db import connection
            # Aquí llamaremos a los inicializadores de los servicios
            # Nota: Debemos asegurar que los servicios tengan versiones síncronas
            # o envolverlos adecuadamente.
            
            # Por ahora solo verificamos conexión
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            logger.info("✅ Infraestructura Django Core inicializada y DB conectada.")
            
        except Exception as e:
            logger.error(f"❌ Error en la inicialización de CoreConfig: {e}")

