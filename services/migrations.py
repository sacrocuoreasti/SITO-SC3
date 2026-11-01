"""Backup SQLite prima delle sole migrazioni additive mancanti."""
import os
import sqlite3
from datetime import datetime
from sqlalchemy import inspect


def backup_sqlite(engine):
    expected = {'persona': {'terapie_medicinali'}, 'nucleo_familiare': {'codice_invito'},
                'utente': {'consensi_registrazione', 'gestito_da_id'}}
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = any(table in tables and not columns.issubset({c['name'] for c in inspector.get_columns(table)}) for table, columns in expected.items())
    if not missing or not engine.url.database or engine.url.database == ':memory:':
        return None
    directory = os.path.join(os.path.dirname(os.path.abspath(engine.url.database)), 'backups')
    os.makedirs(directory, mode=0o700, exist_ok=True)
    destination = os.path.join(directory, 'pre-alpha-2.0.0-' + datetime.utcnow().strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
    with engine.connect() as connection:
        with sqlite3.connect(destination) as backup:
            connection.connection.driver_connection.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Verifica del backup database fallita')
    os.chmod(destination, 0o600)
    return destination
