from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Iscrizione, Persona, Presenza, GruppoOratorio, Utente
from services.cf_validator import normalizza_cf
from datetime import date, datetime

oratorio_bp = Blueprint('oratorio_bp', __name__, url_prefix='/api/oratorio')

@oratorio_bp.route('/animatori', methods=['GET'])
def get_animatori():
    """Ritorna tutti gli utenti o persone registrate che hanno il ruolo/privilegio di animatore o oratorio."""
    utenti = Utente.query.filter(Utente.is_attivo == True).all()
    animatori = []
    for u in utenti:
        roles = u.get_all_roles()
        if any(r in ['oratorio', 'animatore', 'admin', 'segreteria'] for r in roles) or u.ruolo in ['oratorio', 'animatore']:
            animatori.append({
                'id': u.id,
                'email': u.email,
                'codice_fiscale': u.codice_fiscale or '',
                'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                'telefono': u.persona.telefono if u.persona else ''
            })
    return jsonify({
        'total': len(animatori),
        'animatori': animatori
    })

@oratorio_bp.route('/gruppi', methods=['GET'])
def get_gruppi_oratorio():
    """
    Ritorna i gruppi di oratorio (estivo e invernale) configurati.
    Filtri opzionali: tipo_oratorio ('estivo' o 'invernale'), anno_pastorale.
    """
    tipo = request.args.get('tipo_oratorio', '').strip().lower()
    anno = request.args.get('anno_pastorale', '').strip()

    query = GruppoOratorio.query
    if tipo:
        query = query.filter_by(tipo_oratorio=tipo)
    if anno:
        query = query.filter_by(anno_pastorale=anno)

    gruppi_db = query.order_by(GruppoOratorio.id.asc()).all()

    # Filtro visibilità per utenti non staff
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_staff = any(r in ['admin', 'parroco', 'segreteria', 'oratorio', 'animatore'] for r in roles)
        if not is_staff:
            gruppi_db = [g for g in gruppi_db if g.stato in ['pubblico', 'chiuso']]

    gruppi = [g.to_dict(include_ragazzi=True) for g in gruppi_db]

    # Attività correlate
    attivita_oratorio = Attivita.query.filter(Attivita.categoria.in_(['oratorio', 'campo_estivo'])).all()

    return jsonify({
        'gruppi': gruppi,
        'attivita_oratorio': [a.to_dict() for a in attivita_oratorio]
    })

@oratorio_bp.route('/gruppi', methods=['POST'])
def create_gruppo_oratorio():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome del gruppo oratorio è obbligatorio'}), 400

    tipo_oratorio = data.get('tipo_oratorio', 'estivo').strip().lower()
    if tipo_oratorio not in ['estivo', 'invernale']:
        tipo_oratorio = 'estivo'

    stato = data.get('stato', 'pubblico').strip().lower()
    if stato not in ['pubblico', 'bozza', 'chiuso']:
        stato = 'pubblico'

    nuovo = GruppoOratorio(
        nome=nome,
        anno_pastorale=data.get('anno_pastorale', '2026/2027').strip(),
        tipo_oratorio=tipo_oratorio,
        animatore_referente_nome=data.get('animatore_referente_nome', '').strip(),
        animatore_cf=normalizza_cf(data.get('animatore_cf', '')) or None,
        animatore_utente_id=data.get('animatore_utente_id') or None,
        giorni_orari=data.get('giorni_orari', '').strip(),
        aula=data.get('aula', '').strip(),
        note=data.get('note', '').strip(),
        stato=stato,
        attivita_id=data.get('attivita_id') or None
    )

    animatori_ids = data.get('animatori_ids', [])
    if isinstance(animatori_ids, list) and animatori_ids:
        for uid in animatori_ids:
            u = db.session.get(Utente, uid)
            if u and u not in nuovo.animatori:
                nuovo.animatori.append(u)

    db.session.add(nuovo)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Gruppo Oratorio "{nuovo.nome}" ({nuovo.tipo_oratorio.capitalize()}) creato con successo',
        'gruppo': nuovo.to_dict(include_ragazzi=True)
    }), 201

