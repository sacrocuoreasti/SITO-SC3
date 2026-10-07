from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from models import db, Utente, Persona, NucleoFamiliare
from services.cf_validator import normalizza_cf, valida_cf, estrai_dati_cf
import json
from datetime import datetime

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email e password sono obbligatorie'}), 400

    utente = Utente.query.filter_by(email=email).first()
    if not utente or not utente.check_password(password):
        return jsonify({'error': 'Credenziali non valide. Verifica email e password.'}), 401

    if not utente.is_attivo:
        return jsonify({'error': 'Questo account è disattivato. Contatta la segreteria parrocchiale.'}), 403

    utente.last_login = datetime.utcnow()
    db.session.commit()
    login_user(utente, remember=True)

    return jsonify({
        'success': True,
        'message': f'Benvenuto, {utente.persona.nominativo if utente.persona else utente.email}!',
        'user': utente.to_dict()
    })

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    nome = data.get('nome', '').strip()
    cognome = data.get('cognome', '').strip()
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    telefono = data.get('telefono', '').strip()
    nome_famiglia = data.get('nome_famiglia', '').strip() or f"Famiglia {cognome}"

    if not email or not password or not nome or not cognome or not cf:
        return jsonify({'error': 'Tutti i campi obbligatori (Nome, Cognome, CF, Email, Password) devono essere compilati'}), 400

    if not valida_cf(cf):
        return jsonify({'error': 'Il Codice Fiscale inserito non è formalmente valido'}), 400

    if Utente.query.filter_by(email=email).first():
        return jsonify({'error': 'Un utente con questa email esiste già nel sistema'}), 400

    if Utente.query.filter_by(codice_fiscale=cf).first():
        return jsonify({'error': 'Un utente con questo Codice Fiscale è già registrato'}), 400

    # Controlla se la Persona esiste già (ad esempio inserita prima dalla segreteria o da Excel)
    persona = db.session.get(Persona, cf)
    dati_cf = estrai_dati_cf(cf)
    
    if not persona:
        persona = Persona(
            codice_fiscale=cf,
            nome=nome,
            cognome=cognome,
            sesso=dati_cf.get('sesso', 'M'),
            data_nascita=dati_cf.get('data_nascita'),
            comune_residenza='Asti',
            cap_residenza='14100',
            telefono=telefono,
            email=email,
            ruolo_famiglia='Capofamiglia'
        )
        db.session.add(persona)
        db.session.flush()
    else:
        # Aggiorna contatti se mancanti
        if not persona.email:
            persona.email = email
        if not persona.telefono:
            persona.telefono = telefono

    # Crea o collega Nucleo Familiare
    if not persona.nucleo_id:
        nucleo = NucleoFamiliare.query.filter_by(codice_fiscale_capofamiglia=cf).first()
        if not nucleo:
            nucleo = NucleoFamiliare(
                nome_famiglia=nome_famiglia,
                codice_fiscale_capofamiglia=cf,
                telefono_principale=telefono,
                citta='Asti'
            )
            db.session.add(nucleo)
            db.session.flush()
        persona.nucleo_id = nucleo.id
        persona.ruolo_famiglia = 'Capofamiglia'

    # Se è il primissimo utente registrato in un database vuoto, diventa automaticamente Amministratore Parrocchiale
    is_first_user = Utente.query.count() == 0
    ruolo_assegnato = 'admin' if is_first_user else 'utente'
    privilegi_assegnati = ['admin', 'segreteria', 'parroco', 'catechista', 'oratorio', 'utente'] if is_first_user else ['utente']

    campi_extra_data = data.get('campi_extra', {})

    nuovo_utente = Utente(
        email=email,
        codice_fiscale=cf,
        ruolo=ruolo_assegnato,
        privilegi_extra=json.dumps(privilegi_assegnati),
        campi_extra=json.dumps(campi_extra_data),
        is_attivo=True
    )
    nuovo_utente.set_password(password)
    db.session.add(nuovo_utente)
    db.session.commit()

    login_user(nuovo_utente, remember=True)

    msg = 'Account Amministratore Parrocchiale creato con successo!' if is_first_user else 'Registrazione completata con successo!'

    return jsonify({
        'success': True,
        'message': msg,
        'user': nuovo_utente.to_dict()
    }), 201

