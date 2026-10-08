from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from models import db, Persona, NucleoFamiliare, Utente
from services.cf_validator import normalizza_cf, valida_cf, estrai_dati_cf
from datetime import datetime

persone_bp = Blueprint('persone_bp', __name__, url_prefix='/api/persone')

@persone_bp.route('/validate-cf', methods=['POST'])
def validate_cf_endpoint():
    data = request.get_json() or {}
    raw_cf = data.get('codice_fiscale', '')
    cf = normalizza_cf(raw_cf)
    is_valid = valida_cf(cf)
    info = estrai_dati_cf(cf) if (is_valid or len(cf) == 16) else {}
    
    # Controlla se è già censito nel database
    persona_esistente = db.session.get(Persona, cf) if len(cf) == 16 else None

    return jsonify({
        'codice_fiscale': cf,
        'valido': is_valid,
        'estratto': info,
        'gia_presente': bool(persona_esistente),
        'nominativo_esistente': persona_esistente.nominativo if persona_esistente else None
    })

@persone_bp.route('', methods=['GET'])
def get_persone():
    q = request.args.get('q', '').strip()
    nucleo_id = request.args.get('nucleo_id', type=int)
    ruolo_famiglia = request.args.get('ruolo_famiglia', '').strip()
    solo_allergie = request.args.get('solo_allergie', '').lower() in ['true', '1']

    query = Persona.query

    if q:
        search = f"%{q}%"
        query = query.filter(
            (Persona.cognome.ilike(search)) |
            (Persona.nome.ilike(search)) |
            (Persona.codice_fiscale.ilike(search)) |
            (Persona.telefono.ilike(search))
        )

    if nucleo_id:
        query = query.filter(Persona.nucleo_id == nucleo_id)

    if ruolo_famiglia:
        query = query.filter(Persona.ruolo_famiglia == ruolo_famiglia)

    if solo_allergie:
        query = query.filter(
            (Persona.allergie.isnot(None) & (Persona.allergie != '')) |
            (Persona.intolleranze_alimentari.isnot(None) & (Persona.intolleranze_alimentari != ''))
        )

    # Restrizione profilo utente: l'utente normale non deve vedere l'anagrafica pastorale globale
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'segreteria', 'parroco', 'catechista', 'educatore', 'oratorio'] for r in roles)
        if not is_staff:
            if current_user.persona and current_user.persona.nucleo_id:
                query = query.filter(Persona.nucleo_id == current_user.persona.nucleo_id)
            elif current_user.persona:
                query = query.filter(Persona.codice_fiscale == current_user.persona.codice_fiscale)
            else:
                return jsonify({'total': 0, 'persone': []})

    persone = query.order_by(Persona.cognome.asc(), Persona.nome.asc()).all()
    return jsonify({
        'total': len(persone),
        'persone': [p.to_dict() for p in persone]
    })

@persone_bp.route('/<cf>', methods=['GET'])
def get_persona(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': f'Nessuna persona trovata con Codice Fiscale {cf}'}), 404

    # Controllo permessi accesso scheda persona
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'segreteria', 'parroco', 'catechista'] for r in roles)
        if not is_staff:
            user_cf = (current_user.codice_fiscale or '').upper()
            family_cfs = []
            if current_user.persona and current_user.persona.nucleo:
                family_cfs = [(c.codice_fiscale or '').upper() for c in current_user.persona.nucleo.componenti]
            if cf != user_cf and cf not in family_cfs:
                return jsonify({'error': 'Non autorizzato a visualizzare dati di fedeli esterni al tuo nucleo'}), 403

    return jsonify({'persona': p.to_dict()})

@persone_bp.route('', methods=['POST'])
def create_persona():
    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    nome = data.get('nome', '').strip()
    cognome = data.get('cognome', '').strip()

    if not cf or not nome or not cognome:
        return jsonify({'error': 'Codice Fiscale, Nome e Cognome sono campi obbligatori'}), 400

    if not valida_cf(cf):
        return jsonify({'error': 'Il Codice Fiscale inserito non è valido secondo l\'algoritmo ufficiale'}), 400

    if db.session.get(Persona, cf):
        return jsonify({'error': f'Una persona con Codice Fiscale {cf} è già registrata nell\'anagrafica'}), 409

    data_nascita = None
    data_str = data.get('data_nascita')
    if data_str:
        try:
            data_nascita = datetime.strptime(data_str, '%Y-%m-%d').date()
        except Exception:
            pass

    sesso = data.get('sesso', '').upper()
    if not sesso or not data_nascita:
        dati_cf = estrai_dati_cf(cf)
        if not sesso and 'sesso' in dati_cf:
            sesso = dati_cf['sesso']
        if not data_nascita and 'data_nascita' in dati_cf:
            data_nascita = dati_cf['data_nascita']

    persona = Persona(
        codice_fiscale=cf,
        nome=nome,
        cognome=cognome,
        sesso=sesso if sesso in ['M', 'F'] else 'M',
        data_nascita=data_nascita,
        luogo_nascita=data.get('luogo_nascita', '').strip(),
        provincia_nascita=data.get('provincia_nascita', '').strip(),
        indirizzo_residenza=data.get('indirizzo_residenza', '').strip(),
        comune_residenza=data.get('comune_residenza', 'Asti').strip(),
        cap_residenza=data.get('cap_residenza', '14100').strip(),
        provincia_residenza=data.get('provincia_residenza', 'AT').strip(),
        telefono=data.get('telefono', '').strip(),
        email=data.get('email', '').strip().lower(),
        intolleranze_alimentari=data.get('intolleranze_alimentari', '').strip(),
        allergie=data.get('allergie', '').strip(),
        note_generali=data.get('note_generali', '').strip(),
        nucleo_id=data.get('nucleo_id') or (current_user.persona.nucleo_id if (current_user.is_authenticated and current_user.persona) else None),
        ruolo_famiglia=data.get('ruolo_famiglia', 'Figlio/a')
    )

    db.session.add(persona)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Persona registrata con successo',
        'persona': persona.to_dict()
    }), 201

