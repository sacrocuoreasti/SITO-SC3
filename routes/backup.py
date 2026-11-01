import tempfile
import hashlib
import json
import re
import zipfile
from pathlib import Path
from flask import Blueprint, current_app, jsonify, send_file, request
from flask_login import current_user
from models import db
from services.backup_service import create_backup

backup_bp = Blueprint('backup_bp', __name__, url_prefix='/api/backup')


@backup_bp.route('/export', methods=['GET'])
def export_backup():
    if not current_user.is_authenticated or 'admin' not in current_user.get_all_roles():
        return jsonify(error='Backup completo riservato agli amministratori'), 403
    if db.engine.dialect.name != 'sqlite':
        return jsonify(error='Questa esportazione richiede SQLite'), 400
    temporary = tempfile.TemporaryDirectory(prefix='sc3-export-')
    path = Path(temporary.name) / 'backup.zip'
    try:
        create_backup(db.engine.url.database, current_app.config['UPLOAD_FOLDER'], path, current_app.config['APP_VERSION'])
        response = send_file(path, as_attachment=True, download_name='cuoreinrete-backup.zip', mimetype='application/zip')
        response.direct_passthrough = False
        response.call_on_close(temporary.cleanup)
        return response
    except Exception:
        temporary.cleanup()
        raise


def is_admin():
    return current_user.is_authenticated and 'admin' in current_user.get_all_roles()


@backup_bp.route('/prepare-release', methods=['POST'])
def prepare_release():
    if not is_admin():
        return jsonify(error='Operazione riservata agli amministratori'), 403
    from services.deployment_backup import backup_secret, encrypt_archive
    target = (request.get_json() or {}).get('target_version', '')
    pattern = r'alpha (\d+)\.(\d+)\.(\d+)'
    match, current = re.fullmatch(pattern, target), re.fullmatch(pattern, current_app.config['APP_VERSION'])
    if not match or (current and tuple(map(int, match.groups())) <= tuple(map(int, current.groups()))):
        return jsonify(error='La versione di destinazione deve essere successiva a quella online'), 400
    try:
        secret = backup_secret()
    except ValueError as error:
        return jsonify(error=str(error)), 503
    if db.engine.dialect.name != 'sqlite':
        return jsonify(error='Il rilascio automatico richiede SQLite'), 400
    gate = current_app.config['RELEASE_GATE']
    try:
        state = gate.freeze(target)
    except ValueError as error:
        return jsonify(error=str(error)), 409
    temporary = tempfile.TemporaryDirectory(prefix='sc3-release-')
    try:
        archive = Path(temporary.name) / 'backup.zip'
        create_backup(db.engine.url.database, current_app.config['UPLOAD_FOLDER'], archive, current_app.config['APP_VERSION'])
        data = archive.read_bytes()
        manifest = dict(state, format=1, source_version=current_app.config['APP_VERSION'], archive_sha256=hashlib.sha256(data).hexdigest())
        encrypted = encrypt_archive(data, secret, manifest)
        manifest['encrypted_sha256'] = hashlib.sha256(encrypted).hexdigest()
        bundle = Path(temporary.name) / 'release.zip'
        with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_STORED) as output:
            output.write(archive, 'backup.zip')
            output.writestr('restore.enc', encrypted)
            output.writestr('manifest.json', json.dumps(manifest))
        response = send_file(bundle, as_attachment=True, download_name='cuoreinrete-release.zip', mimetype='application/zip')
        response.direct_passthrough = False
        response.call_on_close(temporary.cleanup)
        return response
    except Exception:
        gate.resume()
        temporary.cleanup()
        raise


@backup_bp.route('/cancel-release', methods=['POST'])
def cancel_release():
    if not is_admin():
        return jsonify(error='Operazione riservata agli amministratori'), 403
    gate = current_app.config['RELEASE_GATE']
    manifest_path = Path(current_app.config['DEPLOYMENT_DIRECTORY']) / 'manifest.json'
    if gate.state and manifest_path.exists() and json.loads(manifest_path.read_text()).get('release_id') == gate.state['release_id']:
        return jsonify(error='Il nuovo rilascio deve essere verificato prima della riapertura'), 409
    gate.resume()
    return jsonify(success=True, message='Manutenzione annullata; dati invariati')


@backup_bp.route('/complete-release', methods=['POST'])
def complete_release():
    if not is_admin():
        return jsonify(error='Operazione riservata agli amministratori'), 403
    from services.deployment_backup import verify_restored_data, backup_secret
    directory = Path(current_app.config['DEPLOYMENT_DIRECTORY'])
    if not (directory / 'manifest.json').exists():
        return jsonify(error='Nessun ripristino di rilascio da verificare'), 409
    result = verify_restored_data(directory, db.engine.url.database, current_app.config['UPLOAD_FOLDER'], backup_secret())
    if not result['matches']:
        return jsonify(result), 409
    marker = Path(db.engine.url.database).parent / '.deployment-verified.json'
    marker.write_text(json.dumps({'release_id': result['release_id']}))
    current_app.config['RELEASE_GATE'].resume()
    return jsonify(success=True, **result)
