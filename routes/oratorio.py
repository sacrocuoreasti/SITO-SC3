from flask import Blueprint, request, jsonify
from models import db, Attivita, Iscrizione, Persona, Presenza
from services.cf_validator import normalizza_cf
from datetime import date, datetime

oratorio_bp = Blueprint('oratorio_bp', __name__, url_prefix='/api/oratorio')

@oratorio_bp.route('/allergie', methods=['GET'])
def get_quadro_allergie():
    """
    Cruscotto sanitario e alimentare essenziale per gli animatori e i cuochi della parrocchia.
    Mostra tutti i partecipanti iscritti a Estate Ragazzi o attività con allergie,
    intolleranze o diete speciali, raggruppati per tipologia.
    """
    attivita_id = request.args.get('attivita_id', type=int)

    query = db.session.query(Iscrizione).join(Persona, Iscrizione.codice_fiscale_partecipante == Persona.codice_fiscale)
    
    if attivita_id:
        query = query.filter(Iscrizione.attivita_id == attivita_id)
    else:
        # Default: attività di tipo oratorio o campo estivo
        query = query.join(Attivita, Iscrizione.attivita_id == Attivita.id).filter(
            Attivita.categoria.in_(['oratorio', 'campo_estivo', 'doposcuola'])
        )

    # Filtra chi ha intolleranze alimentari o allergie compilate
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
        # Prendi la prima attività oratorio attiva
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

    # Lista iscritti all'attività
    iscritti = [i.to_dict() for i in attivita.iscrizioni if i.stato == 'confermata']

    # Presenze registrate per questa data
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
