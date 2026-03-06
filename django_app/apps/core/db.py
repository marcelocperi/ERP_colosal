import logging
from django.db import connections, transaction
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def dictfetchone(cursor):
    """Return one row from a cursor as a dict"""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))

@contextmanager
def get_db_cursor(using='default', dictionary=True):
    """
    Context manager for database cursor.
    Mirrors the Quart implementation.
    """
    cursor = connections[using].cursor()
    try:
        yield cursor
    finally:
        cursor.close()

def atomic_transaction(using='default'):
    """Decorator for atomic transactions."""
    return transaction.atomic(using=using)
