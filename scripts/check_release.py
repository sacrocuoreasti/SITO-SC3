"""Verifica senza chiavi che ogni nuova versione abbia il proprio backup cifrato."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.deployment_backup import validate_release_files
validate_release_files(ROOT / '.deployment', (ROOT / 'VERSION').read_text().strip())
print('Protezione dati del rilascio verificata')
