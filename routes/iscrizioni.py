from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Iscrizione, Attivita, Persona, NucleoFamiliare, Lista
from services.cf_validator import normalizza_cf

iscrizioni_bp = Blueprint('iscrizioni_bp', __name__, url_prefix='/api/iscrizioni')

@iscrizioni_bp.route('', methods=['GET'])
def get_iscrizioni():
    attivita_id = request.args.get('attivita_id', type=int)
    stato = request.args.get('stato')
    stato_pagamento = request.args.get('stato_pagamento')
    solo_mie = request.args.get('solo_mie', '').lower() in ['true', '1']

    query = Iscrizione.query

    if solo_mie and current_user.is_authenticated:
        cf_list = []
        if current_user.persona and current_user.persona.nucleo:
            cf_list = [c.codice_fiscale for c in current_user.persona.nucleo.componenti]
        elif current_user.codice_fiscale:
            cf_list = [current_user.codice_fiscale]

        query = query.filter(
            (Iscrizione.iscritto_da_id == current_user.id) |
            (Iscrizione.codice_fiscale_partecipante.in_(cf_list))
        )

    if attivita_id:
        query = query.filter(Iscrizione.attivita_id == attivita_id)
    if stato:
        query = query.filter(Iscrizione.stato == stato)
    if stato_pagamento:
        query = query.filter(Iscrizione.stato_pagamento == stato_pagamento)

    iscrizioni = query.order_by(Iscrizione.id.desc()).all()
    return jsonify({
        'total': len(iscrizioni),
        'iscrizioni': [i.to_dict() for i in iscrizioni]
    })

