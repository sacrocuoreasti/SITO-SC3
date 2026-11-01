import os
import secrets
from pathlib import Path
from flask import Flask, render_template, send_from_directory, jsonify, request, abort
from flask_login import LoginManager, current_user
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from config import Config
from models import db, Utente

login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

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
            'persone_bp.validate_cf_endpoint',
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
        return render_template('index.html')

    @app.route('/health')
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify(status='ok', app='Parrocchia Sacro Cuore Asti', revision=os.environ.get('RENDER_GIT_COMMIT', 'local'))
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
