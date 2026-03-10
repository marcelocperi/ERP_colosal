
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

# Usamos un logger específico para esta instancia
port = int(os.environ.get('PORT', 8000))
log_name = f"server_django_{port}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, log_name)),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(f'django_server_{port}')

def start_server():
    # Django application
    try:
        application = get_wsgi_application()
    except Exception as e:
        logger.error(f"Error al cargar la aplicación Django: {e}")
        sys.exit(1)
    
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Iniciando Servidor Waitress (Django) en {host}:{port}...")
    try:
        serve(application, host=host, port=port, threads=12)
    except Exception as e:
        logger.error(f"Error fatal al iniciar el servidor Django en puerto {port}: {e}")
        sys.exit(1)

if __name__ == '__main__':
    start_server()
