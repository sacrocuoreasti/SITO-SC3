"""Scarica il backup completo autenticandosi come amministratore, senza salvare credenziali."""
import argparse
import getpass
import http.cookiejar
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backup_service import verify_backup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://sito-sc3.onrender.com')
    parser.add_argument('--output', default=str(ROOT / 'backups' / ('online-' + datetime.utcnow().strftime('%Y%m%dT%H%M%S') + '.zip')))
    args = parser.parse_args()
    if not args.url.startswith('https://'):
        raise SystemExit('Usare un URL HTTPS')
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    credentials = {'email': input('Email amministratore: ').strip(), 'password': getpass.getpass('Password: ')}
    request = urllib.request.Request(args.url.rstrip('/') + '/api/auth/login', data=json.dumps(credentials).encode(), headers={'Content-Type': 'application/json'})
    with opener.open(request, timeout=30) as response:
        if not json.load(response).get('success'):
            raise SystemExit('Accesso non riuscito')
    del credentials, request
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as target:
            with opener.open(args.url.rstrip('/') + '/api/backup/export', timeout=120) as response:
                if response.headers.get_content_type() != 'application/zip':
                    raise ValueError('Il server non ha restituito un backup ZIP')
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
        manifest = verify_backup(output)
        print('Backup online scaricato e verificato:', output)
        print('Versione:', manifest['version'], 'File:', len(manifest['files']))
    except Exception:
        output.unlink(missing_ok=True)
        raise
