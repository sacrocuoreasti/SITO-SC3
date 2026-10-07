from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Utente, Persona
import json

utenti_bp = Blueprint('utenti_bp', __name__, url_prefix='/api/utenti')

@utenti_bp.route('', methods=['GET'])
def get_utenti():
    """Restituisce tutti gli account utente con le anagrafiche e i privilegi associati."""
    solo_permessi = request.args.get('solo_con_permessi', '').lower() in ['true', '1']
    utenti = Utente.query.order_by(Utente.id.asc()).all()
    if solo_permessi:
        staff_roles = {'admin', 'segreteria', 'parroco', 'catechista', 'oratorio'}
        utenti = [u for u in utenti if any(r in staff_roles for r in u.get_all_roles())]
    return jsonify({
        'total': len(utenti),
        'utenti': [u.to_dict() for u in utenti]
    })

@utenti_bp.route('', methods=['POST'])
def create_utente():
    """
    Crea un nuovo account utente con Codice Fiscale, Email, Password Temporanea e Privilegi.
    Se viene fornito il CF e la persona non esiste in anagrafica, viene creata la scheda anagrafica di base.
    """
    from services.cf_validator import normalizza_cf

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    ruolo = data.get('ruolo', 'utente').strip()
    raw_cf = data.get('codice_fiscale', '').strip()
    cf = normalizza_cf(raw_cf) if raw_cf else None

    if not email or not password:
        return jsonify({'error': 'Email e password sono obbligatorie'}), 400

    if Utente.query.filter_by(email=email).first():
        return jsonify({'error': 'Un account con questa email esiste già'}), 400

    if cf and Utente.query.filter_by(codice_fiscale=cf).first():
        return jsonify({'error': 'Un utente con questo Codice Fiscale è già registrato'}), 400

    valid_roles = ['utente', 'genitore', 'oratorio', 'catechista', 'segreteria', 'parroco', 'admin']
    if ruolo not in valid_roles:
        ruolo = 'utente'

    privilegi = data.get('privilegi', [ruolo])
    if not isinstance(privilegi, list):
        privilegi = [ruolo]
    if ruolo not in privilegi:
        privilegi.append(ruolo)

    # Se è specificato il CF, assicura che esista una Persona associata per soddisfare la foreign key
    if cf:
        persona = db.session.get(Persona, cf)
        if not persona:
            nome = data.get('nome', '').strip() or email.split('@')[0].capitalize()
            cognome = data.get('cognome', '').strip() or 'Parrocchiano'
            persona = Persona(
                codice_fiscale=cf,
                nome=nome,
                cognome=cognome,
                email=email,
                telefono=data.get('telefono', '').strip()
            )
            db.session.add(persona)
            db.session.flush()

    nuovo = Utente(
        email=email,
        codice_fiscale=cf,
        ruolo=ruolo,
        privilegi_extra=json.dumps(privilegi),
        is_attivo=True
    )
    nuovo.set_password(password)
    db.session.add(nuovo)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Account {nuovo.email} ({nuovo.ruolo}) creato con successo',
        'utente': nuovo.to_dict()
    }), 201

@utenti_bp.route('/<int:id>/ruoli', methods=['PUT'])
def update_ruoli(id):
    """
    Consente di aggiornare il ruolo primario e tutti i privilegi/ruoli multipli
    ('utente', 'genitore', 'oratorio', 'catechista', 'segreteria', 'admin', 'parroco').
    """
    utente = db.session.get(Utente, id)
    if not utente:
        return jsonify({'error': 'Utente non trovato'}), 404

    data = request.get_json() or {}
    ruolo_primario = data.get('ruolo')
    privilegi_lista = data.get('privilegi', [])

    valid_roles = ['utente', 'genitore', 'oratorio', 'catechista', 'segreteria', 'parroco', 'admin']

    if ruolo_primario and ruolo_primario in valid_roles:
        utente.ruolo = ruolo_primario

    if isinstance(privilegi_lista, list):
        clean_privs = [r for r in privilegi_lista if r in valid_roles]
        utente.privilegi_extra = json.dumps(clean_privs)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Privilegi aggiornati per {utente.email}',
        'utente': utente.to_dict()
    })

@utenti_bp.route('/<int:id>/stato', methods=['PUT'])
def toggle_stato(id):
    utente = db.session.get(Utente, id)
    if not utente:
        return jsonify({'error': 'Utente non trovato'}), 404

    data = request.get_json(silent=True) or {}
    if 'is_attivo' in data:
        utente.is_attivo = bool(data['is_attivo'])
    else:
        utente.is_attivo = not utente.is_attivo

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Stato utente impostato a: {"Attivo" if utente.is_attivo else "Disattivato"}',
        'utente': utente.to_dict()
    })