@oratorio_bp.route('/gruppi/<int:id>', methods=['GET'])
def get_gruppo_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo Oratorio non trovato'}), 404
    return jsonify({'gruppo': g.to_dict(include_ragazzi=True)})

@oratorio_bp.route('/gruppi/<int:id>', methods=['PUT'])
def update_gruppo_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo Oratorio non trovato'}), 404

    data = request.get_json() or {}
    if 'nome' in data: g.nome = data['nome'].strip()
    if 'anno_pastorale' in data: g.anno_pastorale = data['anno_pastorale'].strip()
    if 'tipo_oratorio' in data:
        t = data['tipo_oratorio'].strip().lower()
        if t in ['estivo', 'invernale']: g.tipo_oratorio = t
    if 'animatore_referente_nome' in data: g.animatore_referente_nome = data['animatore_referente_nome'].strip()
    if 'animatore_cf' in data: g.animatore_cf = normalizza_cf(data['animatore_cf']) or None
    if 'animatore_utente_id' in data: g.animatore_utente_id = data['animatore_utente_id'] or None
    if 'giorni_orari' in data: g.giorni_orari = data['giorni_orari'].strip()
    if 'aula' in data: g.aula = data['aula'].strip()
    if 'note' in data: g.note = data['note'].strip()
    if 'stato' in data:
        s = data['stato'].strip().lower()
        if s in ['pubblico', 'bozza', 'chiuso']: g.stato = s
    if 'attivita_id' in data: g.attivita_id = data['attivita_id'] or None

    if 'animatori_ids' in data and isinstance(data['animatori_ids'], list):
        g.animatori = []
        for uid in data['animatori_ids']:
            u = db.session.get(Utente, uid)
            if u and u not in g.animatori:
                g.animatori.append(u)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Gruppo Oratorio "{g.nome}" aggiornato',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@oratorio_bp.route('/gruppi/<int:id>', methods=['DELETE'])
def delete_gruppo_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404
    db.session.delete(g)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Gruppo oratorio eliminato con successo'})

