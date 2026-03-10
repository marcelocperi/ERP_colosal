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
        import sys
        if 'manage.py' in sys.argv and ('makemigrations' in sys.argv or 'migrate' in sys.argv):
            return

        try:
            logger.info("✅ Infraestructura Django Core inicializada (DB será inicializada por la primera solicitud HTTP).")
        except Exception as e:
            logger.error(f"❌ Error en la inicialización de CoreConfig: {e}")

