import os
from flask import Flask, render_template, send_from_directory, jsonify
from flask_login import LoginManager
from config import Config
from models import db, Utente

login_manager = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

    # Assicura esistenza cartelle database e upload
    os.makedirs(os.path.join(app.root_path, 'database'), exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth_bp.login'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Utente, int(user_id))

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
        return jsonify({'status': 'ok', 'app': 'Parrocchia Sacro Cuore Asti'})

    @app.route('/template_anagrafica_sacro_cuore.xlsx')
    def serve_template():
        return send_from_directory(app.root_path, 'template_anagrafica_sacro_cuore.xlsx')

    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    with app.app_context():
        from models import init_default_configurazioni
        db.create_all()
        init_default_configurazioni()

    return app

if __name__ == '__main__':
    application = create_app()
    port = int(os.environ.get('PORT', 5001))
    print(f"Server avviato su http://127.0.0.1:{port}")
    application.run(host='0.0.0.0', port=port, debug=True)
