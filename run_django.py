
import os
import sys
import logging
from waitress import serve
from django.core.wsgi import get_wsgi_application

# Configurar el entorno de Django
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DJANGO_APP_DIR = os.path.join(PROJECT_ROOT, "django_app")
sys.path.append(DJANGO_APP_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colosal_django.settings')

# Configurar logging para producción
log_dir = os.path.join(PROJECT_ROOT, "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "server_production_django.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('django_production_server')

def start_server():
    # Django application
    application = get_wsgi_application()
    
    # Puerto por defecto 8000 para Django o 5000 para compatibilidad Colosal
    port = int(os.environ.get('PORT', 8000))
    host = '0.0.0.0'
    
    logger.info(f"Iniciando Servidor Waitress (Django) en {host}:{port}...")
    try:
        serve(application, host=host, port=port, threads=12)
    except Exception as e:
        logger.error(f"Error fatal al iniciar el servidor Django: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_server()