@persone_bp.route('/<cf>', methods=['PUT'])
def update_persona(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    # Controllo permessi modifica scheda anagrafica
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'segreteria', 'parroco', 'catechista'] for r in roles)
        if not is_staff:
            user_cf = (current_user.codice_fiscale or '').upper()
            family_cfs = []
            if current_user.persona and current_user.persona.nucleo:
                family_cfs = [(c.codice_fiscale or '').upper() for c in current_user.persona.nucleo.componenti]
            if cf != user_cf and cf not in family_cfs:
                return jsonify({'error': 'Non autorizzato a modificare persone esterne al tuo nucleo'}), 403

    data = request.get_json() or {}

    if 'nome' in data: p.nome = data['nome'].strip()
    if 'cognome' in data: p.cognome = data['cognome'].strip()
    if 'sesso' in data and data['sesso'] in ['M', 'F']: p.sesso = data['sesso']
    if 'data_nascita' in data and data['data_nascita']:
        try:
            p.data_nascita = datetime.strptime(data['data_nascita'], '%Y-%m-%d').date()
        except Exception:
            pass
    if 'luogo_nascita' in data: p.luogo_nascita = data['luogo_nascita'].strip()
    if 'indirizzo_residenza' in data: p.indirizzo_residenza = data['indirizzo_residenza'].strip()
    if 'comune_residenza' in data: p.comune_residenza = data['comune_residenza'].strip()
    if 'cap_residenza' in data: p.cap_residenza = data['cap_residenza'].strip()
    if 'telefono' in data: p.telefono = data['telefono'].strip()
    if 'email' in data: p.email = data['email'].strip().lower()
    if 'intolleranze_alimentari' in data: p.intolleranze_alimentari = data['intolleranze_alimentari'].strip()
    if 'allergie' in data: p.allergie = data['allergie'].strip()
    if 'note_generali' in data: p.note_generali = data['note_generali'].strip()
    if 'ruolo_famiglia' in data: p.ruolo_famiglia = data['ruolo_famiglia'].strip()
    if 'nucleo_id' in data: p.nucleo_id = data['nucleo_id']

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Scheda anagrafica aggiornata',
        'persona': p.to_dict()
    })

@persone_bp.route('/<cf>/certificato-battesimo', methods=['POST'])
def upload_certificato_battesimo(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    if 'certificato' not in request.files:
        return jsonify({'error': 'Nessun file selezionato'}), 400

    file = request.files['certificato']
    if not file or file.filename == '':
        return jsonify({'error': 'File non valido'}), 400

    import os
    from flask import current_app
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.jpg', '.jpeg', '.png', '.webp']:
        return jsonify({'error': 'Formato file non supportato. Carica un PDF o un\'immagine (JPG, PNG).'}), 400

    filename = f"battesimo_{cf}_{int(datetime.utcnow().timestamp())}{ext}"
    mimetype = file.content_type or 'application/octet-stream'

    from services.google_drive import is_google_drive_configured, upload_file_to_drive, delete_file_from_drive

    if is_google_drive_configured():
        drive_res = upload_file_to_drive(file, filename, mimetype=mimetype)
        if drive_res.get('success'):
            if p.certificato_battesimo_path:
                delete_file_from_drive(p.certificato_battesimo_path)
            p.certificato_battesimo_path = drive_res.get('direct_url') or drive_res.get('url')
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Certificato di battesimo salvato su Google Drive per {p.nominativo}',
                'persona': p.to_dict()
            })

    # Fallback locale se Drive non è configurato
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.seek(0)
    file.save(filepath)

    # Rimuovi eventuale vecchio certificato locale
    if p.certificato_battesimo_path and not p.certificato_battesimo_path.startswith('http') and p.certificato_battesimo_path != filename:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], p.certificato_battesimo_path)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except Exception: pass

    p.certificato_battesimo_path = filename
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Certificato di battesimo per {p.nominativo} caricato con successo',
        'persona': p.to_dict()
    })

