import tempfile
from pathlib import Path
from flask import Blueprint, current_app, jsonify, send_file
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
        response.call_on_close(temporary.cleanup)
        return response
    except Exception:
        temporary.cleanup()
        raise