@iscrizioni_bp.route('', methods=['POST'])
def create_iscrizione():
    data = request.get_json() or {}
    attivita_id = data.get('attivita_id')
    cf = normalizza_cf(data.get('codice_fiscale_partecipante', '') or data.get('codice_fiscale', ''))

    if not attivita_id or not cf:
        return jsonify({'error': 'Attività e Codice Fiscale del partecipante sono obbligatori'}), 400

    attivita = db.session.get(Attivita, attivita_id)
    if not attivita:
        return jsonify({'error': 'Attività selezionata non esistente'}), 404

    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': f'Partecipante con Codice Fiscale {cf} non presente in anagrafica'}), 404

    # Controllo fascia di età obbligatoria (es. una persona di 60 anni non si iscrive al catechismo o all'oratorio estivo)
    eta = persona.eta
    if eta is not None:
        if attivita.eta_min and eta < attivita.eta_min:
            return jsonify({
                'error': f'Età non idonea: {persona.nominativo} ha {eta} anni, ma l\'attività "{attivita.titolo}" richiede un\'età minima di {attivita.eta_min} anni.'
            }), 400
        if attivita.eta_max and eta > attivita.eta_max:
            return jsonify({
                'error': f'Età non idonea: {persona.nominativo} ha {eta} anni, ma l\'attività "{attivita.titolo}" è riservata a ragazzi fino a {attivita.eta_max} anni.'
            }), 400

    # Controllo clausole d'iscrizione (obbligatorie vs facoltative personalizzabili da segreteria)
    import json
    from models import ClausolaIscrizione
    clausole_attive = ClausolaIscrizione.query.filter_by(is_attiva=True).all()
    clausole_input = data.get('clausole_accettate', {})
    if not isinstance(clausole_input, dict):
        clausole_input = {}

    for c in clausole_attive:
        accettata = bool(clausole_input.get(str(c.id)) or clausole_input.get(c.id) or clausole_input.get(f'clausola_{c.id}'))
        if c.is_obbligatoria and not accettata:
            return jsonify({'error': f'È obbligatorio accettare la clausola: "{c.titolo}" per procedere con l\'iscrizione.'}), 400

    # Controlla se è già iscritto a questa attività
    esistente = Iscrizione.query.filter_by(
        attivita_id=attivita_id,
        codice_fiscale_partecipante=cf
    ).first()

    if esistente:
        return jsonify({'error': f'{persona.nominativo} è già iscritto/a a {attivita.titolo}'}), 409

    # Controllo posti disponibili
    if attivita.posti_disponibili is not None and attivita.posti_disponibili <= 0:
        return jsonify({'error': f'I posti per "{attivita.titolo}" sono esauriti'}), 400

    # Se sono state fornite note sanitarie o aggiornamenti, salvali anche nella scheda persona
    if data.get('allergie'):
        persona.allergie = data['allergie'].strip()
    if data.get('intolleranze_alimentari'):
        persona.intolleranze_alimentari = data['intolleranze_alimentari'].strip()

    quota = attivita.quota_iscrizione
    iscritto_da_id = current_user.id if current_user.is_authenticated else None

    campi_pers_input = data.get('campi_personalizzati', {})
    if not isinstance(campi_pers_input, dict):
        campi_pers_input = {}

    nuova = Iscrizione(
        attivita_id=attivita_id,
        codice_fiscale_partecipante=cf,
        iscritto_da_id=iscritto_da_id,
        stato='confermata',
        stato_pagamento='da_pagare' if quota > 0 else 'esente',
        importo_dovuto=quota,
        importo_pagato=0.0,
        note_iscrizione=data.get('note_iscrizione', '').strip(),
        squadra=data.get('squadra', '').strip(),
        consenso_privacy=data.get('consenso_privacy', True),
        consenso_foto=data.get('consenso_foto', True),
        consenso_uscite=data.get('consenso_uscite', True),
        clausole_accettate=json.dumps(clausole_input),
        campi_personalizzati=json.dumps(campi_pers_input)
    )

    db.session.add(nuova)

    # Associazione automatica alla Lista dell'attività (lato segreteria, un utente può stare in più liste)
    lista_att = Lista.query.filter_by(attivita_id=attivita_id).first()
    if not lista_att:
        colore_badge = '#059669' if attivita.categoria == 'oratorio' else ('#d97706' if attivita.categoria == 'catechismo' else '#8B1E1E')
        lista_att = Lista(
            nome=f"Iscritti: {attivita.titolo}",
            descrizione=f"Elenco iscritti all'attività {attivita.titolo} ({attivita.anno_pastorale})",
            colore=colore_badge,
            attivita_id=attivita_id
        )
        db.session.add(lista_att)
        db.session.flush()

    if persona not in lista_att.membri:
        lista_att.membri.append(persona)

    # Associazione facoltativa a un Gruppo Catechismo selezionato
    gruppo_cat_id = data.get('gruppo_catechismo_id')
    if gruppo_cat_id:
        from models import GruppoCatechismo
        try:
            grp = db.session.get(GruppoCatechismo, int(gruppo_cat_id))
            if grp and persona not in grp.ragazzi:
                grp.ragazzi.append(persona)
        except Exception:
            pass

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Iscrizione di {persona.nominativo} registrata con successo e associata alla lista "{lista_att.nome}"!',
        'iscrizione': nuova.to_dict()
    }), 201

@iscrizioni_bp.route('/<int:id>/stato', methods=['PUT'])
def update_stato(id):
    isc = db.session.get(Iscrizione, id)
    if not isc:
        return jsonify({'error': 'Iscrizione non trovata'}), 404

    data = request.get_json(silent=True) or {}
    nuovo_stato = data.get('stato')
    if nuovo_stato not in ['in_attesa', 'confermata', 'rifiutata', 'annullata']:
        return jsonify({'error': 'Stato non valido'}), 400

    isc.stato = nuovo_stato
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Stato iscrizione aggiornato a "{nuovo_stato}"',
        'iscrizione': isc.to_dict()
    })

