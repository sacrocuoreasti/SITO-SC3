import os
import secrets
import gzip
from functools import lru_cache
from pathlib import Path
from flask import Flask, render_template, send_from_directory, jsonify, request, abort, g
from flask_login import LoginManager, current_user
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from config import Config
from models import db, Utente
from services.quick_login import quick_login_enabled

@lru_cache(maxsize=8)
def compressed_asset(data):
    return gzip.compress(data, compresslevel=5, mtime=0)


login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)
    app.config['APP_VERSION'] = app.config.get('APP_VERSION') or (Path(app.root_path) / 'VERSION').read_text().strip()
    from sqlalchemy.engine import make_url
    from services.deployment_backup import ReleaseGate, restore_snapshot, backup_secret
    database_url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    database_path = database_url.database if database_url.get_backend_name() == 'sqlite' and database_url.database != ':memory:' else None
    deployment_directory = Path(app.config.get('DEPLOYMENT_DIRECTORY', Path(app.root_path) / '.deployment'))
    restored = None
    if os.environ.get('RENDER') == 'true' and (not app.testing or app.config.get('DEPLOYMENT_RESTORE_IN_TESTS')):
        key = backup_secret()
        if database_path:
            restored = restore_snapshot(deployment_directory, app.config['APP_VERSION'], database_path, app.config['UPLOAD_FOLDER'], key)
    gate = ReleaseGate(Path(database_path).parent / '.release-state.json' if database_path else None)
    app.config['RELEASE_GATE'] = gate
    app.config['DEPLOYMENT_DIRECTORY'] = str(deployment_directory)
    verified_marker = Path(database_path).parent / '.deployment-verified.json' if database_path else None
    import json
    verified_release = json.loads(verified_marker.read_text()).get('release_id') if verified_marker and verified_marker.exists() else None
    if restored and not gate.state and verified_release != restored['release_id']:
        gate.freeze(restored['target_version'], restored['release_id'])

    @app.before_request
    def release_admission():
        if not request.path.startswith('/api/'):
            return
        if request.blueprint == 'backup_bp' or request.endpoint in {'auth_bp.login', 'auth_bp.logout', 'auth_bp.get_current_user'}:
            return
        if not gate.admit():
            response = jsonify(error='Aggiornamento in corso. Riprova tra poco.', success=False)
            response.headers['Retry-After'] = '30'
            return response, 503
        g.release_admitted = True

    @app.teardown_request
    def release_finished(error):
        if g.pop('release_admitted', False):
            gate.leave()


    @app.context_processor
    def release_context():
        return {'app_version': app.config['APP_VERSION']}

    # Assicura esistenza cartelle database e upload
    os.makedirs(os.path.join(os.environ.get('DATA_DIR', app.root_path), 'database'), exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    if not app.config.get('SECRET_KEY'):
        # Compatibilità con servizi già attivi: chiave privata locale, mai hardcoded.
        key_path = Path(os.environ.get('DATA_DIR', app.root_path)) / 'database' / '.session-key'
        try:
            fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as key_file:
                key_file.write(secrets.token_hex(32))
        app.config['SECRET_KEY'] = key_path.read_text().strip()
        if not app.config['SECRET_KEY']:
            raise RuntimeError('Chiave di sessione locale vuota: impostare SECRET_KEY.')
        app.logger.warning('SECRET_KEY assente: usata chiave locale. Su Render configurare una chiave stabile.')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth_bp.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(Utente, int(user_id))
        except (TypeError, ValueError):
            return None
        return user if user and user.is_attivo else None

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error='Accedi per continuare', success=False), 401

    @app.before_request
    def protect_api():
        if not request.path.startswith('/api/') or request.endpoint is None:
            return
        public_endpoints = {
            'auth_bp.login', 'auth_bp.register', 'auth_bp.get_current_user',
            'auth_bp.richiedi_recupero_password', 'auth_bp.conferma_recupero_password',
            'persone_bp.validate_cf_endpoint', 'auth_bp.registration_options',
        }
        public_get = (
            request.method in {'GET', 'HEAD', 'OPTIONS'} and (
                request.blueprint in {'impostazioni_bp', 'configurazioni_bp', 'celebrazioni_bp'}
                or request.endpoint in {'attivita_bp.get_attivita', 'attivita_bp.get_attivita_detail'}
            )
        )
        if request.endpoint in public_endpoints or public_get:
            # Le API accettano oggetti JSON, mai liste o scalari.
            if request.is_json and not isinstance(request.get_json(), dict):
                abort(400, description='Il corpo JSON deve essere un oggetto')
            return
        if not current_user.is_authenticated:
            abort(401)
        roles = set(current_user.get_all_roles())
        staff = bool(roles & {'admin', 'parroco', 'segreteria'})
        if request.blueprint in {'utenti_bp', 'segreteria_bp', 'excel_bp', 'liste_bp'} and not staff:
            abort(403)
        if request.blueprint in {'impostazioni_bp', 'configurazioni_bp', 'celebrazioni_bp', 'attivita_bp'} and not staff:
            abort(403)
        if request.is_json and not isinstance(request.get_json(), dict):
            abort(400, description='Il corpo JSON deve essere un oggetto')

    # Registrazione Blueprint API
    from routes.auth import auth_bp
    from routes.persone import persone_bp
    from routes.famiglie import famiglie_bp
    from routes.attivita import attivita_bp
    from routes.iscrizioni import iscrizioni_bp
    from routes.oratorio import oratorio_bp
    from routes.catechismo import catechismo_bp
    from routes.segreteria import segreteria_bp
    from routes.utenti import utenti_bp
    from routes.excel_routes import excel_bp
    from routes.liste import liste_bp
    from routes.impostazioni import impostazioni_bp
    from routes.configurazioni import configurazioni_bp
    from routes.celebrazioni import celebrazioni_bp
    from routes.doposcuola import doposcuola_bp

    from routes.backup import backup_bp
    app.register_blueprint(backup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(persone_bp)
    app.register_blueprint(famiglie_bp)
    app.register_blueprint(attivita_bp)
    app.register_blueprint(iscrizioni_bp)
    app.register_blueprint(oratorio_bp)
    app.register_blueprint(catechismo_bp)
    app.register_blueprint(doposcuola_bp)
    app.register_blueprint(segreteria_bp)
    app.register_blueprint(utenti_bp)
    app.register_blueprint(excel_bp)
    app.register_blueprint(liste_bp)
    app.register_blueprint(impostazioni_bp)
    app.register_blueprint(configurazioni_bp)
    app.register_blueprint(celebrazioni_bp)

    @app.route('/')
    def index():
        version = os.environ.get('RENDER_GIT_COMMIT') or str(max(os.stat(app.static_folder + '/' + name).st_mtime_ns for name in ['css/style.css', 'js/app.js']))
        return render_template('index.html', asset_version=version, quick_login_enabled=quick_login_enabled())

    @app.route('/health')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify(status='ok', app='Parrocchia Sacro Cuore Asti', revision=os.environ.get('RENDER_GIT_COMMIT', 'local'), version=app.config['APP_VERSION'], maintenance=bool(gate.state), backup_ready=bool(os.environ.get('BACKUP_ENCRYPTION_KEY') or os.environ.get('GOOGLE_SCRIPT_SECRET')))
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception('Health check database fallito')
            return jsonify(status='unavailable'), 503

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error=error.description, success=False), error.code
        return error

    @app.errorhandler(IntegrityError)
    def handle_conflict(error):
        db.session.rollback()
        app.logger.warning('Conflitto di integrità su %s', request.path)
        return jsonify(error='I dati sono già presenti o collegati ad altri record. Aggiorna la pagina e riprova.', success=False), 409

    @app.errorhandler(OperationalError)
    def handle_database_unavailable(error):
        db.session.rollback()
        app.logger.exception('Database temporaneamente non disponibile')
        response = jsonify(error='Servizio temporaneamente occupato. Riprova tra poco.', success=False)
        response.headers['Retry-After'] = '5'
        return response, 503

    @app.errorhandler(500)
    def handle_500(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify(error='Errore interno del server. Riprova tra poco.', success=False), 500
        return 'Errore interno del server', 500

    @app.after_request
    def response_headers(response):
        if request.path.startswith('/api/') or request.path == '/health':
            response.headers['Cache-Control'] = 'no-store'
        # Comprime solo documenti pubblici e asset, mai risposte API con dati personali.
        if request.path == '/' or request.path.startswith('/static/'):
            response.vary.add('Accept-Encoding')
            if request.path == '/':
                response.headers['Cache-Control'] = 'no-cache'
            elif request.args.get('v') and response.status_code == 200:
                response.headers['Cache-Control'] = 'public, max-age=86400'
            if (request.method == 'GET' and response.status_code == 200
                    and request.accept_encodings['gzip'] > 0
                    and response.mimetype in {'text/html', 'text/css', 'text/javascript', 'application/javascript'}
                    and 'Content-Encoding' not in response.headers and 'Range' not in request.headers):
                response.direct_passthrough = False
                data = response.get_data()
                if len(data) > 1024:
                    response.set_data(compressed_asset(data))
                    response.headers['Content-Encoding'] = 'gzip'
                    etag, _ = response.get_etag()
                    if etag:
                        response.set_etag(etag, weak=True)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/template_anagrafica_sacro_cuore.xlsx')
    def serve_template():
        return send_from_directory(app.root_path, 'template_anagrafica_sacro_cuore.xlsx')

    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    with app.app_context():
        from models import init_default_configurazioni
        if db.engine.dialect.name == 'sqlite':
            @event.listens_for(db.engine, 'connect')
            def sqlite_connection(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute('PRAGMA busy_timeout=30000')
                cursor.close()
            with db.engine.connect() as connection:
                connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        init_default_configurazioni()

    @app.cli.command('create-admin')
    def create_admin():
        """Crea un amministratore da terminale, senza password nel codice."""
        import click
        email = click.prompt('Email amministratore').strip().lower()
        if Utente.query.filter_by(email=email).first():
            raise click.ClickException('Account già esistente: nessuna modifica eseguita.')
        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        if len(password) < 12:
            raise click.ClickException('Usa almeno 12 caratteri.')
        user = Utente(email=email, ruolo='admin', privilegi_extra='["admin"]', is_attivo=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo('Amministratore creato.')

    return app

def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    application = create_app()
    port = int(os.environ.get('PORT', 5001))
    local_ip = get_local_ip()
    print("=" * 65)
    print(" ⛪ PORTALE PARROCCHIALE SACRO CUORE DI GESÙ - ASTI")
    print("=" * 65)
    print(f" 💻 Accesso su questo computer:   http://127.0.0.1:{port}")
    print(f" 📱 Accesso da Rete Locale/Wi-Fi: http://{local_ip}:{port}")
    print(" (Puoi aprire questo indirizzo da smartphone, tablet o altri PC connessi al Wi-Fi)")
    print("=" * 65)
    application.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')
