"""Ripristino offline verificato. Fermare il server e impostare DATA_DIR prima di avviarlo."""
import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backup_service import verify_backup, create_backup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--server-stopped', action='store_true', required=True)
    args = parser.parse_args()
    manifest = verify_backup(args.archive)
    destination = Path(args.data_dir).resolve()
    database = destination / 'database/sacro_cuore.db'
    if database.exists():
        create_backup(database, destination / 'uploads', destination / 'backups' / ('before-restore-' + datetime.utcnow().strftime('%Y%m%dT%H%M%S%f') + '.zip'), 'before-restore')
    with zipfile.ZipFile(args.archive) as archive:
        for name in manifest['files']:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination not in target.resolve().parents:
                raise SystemExit('Destinazione non valida')
            # Non sovrascrivere allegati già esistenti con contenuto differente.
            if name.startswith('uploads/') and target.exists() and target.read_bytes() != archive.read(name):
                raise SystemExit('Allegato con lo stesso nome già presente: ripristinare in una directory vuota')
        for name in manifest['files']:
            target = destination / name
            temporary = target.with_name(target.name + '.restore-tmp')
            temporary.write_bytes(archive.read(name))
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
    for suffix in ('-wal', '-shm'):
        Path(str(database) + suffix).unlink(missing_ok=True)
    print('Ripristino completato e verificato. Versione backup:', manifest['version'])
