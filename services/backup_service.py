"""Snapshot completo: SQLite Backup API, allegati e manifest verificabile."""
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


def create_backup(database_path, uploads_path, destination, version):
    database_path = Path(database_path).resolve()
    if not database_path.is_file():
        raise ValueError('Database SQLite non trovato; nessun backup creato')
    with tempfile.TemporaryDirectory(prefix='sc3-snapshot-') as temporary:
        snapshot = Path(temporary) / 'sacro_cuore.db'
        with sqlite3.connect('file:' + quote(str(database_path)) + '?mode=ro', uri=True) as source:
            with sqlite3.connect(str(snapshot)) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Verifica integrità database fallita')
                tables = [r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                counts = {table: target.execute('SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0] for table in tables}
        files = [('database/sacro_cuore.db', snapshot)]
        uploads = Path(uploads_path).resolve()
        if uploads.is_dir():
            for path in sorted(uploads.rglob('*')):
                if path.is_file() and not path.is_symlink() and uploads in path.resolve().parents:
                    files.append(('uploads/' + path.relative_to(uploads).as_posix(), path))
        manifest = {'format': 1, 'version': version, 'created_at': datetime.utcnow().isoformat() + 'Z', 'tables': counts, 'files': {}}
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, path in files:
                        content = path.read_bytes()
                        manifest['files'][name] = hashlib.sha256(content).hexdigest()
                        archive.writestr(name, content)
                    archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        verify_backup(destination)
        return manifest


def verify_backup(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or 'database/sacro_cuore.db' not in manifest.get('files', {}):
            raise ValueError('Formato backup non riconosciuto')
        if set(archive.namelist()) != set(manifest['files']) | {'manifest.json'}:
            raise ValueError('Contenuto archivio non coerente con il manifest')
        for name, checksum in manifest['files'].items():
            if name.startswith('/') or '..' in Path(name).parts or not (name == 'database/sacro_cuore.db' or name.startswith('uploads/')):
                raise ValueError('Percorso non valido nel backup')
            if hashlib.sha256(archive.read(name)).hexdigest() != checksum:
                raise ValueError('Checksum del backup non valido')
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / 'check.db'
            database.write_bytes(archive.read('database/sacro_cuore.db'))
            with sqlite3.connect(str(database)) as connection:
                if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Database del backup non integro')
                for table, expected in manifest['tables'].items():
                    count = connection.execute('SELECT COUNT(*) FROM "' + table.replace('"', '""') + '"').fetchone()[0]
                    if count != expected:
                        raise ValueError('Conteggio dei record non valido')
        return manifest