@iscrizioni_bp.route('/<int:id>/pagamento', methods=['PUT'])
def update_pagamento(id):
    isc = db.session.get(Iscrizione, id)
    if not isc:
        return jsonify({'error': 'Iscrizione non trovata'}), 404

    data = request.get_json() or {}
    if 'importo_pagato' in data:
        isc.importo_pagato = float(data['importo_pagato'])
    
    if 'stato_pagamento' in data:
        isc.stato_pagamento = data['stato_pagamento']
    else:
        # Calcolo automatico
        if isc.importo_pagato >= isc.importo_dovuto and isc.importo_dovuto > 0:
            isc.stato_pagamento = 'saldato'
        elif isc.importo_pagato > 0:
            isc.stato_pagamento = 'acconto'
        elif isc.importo_dovuto == 0:
            isc.stato_pagamento = 'esente'
        else:
            isc.stato_pagamento = 'da_pagare'

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Pagamento registrato con successo',
        'iscrizione': isc.to_dict()
    })

@iscrizioni_bp.route('/<int:id>/squadra', methods=['PUT'])
def update_squadra(id):
    isc = db.session.get(Iscrizione, id)
    if not isc:
        return jsonify({'error': 'Iscrizione non trovata'}), 404

    data = request.get_json() or {}
    isc.squadra = data.get('squadra', '').strip()
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Squadra aggiornata a "{isc.squadra}"',
        'iscrizione': isc.to_dict()
    })

@iscrizioni_bp.route('/<int:id>', methods=['DELETE'])
def delete_iscrizione(id):
    isc = db.session.get(Iscrizione, id)
    if not isc:
        return jsonify({'error': 'Iscrizione non trovata'}), 404

    # Controllo permessi disiscrizione
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'segreteria', 'parroco'] for r in roles)
        if not is_staff:
            user_cf = (current_user.codice_fiscale or '').upper()
            family_cfs = []
            if current_user.persona and current_user.persona.nucleo:
                family_cfs = [(c.codice_fiscale or '').upper() for c in current_user.persona.nucleo.componenti]
            part_cf = (isc.codice_fiscale_partecipante or '').upper()
            is_owner = (isc.iscritto_da_id == current_user.id or part_cf == user_cf or part_cf in family_cfs)
            if not is_owner:
                return jsonify({'error': 'Non sei autorizzato a disiscrivere questo partecipante'}), 403

    db.session.delete(isc)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Disiscrizione completata con successo'})

@iscrizioni_bp.route('/bulk-pagamento', methods=['POST'])
def bulk_pagamento():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Non autorizzato'}), 401
    roles = current_user.get_all_roles()
    if not any(r in ['admin', 'segreteria', 'parroco'] for r in roles):
        return jsonify({'error': 'Privilegi insufficienti'}), 403

    data = request.get_json() or {}
    ids = data.get('ids', [])
    stato_pagamento = data.get('stato_pagamento', 'saldato')
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'Nessuna iscrizione selezionata'}), 400

    updated_count = 0
    for i_id in ids:
        isc = db.session.get(Iscrizione, i_id)
        if isc:
            isc.stato_pagamento = stato_pagamento
            if stato_pagamento == 'saldato':
                isc.importo_pagato = isc.importo_dovuto
            elif stato_pagamento == 'da_pagare':
                isc.importo_pagato = 0.0
            updated_count += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Stato pagamento aggiornato per {updated_count} iscrizioni',
        'count': updated_count
    })

@iscrizioni_bp.route('/bulk-delete', methods=['POST'])
def bulk_delete_iscrizioni():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Non autorizzato'}), 401
    roles = current_user.get_all_roles()
    if not any(r in ['admin', 'segreteria', 'parroco'] for r in roles):
        return jsonify({'error': 'Privilegi insufficienti'}), 403

    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'Nessuna iscrizione selezionata'}), 400

    deleted_count = 0
    for i_id in ids:
        isc = db.session.get(Iscrizione, i_id)
        if isc:
            db.session.delete(isc)
            deleted_count += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Eliminate {deleted_count} iscrizioni',
        'count': deleted_count
    })