@persone_bp.route('/<cf>/certificato-battesimo', methods=['DELETE'])
def delete_certificato_battesimo(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    if p.certificato_battesimo_path:
        import os
        from flask import current_app
        from services.google_drive import delete_file_from_drive
        if p.certificato_battesimo_path.startswith('http'):
            delete_file_from_drive(p.certificato_battesimo_path)
        else:
            old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], p.certificato_battesimo_path)
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except Exception: pass
        p.certificato_battesimo_path = None
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Certificato di battesimo rimosso',
        'persona': p.to_dict()
    })

# ================= GESTIONE FOTO PROFILO / AVATAR =================
@persone_bp.route('/<cf>/foto-profilo', methods=['POST'])
def upload_foto_profilo(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    # Controllo permessi: admin/segreteria o utente proprietario / membro della stessa famiglia
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'parroco', 'segreteria', 'oratorio', 'catechista'] for r in roles)
        if not is_staff:
            curr_persona = current_user.persona
            if not curr_persona or (curr_persona.codice_fiscale != cf and curr_persona.nucleo_id != p.nucleo_id):
                return jsonify({'error': 'Non autorizzato a modificare la foto profilo di questo utente'}), 403

    if 'foto' not in request.files and 'file' not in request.files:
        return jsonify({'error': 'Nessun file immagine selezionato'}), 400

    file = request.files.get('foto') or request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'File non valido'}), 400

    import os
    from flask import current_app
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
        return jsonify({'error': 'Formato non supportato. Carica un\'immagine (JPG, PNG, WebP)'}), 400

    filename = f"avatar_{cf}_{int(datetime.utcnow().timestamp())}{ext}"
    mimetype = file.content_type or 'image/jpeg'

    from services.google_drive import is_google_drive_configured, upload_file_to_drive, delete_file_from_drive

    if is_google_drive_configured():
        drive_res = upload_file_to_drive(file, filename, mimetype=mimetype)
        if drive_res.get('success'):
            if p.foto_profilo_url:
                delete_file_from_drive(p.foto_profilo_url)
            p.foto_profilo_url = drive_res.get('direct_url') or drive_res.get('url')
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Foto profilo aggiornata con successo su Google Drive per {p.nominativo}!',
                'persona': p.to_dict()
            })

    # Fallback locale se Drive non è configurato
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.seek(0)
    file.save(filepath)

    if p.foto_profilo_url and not p.foto_profilo_url.startswith('http'):
        old_local = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(p.foto_profilo_url))
        if os.path.exists(old_local):
            try: os.remove(old_local)
            except Exception: pass

    p.foto_profilo_url = f"/uploads/{filename}"
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Foto profilo salvata con successo per {p.nominativo}!',
        'persona': p.to_dict()
    })

@persone_bp.route('/<cf>/foto-profilo', methods=['DELETE'])
def delete_foto_profilo(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    if p.foto_profilo_url:
        import os
        from flask import current_app
        from services.google_drive import delete_file_from_drive
        if p.foto_profilo_url.startswith('http'):
            delete_file_from_drive(p.foto_profilo_url)
        else:
            old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.basename(p.foto_profilo_url))
            if os.path.exists(old_path):
                try: os.remove(old_path)
                except Exception: pass
        p.foto_profilo_url = None
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Foto profilo rimossa',
        'persona': p.to_dict()
    })

@persone_bp.route('/<cf>', methods=['DELETE'])
def delete_persona(cf):
    cf = normalizza_cf(cf)
    p = db.session.get(Persona, cf)
    if not p:
        return jsonify({'error': 'Persona non trovata'}), 404

    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Persona eliminata con successo'})

@persone_bp.route('/bulk-delete', methods=['POST'])
def bulk_delete_persone():
    data = request.get_json(silent=True) or {}
    cfs = data.get('cfs', [])
    if not isinstance(cfs, list) or not cfs:
        return jsonify({'error': 'Nessuna persona specificata'}), 400

    from services.cf_validator import normalizza_cf
    conteggio = 0
    for raw_cf in cfs:
        cf = normalizza_cf(raw_cf)
        p = db.session.get(Persona, cf)
        if p:
            db.session.delete(p)
            conteggio += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{conteggio} schede anagrafiche eliminate con successo',
        'conteggio': conteggio
    })

@persone_bp.route('/bulk-aggiungi-lista', methods=['POST'])
def bulk_aggiungi_lista():
    data = request.get_json(silent=True) or {}
    cfs = data.get('cfs', [])
    lista_id = data.get('lista_id')

    if not lista_id:
        return jsonify({'error': 'ID lista obbligatorio'}), 400

    from models import Lista
    lista = db.session.get(Lista, lista_id)
    if not lista:
        return jsonify({'error': 'Lista parrocchiale non trovata'}), 404

    from services.cf_validator import normalizza_cf
    conteggio = 0
    for raw_cf in cfs:
        cf = normalizza_cf(raw_cf)
        p = db.session.get(Persona, cf)
        if p and p not in lista.membri:
            lista.membri.append(p)
            conteggio += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{conteggio} persone aggiunte alla lista "{lista.nome}"',
        'conteggio': conteggio
    })

