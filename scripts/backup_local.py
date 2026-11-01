"""Eseguire dalla root: python scripts/backup_local.py --database ... --uploads ..."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backup_service import create_backup

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=str(ROOT / 'database/sacro_cuore.db'))
    parser.add_argument('--uploads', default=str(ROOT / 'uploads'))
    parser.add_argument('--output', default=str(ROOT / 'backups' / ('backup-' + datetime.utcnow().strftime('%Y%m%dT%H%M%S') + '.zip')))
    args = parser.parse_args()
    result = create_backup(args.database, args.uploads, args.output, (ROOT / 'VERSION').read_text().strip())
    print('Backup locale verificato:', args.output)
    print('Tabelle:', len(result['tables']), 'File:', len(result['files']))