@oratorio_bp.route('/gruppi/<int:id>/ragazzi', methods=['POST'])
def add_ragazzo_gruppo_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': f'Nessuna persona trovata con Codice Fiscale {cf}'}), 404

    if persona not in g.ragazzi:
        g.ragazzi.append(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{persona.nominativo} iscritto/a al gruppo "{g.nome}"',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@oratorio_bp.route('/gruppi/<int:id>/ragazzi/batch', methods=['POST'])
def add_ragazzi_batch_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    cfs = data.get('codici_fiscali', [])
    if not isinstance(cfs, list) or not cfs:
        return jsonify({'error': 'Nessuna persona selezionata per l\'assegnazione'}), 400

    aggiunti = 0
    for raw_cf in cfs:
        cf = normalizza_cf(raw_cf)
        p = db.session.get(Persona, cf)
        if p and p not in g.ragazzi:
            g.ragazzi.append(p)
            aggiunti += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{aggiunti} partecipanti assegnati con successo a "{g.nome}"',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@oratorio_bp.route('/gruppi/<int:id>/ragazzi/<cf>', methods=['DELETE'])
def remove_ragazzo_gruppo_oratorio(id, cf):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf_norm = normalizza_cf(cf)
    persona = db.session.get(Persona, cf_norm)
    if persona and persona in g.ragazzi:
        g.ragazzi.remove(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Partecipante rimosso/a dal gruppo "{g.nome}"',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@oratorio_bp.route('/gruppi/<int:id>/allergie', methods=['GET'])
def get_allergie_gruppo_oratorio(id):
    g = db.session.get(GruppoOratorio, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    ragazzi_allergie = []
    con_allergie_count = 0

    for r in g.ragazzi:
        ha_info = bool(r.allergie or r.intolleranze_alimentari or r.note_generali)
        if ha_info:
            con_allergie_count += 1
        
        telefono_genitore = ''
        nominativo_genitore = ''
        nome_famiglia = ''
        if r.nucleo:
            nome_famiglia = r.nucleo.nome_famiglia or ''
            if r.nucleo.capofamiglia:
                telefono_genitore = r.nucleo.capofamiglia.telefono or ''
                nominativo_genitore = r.nucleo.capofamiglia.nominativo or ''
        if not telefono_genitore and r.telefono:
            telefono_genitore = r.telefono

        ragazzi_allergie.append({
            'codice_fiscale': r.codice_fiscale,
            'nominativo': r.nominativo,
            'eta': r.eta,
            'sesso': r.sesso or 'M',
            'telefono': telefono_genitore,
            'nome_famiglia': nome_famiglia,
            'famiglia_nome': nome_famiglia,
            'capofamiglia_nome': nominativo_genitore,
            'telefono_famiglia': telefono_genitore,
            'cellulare': r.telefono or '',
            'indirizzo': r.indirizzo_residenza or '',
            'allergie': r.allergie or '',
            'intolleranze_alimentari': r.intolleranze_alimentari or '',
            'note_mediche': r.note_generali or '',
            'ha_segnalazione': ha_info,
            'ha_condizioni': ha_info
        })

    return jsonify({
        'gruppo': g.to_dict(include_ragazzi=False),
        'totale_ragazzi': len(g.ragazzi),
        'con_allergie_count': con_allergie_count,
        'ragazzi_con_segnalazioni': con_allergie_count,
        'segnalazioni': ragazzi_allergie,
        'ragazzi': ragazzi_allergie
    })

@oratorio_bp.route('/miei-figli', methods=['GET'])
def get_oratorio_miei_figli():
    """Restituisce i gruppi di oratorio (estivo e invernale) a cui sono iscritti i figli dell'utente loggato."""
    gruppi_aperti_tutti = [g.to_dict(include_ragazzi=False) for g in GruppoOratorio.query.filter_by(stato='pubblico').all()]

    if not current_user.is_authenticated:
        return jsonify({'ha_famiglia': False, 'figli': [], 'gruppi_disponibili': gruppi_aperti_tutti})

    persona_utente = current_user.persona
    if not persona_utente or not persona_utente.nucleo_id:
        # Se utente singolo senza famiglia, usa se stesso come componente
        if persona_utente:
            gruppi_assegnati = [g.to_dict(include_ragazzi=False) for g in persona_utente.gruppi_oratorio]
            gruppi_disp = [g.to_dict(include_ragazzi=False) for g in GruppoOratorio.query.filter_by(stato='pubblico').all() if g not in persona_utente.gruppi_oratorio]
            return jsonify({
                'ha_famiglia': False,
                'gruppi_disponibili': gruppi_aperti_tutti,
                'figli': [{
                    'codice_fiscale': persona_utente.codice_fiscale,
                    'nominativo': persona_utente.nominativo,
                    'eta': persona_utente.eta,
                    'gruppi': gruppi_assegnati,
                    'gruppi_disponibili': gruppi_disp
                }]
            })
        return jsonify({'ha_famiglia': False, 'figli': [], 'gruppi_disponibili': gruppi_aperti_tutti})

    nucleo = persona_utente.nucleo
    figli = [m for m in nucleo.componenti if m.ruolo_famiglia in ['Figlio/a', 'Figlio', 'Figlia', 'Minore', 'Nipote']]
    if not figli:
        figli = nucleo.componenti

    risultati = []
    for f in figli:
        gruppi_assegnati = []
        for g in f.gruppi_oratorio:
            gruppi_assegnati.append(g.to_dict(include_ragazzi=False))

        # Gruppi pubblici aperti in cui può iscriversi
        gruppi_aperti_db = GruppoOratorio.query.filter_by(stato='pubblico').all()
        gruppi_disponibili = [g.to_dict(include_ragazzi=False) for g in gruppi_aperti_db if g not in f.gruppi_oratorio]

        risultati.append({
            'codice_fiscale': f.codice_fiscale,
            'nominativo': f.nominativo,
            'eta': f.eta,
            'gruppi': gruppi_assegnati,
            'gruppi_disponibili': gruppi_disponibili
        })

    return jsonify({
        'ha_famiglia': True,
        'nome_famiglia': nucleo.nome_famiglia,
        'gruppi_disponibili': gruppi_aperti_tutti,
        'figli': risultati
    })

@oratorio_bp.route('/iscrivi-figlio', methods=['POST'])
def iscrivi_figlio_oratorio():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Accesso non autorizzato'}), 401

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    gruppo_id = data.get('gruppo_id')

    if not cf or not gruppo_id:
        return jsonify({'error': 'Dati mancanti per l\'iscrizione'}), 400

    gruppo = db.session.get(GruppoOratorio, gruppo_id)
    if not gruppo:
        return jsonify({'error': 'Gruppo Oratorio non trovato'}), 404

    if gruppo.stato != 'pubblico':
        return jsonify({'error': 'Le iscrizioni a questo gruppo sono chiuse o in bozza'}), 403

    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': 'Persona non trovata'}), 404

    # Verifica appartenenza al nucleo familiare dell'utente
    if current_user.persona and current_user.persona.nucleo_id:
        if persona.nucleo_id != current_user.persona.nucleo_id:
            return jsonify({'error': 'Non puoi iscrivere persone che non appartengono alla tua famiglia'}), 403

    if persona not in gruppo.ragazzi:
        gruppo.ragazzi.append(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{persona.nominativo} è stato/a iscritto/a con successo al gruppo "{gruppo.nome}"!',
        'gruppo': gruppo.to_dict(include_ragazzi=False)
    })

# ================= CRUSCOTTO SANITARIO & ALLERGIE =================
@oratorio_bp.route('/allergie', methods=['GET'])
def get_quadro_allergie():
    attivita_id = request.args.get('attivita_id', type=int)

    query = db.session.query(Iscrizione).join(Persona, Iscrizione.codice_fiscale_partecipante == Persona.codice_fiscale)
    
    if attivita_id:
        query = query.filter(Iscrizione.attivita_id == attivita_id)
    else:
        query = query.join(Attivita, Iscrizione.attivita_id == Attivita.id).filter(
            Attivita.categoria.in_(['oratorio', 'campo_estivo', 'doposcuola'])
        )

    query = query.filter(
        (Persona.intolleranze_alimentari.isnot(None) & (Persona.intolleranze_alimentari != '')) |
        (Persona.allergie.isnot(None) & (Persona.allergie != ''))
    )

    iscrizioni = query.all()

    items = []
    conteggi = {
        'totale_segnalazioni': len(iscrizioni),
        'celiachia_glutine': 0,
        'lattosio': 0,
        'arachidi_frutta_secca': 0,
        'farmaci_salvavita': 0,
        'altre_allergie': 0
    }

    for isc in iscrizioni:
        p = isc.partecipante
        intoll_lower = (p.intolleranze_alimentari or '').lower()
        allerg_lower = (p.allergie or '').lower()
        combined = f"{intoll_lower} {allerg_lower}"

        tag = []
        if 'celia' in combined or 'glutin' in combined:
            conteggi['celiachia_glutine'] += 1
            tag.append('Celiachia (Senza Glutine)')
        if 'latt' in combined:
            conteggi['lattosio'] += 1
            tag.append('Intolleranza Lattosio')
        if 'arachid' in combined or 'frutta secca' in combined or 'noc' in combined:
            conteggi['arachidi_frutta_secca'] += 1
            tag.append('Frutta Secca / Arachidi')
        if 'farmac' in combined or 'antistamin' in combined or 'asma' in combined or 'salvavita' in combined:
            conteggi['farmaci_salvavita'] += 1
            tag.append('Attenzione Farmaci / Asma')
        if not tag:
            conteggi['altre_allergie'] += 1
            tag.append('Altra Esigenza')

        items.append({
            'codice_fiscale': p.codice_fiscale,
            'nominativo': p.nominativo,
            'eta': p.eta,
            'squadra': isc.squadra or 'Non assegnata',
            'attivita_titolo': isc.attivita.titolo if isc.attivita else '',
            'intolleranze_alimentari': p.intolleranze_alimentari or 'Nessuna',
            'allergie': p.allergie or 'Nessuna',
            'note_iscrizione': isc.note_iscrizione or '',
            'telefono_emergenza': p.telefono or (p.nucleo.capofamiglia.telefono if p.nucleo and p.nucleo.capofamiglia else ''),
            'tags': tag
        })

    return jsonify({
        'conteggi': conteggi,
        'segnalazioni': items
    })

@oratorio_bp.route('/presenze', methods=['GET'])
def get_presenze():
    attivita_id = request.args.get('attivita_id', type=int)
    data_str = request.args.get('data')

    if not attivita_id:
        att = Attivita.query.filter_by(categoria='oratorio', is_attiva=True).first()
        if not att:
            return jsonify({'presenze': [], 'partecipanti': []})
        attivita_id = att.id

    data_presenza = date.today()
    if data_str:
        try:
            data_presenza = datetime.strptime(data_str, '%Y-%m-%d').date()
        except Exception:
            pass

    attivita = db.session.get(Attivita, attivita_id)
    if not attivita:
        return jsonify({'error': 'Attività non trovata'}), 404

    iscritti = [i.to_dict() for i in attivita.iscrizioni if i.stato == 'confermata']
    presenze_db = Presenza.query.filter_by(attivita_id=attivita_id, data=data_presenza).all()
    presenze_map = {p.codice_fiscale_persona: p.presente for p in presenze_db}

    risultati = []
    for isc in iscritti:
        cf = isc['codice_fiscale_partecipante']
        risultati.append({
            'iscrizione_id': isc['id'],
            'codice_fiscale': cf,
            'nominativo': isc['partecipante_nome'],
            'squadra': isc['squadra'],
            'presente': presenze_map.get(cf, True),
            'telefono': isc['telefono_contatto'],
            'allergie': isc['allergie']
        })

    return jsonify({
        'attivita_id': attivita_id,
        'attivita_titolo': attivita.titolo,
        'data': data_presenza.isoformat(),
        'partecipanti': risultati
    })

@oratorio_bp.route('/presenze', methods=['POST'])
def save_presenze():
    data = request.get_json() or {}
    attivita_id = data.get('attivita_id')
    data_str = data.get('data')
    elenco = data.get('presenze', [])

    if not attivita_id:
        return jsonify({'error': 'Attività ID obbligatorio'}), 400

    data_presenza = date.today()
    if data_str:
        try:
            data_presenza = datetime.strptime(data_str, '%Y-%m-%d').date()
        except Exception:
            pass

    for item in elenco:
        cf = normalizza_cf(item.get('codice_fiscale', ''))
        presente = bool(item.get('presente', True))

        rec = Presenza.query.filter_by(
            attivita_id=attivita_id,
            codice_fiscale_persona=cf,
            data=data_presenza
        ).first()

        if rec:
            rec.presente = presente
        else:
            rec = Presenza(
                attivita_id=attivita_id,
                codice_fiscale_persona=cf,
                data=data_presenza,
                presente=presente
            )
            db.session.add(rec)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Appello presenze salvato con successo!'})