@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json() or {}
    if 'campi_extra' in data:
        current_user.campi_extra = json.dumps(data['campi_extra'])
    if current_user.persona:
        if 'telefono' in data: current_user.persona.telefono = data['telefono'].strip()
        if 'email' in data: current_user.persona.email = data['email'].strip().lower()
    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Profilo aggiornato con successo',
        'user': current_user.to_dict()
    })

@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    session.clear()
    return jsonify({'success': True, 'message': 'Disconnessione effettuata con successo'})

@auth_bp.route('/recupera-password/richiedi', methods=['POST'])
def richiedi_recupero_password():
    """
    Invia via email (noreply@sacrocuoreasti.com) un codice di sicurezza OTP a 6 cifre
    per consentire all'utente di reimpostare la propria password.
    """
    import random
    from datetime import datetime, timedelta
    from models import PasswordResetToken
    from services.email_service import invia_codice_recupero_password

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Inserisci l\'indirizzo email del tuo account'}), 400

    utente = Utente.query.filter_by(email=email).first()
    if not utente:
        return jsonify({'error': 'Nessun account parrocchiale trovato con questa email'}), 404

    if not utente.is_attivo:
        return jsonify({'error': 'Questo account risulta disattivato. Contatta la segreteria parrocchiale.'}), 403

    # Genera codice numerico casuale a 6 cifre
    codice = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    # Invalida vecchi token pendenti
    PasswordResetToken.query.filter_by(email=email, is_used=False).update({'is_used': True})

    token = PasswordResetToken(
        email=email,
        codice=codice,
        expires_at=expires_at,
        is_used=False
    )
    db.session.add(token)
    db.session.commit()

    nominativo = utente.persona.nominativo if utente.persona else utente.email.split('@')[0]
    ok, msg = invia_codice_recupero_password(email, codice, nominativo)

    if not ok:
        # Fallback informativo se il server SMTP non dovesse rispondere
        print("Nota invio email recupero:", msg)

    return jsonify({
        'success': True,
        'message': f'Abbiamo inviato un codice di sicurezza a {email}. Controlla la tua casella di posta (e la cartella Spam).',
        'email': email
    })

@auth_bp.route('/recupera-password/conferma', methods=['POST'])
def conferma_recupero_password():
    """
    Verifica il codice OTP inviato via email e imposta la nuova password scelta dall'utente.
    """
    from datetime import datetime
    from models import PasswordResetToken

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    codice = data.get('codice', '').strip()
    nuova_password = data.get('nuova_password', '').strip()

    if not email or not codice or not nuova_password:
        return jsonify({'error': 'Email, codice di sicurezza e nuova password sono obbligatori'}), 400

    if len(nuova_password) < 6:
        return jsonify({'error': 'La nuova password deve contenere almeno 6 caratteri'}), 400

    token = PasswordResetToken.query.filter_by(
        email=email,
        codice=codice,
        is_used=False
    ).order_by(PasswordResetToken.id.desc()).first()

    if not token:
        return jsonify({'error': 'Codice di sicurezza errato o già utilizzato'}), 400

    if datetime.utcnow() > token.expires_at:
        return jsonify({'error': 'Il codice di sicurezza è scaduto (validità 15 minuti). Richiedine uno nuovo.'}), 400

    utente = Utente.query.filter_by(email=email).first()
    if not utente:
        return jsonify({'error': 'Account non trovato'}), 404

    utente.set_password(nuova_password)
    token.is_used = True
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Password reimpostata con successo! Ora puoi accedere con la nuova password.'
    })

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False, 'user': None})
    return jsonify({
        'authenticated': True,
        'user': current_user.to_dict()
    })

