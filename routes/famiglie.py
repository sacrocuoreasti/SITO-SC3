from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from models import db, NucleoFamiliare, Persona, Utente
from services.cf_validator import normalizza_cf, valida_cf, estrai_dati_cf
from datetime import datetime

famiglie_bp = Blueprint('famiglie_bp', __name__, url_prefix='/api/famiglie')

@famiglie_bp.route('/mia', methods=['GET'])
def get_mia_famiglia():
    """
    Restituisce il nucleo familiare e tutti i figli/membri dell'utente attualmente collegato.
    Se l'utente non ha ancora un nucleo, tenta di trovarlo via CF o ne crea uno associato.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Accesso richiesto'}), 401

    persona = current_user.persona
    cf_utente = current_user.codice_fiscale

    nucleo = None
    if persona and persona.nucleo:
        nucleo = persona.nucleo
    elif cf_utente:
        nucleo = NucleoFamiliare.query.filter_by(codice_fiscale_capofamiglia=cf_utente).first()

    if not nucleo and persona:
        # Crea automaticamente il nucleo familiare per l'utente loggato se non esiste
        nome_famiglia = f"Famiglia {persona.cognome}"
        nucleo = NucleoFamiliare(
            nome_famiglia=nome_famiglia,
            codice_fiscale_capofamiglia=persona.codice_fiscale,
            telefono_principale=persona.telefono,
            indirizzo=persona.indirizzo_residenza,
            citta=persona.comune_residenza or 'Asti'
        )
        db.session.add(nucleo)
        db.session.flush()
        persona.nucleo_id = nucleo.id
        persona.ruolo_famiglia = 'Capofamiglia'
        db.session.commit()

    if not nucleo:
        return jsonify({'nucleo': None, 'membri': []})

    return jsonify({
        'nucleo': nucleo.to_dict(include_members=True),
        'figli': [c.to_dict(include_family=False) for c in nucleo.componenti if c.ruolo_famiglia == 'Figlio/a' or c.codice_fiscale != nucleo.codice_fiscale_capofamiglia]
    })

@famiglie_bp.route('', methods=['GET'])
def get_famiglie():
    q = request.args.get('q', '').strip()
    query = NucleoFamiliare.query

    if q:
        search = f"%{q}%"
        query = query.filter(
            (NucleoFamiliare.nome_famiglia.ilike(search)) |
            (NucleoFamiliare.codice_fiscale_capofamiglia.ilike(search)) |
            (NucleoFamiliare.telefono_principale.ilike(search))
        )

    famiglie = query.order_by(NucleoFamiliare.nome_famiglia.asc()).all()
    return jsonify({
        'total': len(famiglie),
        'famiglie': [f.to_dict(include_members=True) for f in famiglie]
    })

@famiglie_bp.route('/<int:id>', methods=['GET'])
def get_famiglia(id):
    f = db.session.get(NucleoFamiliare, id)
    if not f:
        return jsonify({'error': 'Nucleo familiare non trovato'}), 404
    return jsonify({'famiglia': f.to_dict(include_members=True)})

@famiglie_bp.route('', methods=['POST'])
def create_famiglia():
    data = request.get_json() or {}
    nome = data.get('nome_famiglia', '').strip()
    cf_capo = normalizza_cf(data.get('codice_fiscale_capofamiglia', ''))

    if not nome:
        return jsonify({'error': 'Il nome della famiglia è obbligatorio'}), 400

    if cf_capo and not valida_cf(cf_capo):
        return jsonify({'error': 'Il Codice Fiscale del capofamiglia non è valido'}), 400

    nucleo = NucleoFamiliare(
        nome_famiglia=nome,
        codice_fiscale_capofamiglia=cf_capo or None,
        telefono_principale=data.get('telefono_principale', '').strip(),
        indirizzo=data.get('indirizzo', '').strip(),
        citta=data.get('citta', 'Asti').strip(),
        note=data.get('note', '').strip()
    )
    db.session.add(nucleo)
    db.session.flush()

    if cf_capo:
        capo = db.session.get(Persona, cf_capo)
        if capo:
            capo.nucleo_id = nucleo.id
            capo.ruolo_famiglia = 'Capofamiglia'

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Nucleo familiare creato con successo',
        'famiglia': nucleo.to_dict(include_members=True)
    }), 201

@famiglie_bp.route('/<int:id>/membri', methods=['POST'])
def add_membro(id):
    """
    Aggiunge un figlio o membro alla famiglia.
    Il genitore compila i dati: Codice Fiscale (chiave primaria), Nome, Cognome, Data Nascita, Allergie.
    Se la persona esiste già in anagrafica, viene associata alla famiglia; altrimenti viene creata.
    """
    nucleo = db.session.get(NucleoFamiliare, id)
    if not nucleo:
        return jsonify({'error': 'Nucleo familiare non trovato'}), 404

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    nome = data.get('nome', '').strip()
    cognome = data.get('cognome', '').strip() or (nucleo.capofamiglia.cognome if nucleo.capofamiglia else '')

    if not cf or not nome:
        return jsonify({'error': 'Codice Fiscale e Nome sono campi obbligatori'}), 400

    if not valida_cf(cf):
        return jsonify({'error': 'Codice Fiscale non valido secondo il calcolo formale'}), 400

    # Ricerca persona esistente o crea nuova
    persona = db.session.get(Persona, cf)
    dati_cf = estrai_dati_cf(cf)

    data_nascita = None
    if data.get('data_nascita'):
        try:
            data_nascita = datetime.strptime(data['data_nascita'], '%Y-%m-%d').date()
        except Exception:
            pass
    if not data_nascita and 'data_nascita' in dati_cf:
        data_nascita = dati_cf['data_nascita']

    sesso = data.get('sesso') or dati_cf.get('sesso', 'M')
    ruolo_famiglia = data.get('ruolo_famiglia', 'Figlio/a')

    if persona:
        # Aggiorna associazione
        persona.nucleo_id = nucleo.id
        persona.ruolo_famiglia = ruolo_famiglia
        if not persona.cognome and cognome: persona.cognome = cognome
        if not persona.nome and nome: persona.nome = nome
        if 'luogo_nascita' in data and data['luogo_nascita']: persona.luogo_nascita = data['luogo_nascita'].strip()
        if 'indirizzo_residenza' in data and data['indirizzo_residenza']: persona.indirizzo_residenza = data['indirizzo_residenza'].strip()
        if 'sesso' in data and data['sesso']: persona.sesso = data['sesso']
        if data_nascita: persona.data_nascita = data_nascita
        if 'intolleranze_alimentari' in data: persona.intolleranze_alimentari = data['intolleranze_alimentari'].strip()
        if 'allergie' in data: persona.allergie = data['allergie'].strip()
        if 'telefono' in data and data['telefono']: persona.telefono = data['telefono'].strip()
    else:
        persona = Persona(
            codice_fiscale=cf,
            nome=nome,
            cognome=cognome,
            sesso=sesso,
            data_nascita=data_nascita,
            luogo_nascita=data.get('luogo_nascita', '').strip(),
            indirizzo_residenza=data.get('indirizzo_residenza', nucleo.indirizzo or '').strip(),
            comune_residenza=data.get('comune_residenza', nucleo.citta or 'Asti').strip(),
            cap_residenza=data.get('cap_residenza', '14100').strip(),
            telefono=data.get('telefono', nucleo.telefono_principale or '').strip(),
            email=data.get('email', '').strip().lower(),
            intolleranze_alimentari=data.get('intolleranze_alimentari', '').strip(),
            allergie=data.get('allergie', '').strip(),
            nucleo_id=nucleo.id,
            ruolo_famiglia=ruolo_famiglia
        )
        db.session.add(persona)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{persona.nome} aggiunto/a con successo al nucleo familiare!',
        'persona': persona.to_dict()
    }), 201

@famiglie_bp.route('/<int:id>/membri/<cf>', methods=['DELETE'])
def remove_membro(id, cf):
    cf = normalizza_cf(cf)
    persona = db.session.get(Persona, cf)
    if not persona or persona.nucleo_id != id:
        return jsonify({'error': 'Membro non trovato nel nucleo familiare'}), 404

    persona.nucleo_id = None
    persona.ruolo_famiglia = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Membro rimosso dal nucleo familiare'})

@famiglie_bp.route('/offerte', methods=['GET'])
def get_offerte_famiglia():
    """Restituisce le coordinate per le offerte (Satispay, IBAN) e il quadro aggiornato delle offerte/quote versate dalla famiglia."""
    from models import ImpostazioniSito, Iscrizione
    impostazioni = ImpostazioniSito.query.first()
    info_pagamento = {
        'iban': (impostazioni.iban if impostazioni and impostazioni.iban else 'IT60X0542811101000000123456'),
        'satispay_url': (impostazioni.satispay_url if impostazioni and impostazioni.satispay_url else 'https://tag.satispay.com/sacrocuoreasti'),
        'intestatario': (impostazioni.intestatario_offerte if impostazioni and impostazioni.intestatario_offerte else 'Parrocchia Sacro Cuore di Gesù - Asti'),
        'causale_predefinita': (impostazioni.causale_predefinita_offerte if impostazioni and impostazioni.causale_predefinita_offerte else 'Offerta per le attività parrocchiali')
    }

    if not current_user.is_authenticated:
        return jsonify({
            'info_pagamento': info_pagamento,
            'totale_offerto': 0.0,
            'storico_versamenti': []
        })

    cfs_famiglia = set()
    if current_user.codice_fiscale:
        cfs_famiglia.add(current_user.codice_fiscale)
    if current_user.persona:
        cfs_famiglia.add(current_user.persona.codice_fiscale)
        if current_user.persona.nucleo:
            for m in current_user.persona.nucleo.componenti:
                cfs_famiglia.add(m.codice_fiscale)

    storico = []
    totale = 0.0

    if cfs_famiglia:
        # Quote iscrizioni pagate / offerte
        iscrizioni = Iscrizione.query.filter(Iscrizione.codice_fiscale_partecipante.in_(cfs_famiglia)).all()
        for isc in iscrizioni:
            versato = float(isc.quota_versata or 0.0)
            if versato > 0:
                totale += versato
                storico.append({
                    'data': isc.data_iscrizione.strftime('%d/%m/%Y') if isc.data_iscrizione else '',
                    'tipo': 'Quota Iscrizione Attività',
                    'descrizione': f"Attività: {isc.attivita.titolo if isc.attivita else 'Attività Parrocchiale'} ({isc.partecipante.nominativo if isc.partecipante else isc.codice_fiscale_partecipante})",
                    'importo': versato,
                    'metodo': isc.metodo_pagamento or 'Contanti / Satispay / Bonifico',
                    'stato': isc.stato_pagamento or 'saldato'
                })

    return jsonify({
        'info_pagamento': info_pagamento,
        'totale_offerto': round(totale, 2),
        'storico_versamenti': storico
    })
