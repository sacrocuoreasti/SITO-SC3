"""Backup di rilascio cifrati, ripristino all'avvio e barriera di manutenzione."""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from services.backup_service import verify_backup

MAGIC = b'SC3BACKUP1\n'


def backup_secret():
    value = os.environ.get('BACKUP_ENCRYPTION_KEY') or os.environ.get('GOOGLE_SCRIPT_SECRET', '')
    if len(value) < 32:
        raise ValueError('Configurare BACKUP_ENCRYPTION_KEY o GOOGLE_SCRIPT_SECRET (almeno 32 caratteri)')
    return value.encode('utf-8')


def _key(secret, salt):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b'CuoreInRete deployment backup v1').derive(secret)


def _aad(manifest):
    return json.dumps({k: manifest[k] for k in ('target_version', 'release_id')}, sort_keys=True).encode()


def encrypt_archive(data, secret, manifest):
    salt, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + salt + nonce + AESGCM(_key(secret, salt)).encrypt(nonce, data, _aad(manifest))


def decrypt_archive(data, secret, manifest):
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 44:
        raise ValueError('Formato del backup cifrato non valido')
    offset = len(MAGIC)
    salt, nonce = data[offset:offset+16], data[offset+16:offset+28]
    return AESGCM(_key(secret, salt)).decrypt(nonce, data[offset+28:], _aad(manifest))


def validate_release_files(directory, version):
    directory = Path(directory)
    manifest_file = directory / 'manifest.json'
    if not manifest_file.exists():
        bootstrap = json.loads((directory / 'bootstrap.json').read_text())
        if bootstrap.get('bootstrap_version') != version:
            raise ValueError('Deploy bloccato: manca il backup online per questa versione')
        return None
    manifest = json.loads(manifest_file.read_text())
    if manifest.get('format') != 1 or manifest.get('target_version') != version:
        raise ValueError('Deploy bloccato: il backup appartiene a un’altra versione')
    encrypted = (directory / 'restore.enc').read_bytes()
    if hashlib.sha256(encrypted).hexdigest() != manifest.get('encrypted_sha256'):
        raise ValueError('Checksum del backup cifrato non valido')
    return manifest


def restore_snapshot(directory, version, database, uploads, secret):
    manifest = validate_release_files(directory, version)
    if manifest is None:
        return None
    marker = Path(database).parent / '.deployment-restored.json'
    if marker.exists() and json.loads(marker.read_text()).get('release_id') == manifest['release_id']:
        return manifest
    data = decrypt_archive((Path(directory) / 'restore.enc').read_bytes(), secret, manifest)
    if hashlib.sha256(data).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Archivio ripristino non corrispondente al manifest')
    with tempfile.TemporaryDirectory() as temporary:
        archive_path = Path(temporary) / 'backup.zip'
        archive_path.write_bytes(data)
        content = verify_backup(archive_path)
        # Validare tutto prima di sostituire il database dell'immagine Docker.
        destinations = {}
        for name in content['files']:
            target = Path(database) if name == 'database/sacro_cuore.db' else Path(uploads) / name[len('uploads/'):]
            if name.startswith('uploads/') and Path(uploads).resolve() not in target.resolve().parents:
                raise ValueError('Percorso allegato non valido')
            destinations[name] = target
        expected_uploads = {name[len('uploads/'):] for name in content['files'] if name.startswith('uploads/')}
        upload_root = Path(uploads)
        if upload_root.exists():
            for existing in upload_root.rglob('*'):
                if existing.is_file() and not existing.is_symlink() and existing.relative_to(upload_root).as_posix() not in expected_uploads:
                    saved = Path(database).parent / 'backups' / ('extra-files-' + manifest['release_id']) / existing.relative_to(upload_root)
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(existing), str(saved))
        with zipfile.ZipFile(archive_path) as archive:
            for name, target in destinations.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                pending = target.with_name(target.name + '.restore-tmp')
                pending.write_bytes(archive.read(name))
                os.chmod(pending, 0o600)
                os.replace(pending, target)
    for suffix in ('-wal', '-shm'):
        Path(str(database) + suffix).unlink(missing_ok=True)
    marker.write_text(json.dumps({'release_id': manifest['release_id']}))
    return manifest


def verify_restored_data(directory, database, uploads, secret):
    manifest = json.loads((Path(directory) / 'manifest.json').read_text())
    archive = decrypt_archive((Path(directory) / 'restore.enc').read_bytes(), secret, manifest)
    differences = []
    with tempfile.TemporaryDirectory() as temporary:
        source_file = Path(temporary) / 'source.db'
        archive_file = Path(temporary) / 'backup.zip'
        archive_file.write_bytes(archive)
        content = verify_backup(archive_file)
        with zipfile.ZipFile(archive_file) as backup:
            source_file.write_bytes(backup.read('database/sacro_cuore.db'))
            with sqlite3.connect(str(source_file)) as source, sqlite3.connect(str(database)) as live:
                for table in content['tables']:
                    quoted_table = '"' + table.replace('"', '""') + '"'
                    columns = [r[1] for r in source.execute('PRAGMA table_info(' + quoted_table + ')') if r[1] != 'last_login']
                    names = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
                    before = source.execute('SELECT ' + names + ' FROM ' + quoted_table).fetchall()
                    after = live.execute('SELECT ' + names + ' FROM ' + quoted_table).fetchall()
                    if sorted(before, key=repr) != sorted(after, key=repr):
                        differences.append(table)
            for name, checksum in content['files'].items():
                if name.startswith('uploads/'):
                    path = Path(uploads) / name[len('uploads/'):]
                    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                        differences.append('allegati')
                        break
    return {'matches': not differences, 'differences': differences, 'release_id': manifest['release_id']}


class ReleaseGate:
    def __init__(self, state_file=None):
        self.condition = threading.Condition()
        self.active = 0
        self.state_file = Path(state_file) if state_file else None
        self.state = json.loads(self.state_file.read_text()) if self.state_file and self.state_file.exists() else None

    def admit(self):
        with self.condition:
            if self.state:
                return False
            self.active += 1
            return True

    def leave(self):
        with self.condition:
            self.active -= 1
            self.condition.notify_all()

    def freeze(self, target_version, release_id=None):
        with self.condition:
            if self.state:
                raise ValueError('Un aggiornamento è già in preparazione. Completarlo o annullarlo.')
            self.state = {'target_version': target_version, 'release_id': release_id or secrets.token_hex(16)}
            self._save()
            while self.active:
                self.condition.wait(timeout=1)
            return dict(self.state)

    def resume(self):
        with self.condition:
            self.state = None
            if self.state_file:
                self.state_file.unlink(missing_ok=True)
            self.condition.notify_all()

    def _save(self):
        if self.state_file:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(self.state))
            os.chmod(self.state_file, 0o600)
