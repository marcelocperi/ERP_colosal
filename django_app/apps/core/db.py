import logging
from django.db import connections, transaction
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def dictfetchall(cursor):
    """Return all rows from a cursor as a dict"""
    if not cursor.description:
        return cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row)) if not isinstance(row, dict) else row
        for row in cursor.fetchall()
    ]

def dictfetchone(cursor):
    """Return one row from a cursor as a dict"""
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if cursor.description:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    return row

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