@utenti_bp.route('/<int:id>/reset-password', methods=['POST'])
def reset_password(id):
    import secrets
    from services.email_service import invia_notifica_nuova_password

    utente = db.session.get(Utente, id)
    if not utente:
        return jsonify({'error': 'Utente non trovato'}), 404

    data = request.get_json() or {}
    nuova_pw = data.get('nuova_password', '').strip()
    if not nuova_pw:
        # Genera password temporanea casuale
        nuova_pw = f"SC-{secrets.randbelow(899999) + 100000}"

    utente.set_password(nuova_pw)
    db.session.commit()

    # Invia notifica email all'utente
    invia_email_notifica = data.get('invia_email', True)
    email_inviata = False
    if invia_email_notifica and utente.email:
        nominativo = utente.persona.nominativo if utente.persona else utente.email.split('@')[0]
        email_inviata, _ = invia_notifica_nuova_password(utente.email, nuova_pw, nominativo)

    msg = f'Password per {utente.email} reimpostata con successo su: {nuova_pw}'
    if email_inviata:
        msg += ' (inviata anche via email all\'utente)'

    return jsonify({
        'success': True,
        'nuova_password': nuova_pw,
        'email_inviata': email_inviata,
        'message': msg
    })

@utenti_bp.route('/<int:id>', methods=['DELETE'])
def delete_utente(id):
    if current_user.is_authenticated and current_user.id == id:
        return jsonify({'error': 'Non puoi eliminare il tuo stesso account mentre sei autenticato'}), 400

    utente = db.session.get(Utente, id)
    if not utente:
        return jsonify({'error': 'Utente non trovato'}), 404

    from models import Iscrizione, GruppoCatechismo
    for isc in Iscrizione.query.filter_by(iscritto_da_id=id).all():
        isc.iscritto_da_id = None
    for grp in GruppoCatechismo.query.filter_by(catechista_utente_id=id).all():
        grp.catechista_utente_id = None

    db.session.delete(utente)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Utente {utente.email} eliminato con successo'})

@utenti_bp.route('/bulk-stato', methods=['POST'])
def bulk_stato():
    """Modifica lo stato di attivazione di più utenti contemporaneamente."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    nuovo_stato = bool(data.get('is_attivo', True))

    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'Nessun utente specificato'}), 400

    conteggio = 0
    for uid in ids:
        if current_user.is_authenticated and current_user.id == uid and not nuovo_stato:
            continue
        u = db.session.get(Utente, uid)
        if u:
            u.is_attivo = nuovo_stato
            conteggio += 1

    db.session.commit()
    azione = "attivati" if nuovo_stato else "disattivati"
    return jsonify({
        'success': True,
        'message': f'{conteggio} utenti {azione} con successo',
        'conteggio': conteggio
    })

@utenti_bp.route('/bulk-privilegi', methods=['POST'])
def bulk_privilegi():
    """Aggiunge o rimuove un privilegio a una lista di utenti."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    ruolo_azione = data.get('azione', 'aggiungi')
    ruolo_target = data.get('ruolo', '').strip().lower()

    valid_roles = ['utente', 'genitore', 'oratorio', 'catechista', 'segreteria', 'parroco', 'admin']
    if ruolo_target not in valid_roles:
        return jsonify({'error': f'Ruolo non valido: {ruolo_target}'}), 400

    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'Nessun utente specificato'}), 400

    conteggio = 0
    for uid in ids:
        u = db.session.get(Utente, uid)
        if not u:
            continue

        try:
            current_privs = json.loads(u.privilegi_extra or '[]')
        except Exception:
            current_privs = []

        if not isinstance(current_privs, list):
            current_privs = [u.ruolo]

        if ruolo_azione == 'aggiungi':
            if ruolo_target not in current_privs:
                current_privs.append(ruolo_target)
            u.privilegi_extra = json.dumps(current_privs)
            conteggio += 1
        elif ruolo_azione == 'rimuovi':
            if current_user.is_authenticated and current_user.id == uid and ruolo_target == 'admin':
                continue
            if ruolo_target in current_privs:
                current_privs.remove(ruolo_target)
            if not current_privs:
                current_privs = ['utente']
            if u.ruolo == ruolo_target:
                u.ruolo = current_privs[0]
            u.privilegi_extra = json.dumps(current_privs)
            conteggio += 1

    db.session.commit()
    msg = f'Privilegio "{ruolo_target}" {"assegnato a" if ruolo_azione == "aggiungi" else "rimosso da"} {conteggio} utenti'
    return jsonify({
        'success': True,
        'message': msg,
        'conteggio': conteggio
    })

@utenti_bp.route('/bulk-delete', methods=['POST'])
def bulk_delete():
    """Elimina più utenti contemporaneamente con controlli di sicurezza."""
    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])

    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'Nessun utente specificato'}), 400

    from models import Iscrizione, GruppoCatechismo

    conteggio = 0
    for uid in ids:
        if current_user.is_authenticated and current_user.id == uid:
            continue
        u = db.session.get(Utente, uid)
        if u:
            for isc in Iscrizione.query.filter_by(iscritto_da_id=uid).all():
                isc.iscritto_da_id = None
            for grp in GruppoCatechismo.query.filter_by(catechista_utente_id=uid).all():
                grp.catechista_utente_id = None
            db.session.delete(u)
            conteggio += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{conteggio} utenti eliminati con successo',
        'conteggio': conteggio
    })


