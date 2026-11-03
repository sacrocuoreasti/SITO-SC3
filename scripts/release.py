"""Release conservativa: backup online, archivio locale, copia cifrata, push, ripristino e confronto."""
import argparse
import getpass
import hashlib
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backup_service import verify_backup
from services.deployment_backup import validate_release_files


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


class ReleaseClient:
    def __init__(self, url, email, password):
        if not url.startswith('https://'):
            raise ValueError('Il servizio online deve usare HTTPS')
        self.url, self.email, self.password = url.rstrip('/'), email, password
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, data=None, binary=False):
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                                         headers={'Content-Type': 'application/json'} if data is not None else {})
        with self.opener.open(request, timeout=120) as response:
            return response.read() if binary else json.load(response)

    def login(self):
        result = self.request('/api/auth/login', {'email': self.email, 'password': self.password})
        if not result.get('success') or 'admin' not in result['user'].get('tutti_i_ruoli', []):
            raise ValueError('È richiesto un account amministratore')


def store_bundle(bundle, version):
    directory = ROOT / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / ('predeploy-' + version.replace(' ', '-') + '-' + datetime.utcnow().strftime('%Y%m%dT%H%M%S%f') + '.zip')
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(bundle)
    with zipfile.ZipFile(path) as archive:
        if set(archive.namelist()) != {'backup.zip', 'restore.enc', 'manifest.json'}:
            raise ValueError('Bundle di release non valido')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['target_version'] != version:
            raise ValueError('Versione del backup non corrispondente')
        plain = archive.read('backup.zip')
        encrypted = archive.read('restore.enc')
        if hashlib.sha256(plain).hexdigest() != manifest['archive_sha256'] or hashlib.sha256(encrypted).hexdigest() != manifest['encrypted_sha256']:
            raise ValueError('Checksum del bundle non valido')
        local = path.with_name(path.stem + '-data.zip')
        descriptor = os.open(str(local), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(plain)
        verify_backup(local)
        deployment = ROOT / '.deployment'
        deployment.mkdir(exist_ok=True)
        (deployment / 'restore.enc').write_bytes(encrypted)
        (deployment / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    validate_release_files(ROOT / '.deployment', version)
    return path


def run_release(client, version=None):
    if git('branch', '--show-current') != 'main' or git('status', '--porcelain'):
        raise ValueError('Eseguire da main con modifiche al codice già committate e working tree pulito')
    client.login()
    online = client.request('/health')['version']
    match = re.fullmatch(r'alpha (\d+)\.(\d+)\.(\d+)', online)
    if not match:
        raise ValueError('La versione online non supporta il flusso di release')
    target = version or 'alpha ' + '.'.join([match[1], match[2], str(int(match[3]) + 1)])
    if not re.fullmatch(r'alpha \d+\.\d+\.\d+', target):
        raise ValueError('Formato versione non valido')
    # Controlli prima di mettere online la manutenzione.
    for command in [[sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], ['node', '--check', 'static/js/app.js'], ['node','--check','static/js/group-calendar.js'], ['node','--check','static/js/portal-views.js'], ['node','--check','static/js/access-control.js'],
                    ['node', 'tests/test_frontend.js'], ['node', 'tests/test_google_script.js'], ['node', 'tests/test_family_frontend.js']]:
        subprocess.run(command, cwd=ROOT, check=True)
    pushed = False
    try:
        bundle = client.request('/api/backup/prepare-release', {'target_version': target}, binary=True)
        path = store_bundle(bundle, target)
        print('Backup online verificato e conservato in locale:', path, flush=True)
        (ROOT / 'VERSION').write_text(target + '\n')
        package = json.loads((ROOT / 'package.json').read_text())
        package['version'] = target.split(' ', 1)[1]
        (ROOT / 'package.json').write_text(json.dumps(package, indent=2) + '\n')
        validate_release_files(ROOT / '.deployment', target)
        git('add', 'VERSION', 'package.json', '.deployment/manifest.json', '.deployment/restore.enc')
        git('commit', '-m', 'Release ' + target + ' with verified online data snapshot')
        revision = git('rev-parse', 'HEAD')
        pushed = True  # Un errore di rete dopo il push non deve riaprire le scritture sul vecchio server.
        subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT, check=True)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            try:
                health = client.request('/health')
                if health.get('revision') == revision and health.get('version') == target:
                    client.login()  # La sessione precedente può essere scaduta durante il riavvio.
                    result = client.request('/api/backup/complete-release', {})
                    if result.get('matches') is not True:
                        raise ValueError('Il confronto dopo il deploy non è riuscito')
                    print('Deploy verificato: dati e allegati invariati. Sito riaperto.', flush=True)
                    return result
            except (OSError, urllib.error.HTTPError):
                pass
            time.sleep(5)
        raise RuntimeError('Deploy non concluso entro 10 minuti: manutenzione mantenuta. Verificare Render; non forzare un ripristino vuoto.')
    except Exception:
        if not pushed:
            try:
                client.request('/api/backup/cancel-release', {})
            except Exception:
                pass
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://sito-sc3.onrender.com')
    parser.add_argument('--version')
    parser.add_argument('--cancel', action='store_true')
    args = parser.parse_args()
    client = ReleaseClient(args.url, input('Email amministratore: ').strip(), getpass.getpass('Password: '))
    if args.cancel:
        client.login()
        client.request('/api/backup/cancel-release', {})
        print('Manutenzione annullata')
    else:
        run_release(client, args.version)
