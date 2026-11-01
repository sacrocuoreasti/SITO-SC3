import os
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from models import db, Utente, Persona, NucleoFamiliare, RichiestaNucleo
from services.family_service import FAMILY_ROLES, HEALTH_PRESETS, REGISTRATION_CONSENTS, consent_record
from services.cf_validator import normalizza_cf, valida_cf, estrai_dati_cf
import json
from datetime import datetime

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if (email == 'a' and not password and os.environ.get('LOCAL_QUICK_LOGIN') == '1'
            and not os.environ.get('RENDER') and request.remote_addr in {'127.0.0.1', '::1'}):
        utente = Utente.query.filter_by(email='admin@sacrocuoreasti.com').first()
        if utente and utente.is_attivo and utente.has_role('admin'):
            login_user(utente, remember=False)
            return jsonify(success=True, message='Accesso effettuato', user=utente.to_dict())

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

@auth_bp.route('/registration-options', methods=['GET'])
def registration_options():
    return jsonify(ruoli_famiglia=FAMILY_ROLES, salute=HEALTH_PRESETS, consensi=REGISTRATION_CONSENTS)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    fields = ('email', 'password', 'nome', 'cognome', 'codice_fiscale', 'telefono', 'nome_famiglia', 'codice_invito', 'ruolo_famiglia')
    if any(not isinstance(data.get(field, ''), str) for field in fields):
        return jsonify(error='Formato dei campi di registrazione non valido'), 400
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    nome = data.get('nome', '').strip()
    cognome = data.get('cognome', '').strip()
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    telefono = data.get('telefono', '').strip()
    role = data.get('ruolo_famiglia', 'Altro')
    code = data.get('codice_invito', '').strip().upper()
    if not all((email, password, nome, cognome, cf)) or '@' not in email or len(password) < 8:
        return jsonify(error='Compila i campi obbligatori e usa una password di almeno 8 caratteri'), 400
    if role not in FAMILY_ROLES or not valida_cf(cf):
        return jsonify(error='Codice fiscale o ruolo familiare non valido'), 400
    try:
        consents = consent_record(data)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if Utente.query.filter((Utente.email == email) | (Utente.codice_fiscale == cf)).first():
        return jsonify(error='Email o codice fiscale già associati a un account'), 409
    invited_family = NucleoFamiliare.query.filter_by(codice_invito=code).first() if code else None
    if code and (len(code) != 3 or not invited_family):
        return jsonify(error='Codice famiglia non valido'), 400
    persona = db.session.get(Persona, cf)
    if persona and persona.nucleo_id:
        return jsonify(error='Scheda già presente in un nucleo: chiedi al capofamiglia di attivare il tuo account'), 409
    if not persona:
        dati_cf = estrai_dati_cf(cf)
        persona = Persona(codice_fiscale=cf, nome=nome, cognome=cognome,
                          sesso=dati_cf.get('sesso', 'M'), data_nascita=dati_cf.get('data_nascita'),
                          telefono=telefono, email=email, ruolo_famiglia=role)
        db.session.add(persona)
        db.session.flush()
    else:
        if not persona.email:
            persona.email = email
        if not persona.telefono:
            persona.telefono = telefono
        persona.ruolo_famiglia = role
    if not invited_family:
        family = NucleoFamiliare(nome_famiglia=data.get('nome_famiglia', '').strip() or f'Famiglia {cognome}',
                                codice_fiscale_capofamiglia=cf, telefono_principale=telefono,
                                indirizzo=persona.indirizzo_residenza, citta=persona.comune_residenza or 'Asti')
        db.session.add(family)
        db.session.flush()
        persona.nucleo_id = family.id
    nuovo = Utente(email=email, codice_fiscale=cf, ruolo='utente', privilegi_extra='["utente"]',
                   consensi_registrazione=consents, campi_extra=json.dumps(data.get('campi_extra', {})), is_attivo=True)
    nuovo.set_password(password)
    db.session.add(nuovo)
    db.session.flush()
    if invited_family:
        db.session.add(RichiestaNucleo(nucleo_id=invited_family.id, utente_id=nuovo.id))
    db.session.commit()
    login_user(nuovo, remember=True)
    message = 'Account creato. La richiesta di ingresso nel nucleo attende l’approvazione del capofamiglia.' if invited_family else 'Registrazione completata con successo!'
    return jsonify(success=True, message=message, user=nuovo.to_dict()), 201

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
    import secrets
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

    recent = PasswordResetToken.query.filter_by(email=email, is_used=False).filter(
        PasswordResetToken.created_at > datetime.utcnow() - timedelta(seconds=60)
    ).first()
    if recent:
        return jsonify(error='Un codice è già stato richiesto. Attendi un minuto prima di riprovare.'), 429

    # Genera codice numerico casuale a 6 cifre
    codice = str(secrets.randbelow(900000) + 100000)
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
        token.is_used = True
        db.session.commit()
        return jsonify(error='Invio email temporaneamente non disponibile. Contatta la segreteria.'), 503

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

