import logging
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

def run_async(async_func, *args, **kwargs):
    """
    Envuelve una función asíncrona para correrla de forma síncrona.
    Útil para llamar a servicios heredados de Quart que aún no han sido migrados a sync.
    """
    try:
        return async_to_sync(async_func)(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error ejecutando función asíncrona {async_func.__name__}: {e}")
        raise e
