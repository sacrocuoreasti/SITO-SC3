"""Backup SQLite prima delle sole migrazioni additive mancanti."""
import os
import sqlite3
from datetime import datetime
from sqlalchemy import inspect


def backup_sqlite(engine):
    expected = {'definizione_accesso': {'versione_viste','eliminato'}, 'calendario_comunita': {'tipo','origine_gruppo'}, 'celebrazione': {'data_specifica'}, 'presenza': {'gruppo_categoria','gruppo_id'}, 'persona': {'terapie_medicinali','civico_residenza','consensi_aggiunta'}, 'nucleo_familiare': {'codice_invito'},
                'utente': {'consensi_registrazione', 'gestito_da_id'},
                'gruppo_oratorio': {'eta_min','eta_max','google_calendar_url'}, 'gruppo_catechismo': {'eta_min','eta_max'},
                'gruppo_doposcuola': {'eta_min','eta_max','google_calendar_url'}}
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = any(table in tables and not columns.issubset({c['name'] for c in inspector.get_columns(table)}) for table, columns in expected.items())
    missing = missing or ('persona' in tables and 'documento_persona' not in tables)
    missing = missing or ('utente' in tables and 'definizione_accesso' not in tables)
    missing = missing or ('gruppo_doposcuola' in tables and 'gruppo_doposcuola_educatori' not in tables)
    missing = missing or ('persona' in tables and not {'gruppo_giovani','gruppo_giovani_persona','gruppo_giovani_responsabili','avviso_gruppo'}.issubset(tables))
    missing = missing or ('calendario_comunita' in tables and 'evento_calendario_comunita' not in tables)
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
