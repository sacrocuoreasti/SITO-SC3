from services.profile_files import profile_payload, commit_profile
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from models import db, NucleoFamiliare, Persona, Utente, RichiestaNucleo
from services.family_service import can_manage_family, family_member, staff_user, FAMILY_ROLES, consent_record
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

    pending = RichiestaNucleo.query.filter_by(utente_id=current_user.id).filter(RichiestaNucleo.stato.in_(['in_attesa', 'rifiutata'])).order_by(RichiestaNucleo.id.desc()).first()
    if not nucleo and pending:
        return jsonify(nucleo=None, richiesta_in_attesa=pending.stato == 'in_attesa', richiesta_rifiutata=pending.stato == 'rifiutata', membri=[])

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
        # La responsabilità di capofamiglia è indipendente dal ruolo.
        db.session.commit()

    if not nucleo:
        return jsonify({'nucleo': None, 'membri': []})

    return jsonify({
        'nucleo': nucleo.to_dict(include_members=True),
        'puo_gestire': bool(can_manage_family(nucleo)),
        'richieste_ingresso': [{'id': r.id, 'nome': r.utente.persona.nominativo, 'email': r.utente.email} for r in RichiestaNucleo.query.filter_by(nucleo_id=nucleo.id, stato='in_attesa').all()] if can_manage_family(nucleo) else [],
        'figli': [c.to_dict(include_family=False) for c in nucleo.componenti if c.ruolo_famiglia == 'Figlio/a' or c.codice_fiscale != nucleo.codice_fiscale_capofamiglia]
    })

@famiglie_bp.route('', methods=['GET'])
def get_famiglie():
    q = request.args.get('q', '').strip()
    query = NucleoFamiliare.query
    if not staff_user():
        query = query.filter_by(id=current_user.persona.nucleo_id if current_user.persona else None)

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
    if not staff_user() and not family_member(f):
        return jsonify(error='Accesso al nucleo non autorizzato'), 403
    return jsonify({'famiglia': f.to_dict(include_members=True)})

@famiglie_bp.route('', methods=['POST'])
def create_famiglia():
    if not staff_user():
        return jsonify(error='Operazione riservata alla segreteria'), 403
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
            # Mantieni invariato il ruolo familiare esistente.

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Nucleo familiare creato con successo',
        'famiglia': nucleo.to_dict(include_members=True)
    }), 201

@famiglie_bp.route('/<int:id>/membri', methods=['POST'])
def add_membro(id):
    nucleo = db.session.get(NucleoFamiliare, id)
    if not nucleo:
        return jsonify(error='Nucleo familiare non trovato'), 404
    if not can_manage_family(nucleo):
        return jsonify(error='Solo il capofamiglia o la segreteria possono aggiungere membri'), 403
    data = profile_payload()
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    nome = data.get('nome', '').strip()
    cognome = data.get('cognome', '').strip() or (nucleo.capofamiglia.cognome if nucleo.capofamiglia else '')
    role = data.get('ruolo_famiglia', 'Figlio/a')
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if not cf or not nome or not cognome or not valida_cf(cf) or role not in FAMILY_ROLES:
        return jsonify(error='Verifica codice fiscale, nome, cognome e ruolo familiare'), 400
    existing = db.session.get(Persona, cf)
    if existing:
        return jsonify(error='Persona già censita: usa la modifica della scheda o un invito, senza sovrascrivere dati esistenti'), 409
    try:
        consents = consent_record(data, current_user.id)
    except ValueError as error:
        return jsonify(error=str(error)),400
    if email and '@' not in email:
        return jsonify(error='Email non valida'),400
    if password:
        if '@' not in email or len(password) < 8:
            return jsonify(error='Per attivare l’account servono email e password di almeno 8 caratteri'), 400
        if Utente.query.filter_by(email=email).first():
            return jsonify(error='Email già utilizzata da un account'), 409
    dati_cf = estrai_dati_cf(cf)
    born = dati_cf.get('data_nascita')
    if data.get('data_nascita'):
        try:
            born = datetime.strptime(data['data_nascita'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify(error='Data di nascita non valida'), 400
    capo = nucleo.capofamiglia
    persona = Persona(consensi_aggiunta=consents, civico_residenza=data.get('civico_residenza', '').strip() or (capo.civico_residenza if capo else None), codice_fiscale=cf, nome=nome, cognome=cognome, sesso=data.get('sesso') or dati_cf.get('sesso', 'M'),
                      data_nascita=born, luogo_nascita=data.get('luogo_nascita', '').strip(),
                      indirizzo_residenza=data.get('indirizzo_residenza', '').strip() or (capo.indirizzo_residenza if capo else None) or nucleo.indirizzo,
                      comune_residenza=data.get('comune_residenza', '').strip() or (capo.comune_residenza if capo else None) or nucleo.citta,
                      cap_residenza=data.get('cap_residenza', '').strip() or (capo.cap_residenza if capo else None) or '14100',
                      provincia_residenza=data.get('provincia_residenza', '').strip() or (capo.provincia_residenza if capo else None) or 'AT',
                      telefono=data.get('telefono', '').strip(), email=email,
                      intolleranze_alimentari=data.get('intolleranze_alimentari', '').strip(),
                      allergie=data.get('allergie', '').strip(), terapie_medicinali=data.get('terapie_medicinali', '').strip(),
                      nucleo_id=nucleo.id, ruolo_famiglia=role, note_generali=data.get('note_generali','').strip())
    db.session.add(persona)
    db.session.flush()
    if email and password:
        user = Utente(email=email, codice_fiscale=cf, ruolo='utente', privilegi_extra='["utente"]',
                      gestito_da_id=current_user.id, consensi_registrazione=consents, is_attivo=True)
        user.set_password(password)
        db.session.add(user)
    commit_profile(persona, data)
    return jsonify(success=True, message='Membro aggiunto al nucleo' + (' e account personale attivato' if password else ''), persona=persona.to_dict()), 201


@famiglie_bp.route('/<int:id>/membri/<cf>/account', methods=['PUT'])
def manage_member_account(id, cf):
    family = db.session.get(NucleoFamiliare, id)
    if not family or not can_manage_family(family):
        return jsonify(error='Gestione account riservata al capofamiglia o alla segreteria'), 403
    person = db.session.get(Persona, normalizza_cf(cf))
    if not person or person.nucleo_id != id:
        return jsonify(error='Membro non trovato'), 404
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    if '@' not in email or (password and len(password) < 8):
        return jsonify(error='Verifica email e password (almeno 8 caratteri)'), 400
    user = person.utente
    if user and set(user.get_all_roles()) & {'admin', 'segreteria', 'parroco'} and not staff_user():
        return jsonify(error='L’account del personale può essere gestito solo dalla segreteria'), 403
    if Utente.query.filter(Utente.email == email, Utente.id != (user.id if user else -1)).first():
        return jsonify(error='Email già utilizzata'), 409
    if not user:
        if not password:
            return jsonify(error='La password è obbligatoria per un nuovo account'), 400
        try:
            consent = consent_record(data, current_user.id)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        user = Utente(email=email, codice_fiscale=person.codice_fiscale, ruolo='utente', privilegi_extra='["utente"]',
                      consensi_registrazione=consent, gestito_da_id=current_user.id, is_attivo=True)
        db.session.add(user)
    user.email = person.email = email
    if password:
        user.set_password(password)
    db.session.commit()
    return jsonify(success=True, message='Account del membro aggiornato')


@famiglie_bp.route('/<int:id>/richieste/<int:request_id>', methods=['PUT'])
def review_family_request(id, request_id):
    family = db.session.get(NucleoFamiliare, id)
    if not family or not can_manage_family(family):
        return jsonify(error='Solo il capofamiglia può gestire gli inviti'), 403
    entry = db.session.get(RichiestaNucleo, request_id)
    if not entry or entry.nucleo_id != id or entry.stato != 'in_attesa':
        return jsonify(error='Richiesta non trovata o già gestita'), 404
    decision = (request.get_json() or {}).get('azione')
    if decision not in {'approva', 'rifiuta'}:
        return jsonify(error='Scegli approva o rifiuta'), 400
    if decision == 'approva':
        person = entry.utente.persona
        if not person or person.nucleo_id not in (None, id):
            return jsonify(error='La persona appartiene già a un altro nucleo'), 409
        person.nucleo_id = id
        entry.utente.gestito_da_id = current_user.id
        entry.stato = 'approvata'
    else:
        entry.stato = 'rifiutata'
    db.session.commit()
    return jsonify(success=True, message='Richiesta ' + entry.stato)


@famiglie_bp.route('/<int:id>/membri/<cf>', methods=['DELETE'])
def remove_membro(id, cf):
    family = db.session.get(NucleoFamiliare, id)
    if not family or not can_manage_family(family):
        return jsonify(error='Operazione riservata al capofamiglia'), 403
    persona = db.session.get(Persona, normalizza_cf(cf))
    if not persona or persona.nucleo_id != id:
        return jsonify(error='Membro non trovato nel nucleo familiare'), 404
    if family.codice_fiscale_capofamiglia == persona.codice_fiscale:
        return jsonify(error='Assegna prima un altro capofamiglia'), 400
    persona.nucleo_id = None
    persona.ruolo_famiglia = None
    if persona.utente:
        persona.utente.gestito_da_id = None
    db.session.commit()
    return jsonify(success=True, message='Membro scollegato dal nucleo; account e dati conservati')

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


@famiglie_bp.route('/opportunita', methods=['GET'])
@login_required
def get_enrollment_options():
    from services.enrollment_options import enrollment_options
    return jsonify(enrollment_options())


@famiglie_bp.route('/iscrizioni-gruppo', methods=['POST'])
@login_required
def enroll_family_group():
    from services.enrollment_options import GROUP_MODELS, group_candidates, age_eligible
    from services.cf_validator import normalizza_cf
    data = request.get_json() or {}
    category = data.get('categoria')
    if not isinstance(category,str) or category not in GROUP_MODELS:
        return jsonify(error='Categoria non valida'),400
    model, collection = GROUP_MODELS[category]
    try:
        group = db.session.get(model, int(data.get('gruppo_id')))
    except (ValueError, TypeError):
        return jsonify(error='Gruppo non valido'),400
    if not group or group.stato != 'pubblico':
        return jsonify(error='Gruppo non disponibile'),400
    supplied = data.get('partecipanti')
    if not isinstance(supplied,list) or not supplied or any(not isinstance(cf,str) for cf in supplied):
        return jsonify(error='Seleziona almeno un figlio'),400
    cfs = list(dict.fromkeys(normalizza_cf(cf) for cf in supplied))
    allowed = {p.codice_fiscale:p for p in group_candidates()}
    for cf in cfs:
        if cf not in allowed:
            return jsonify(error='Non sei autorizzato a iscrivere uno dei partecipanti'),403
        if not age_eligible(allowed[cf],group):
            return jsonify(error='Uno dei partecipanti non rientra nella fascia di età'),400
    members = getattr(group,collection)
    for cf in cfs:
        if allowed[cf] not in members:
            members.append(allowed[cf])
    db.session.commit()
    return jsonify(success=True,message='Iscrizione al gruppo completata')


@famiglie_bp.route('/calendari-gruppi', methods=['GET'])
@login_required
def get_family_group_calendars():
    from services.enrollment_options import manageable_people,person_groups
    from services.group_calendar import calendar_info
    from services.catechismo_parents import is_parent_group
    calendars={}
    for person in manageable_people():
        for category in ('oratorio','catechismo','doposcuola'):
            for group in person_groups(person,category):
                url=calendar_info(group)
                if url or is_parent_group(group):
                    key=category+':'+str(group.id)
                    calendars[key]={'id':key,'titolo':group.nome,'categoria':category,'calendar_embed_url':url,'google_calendar_url':url,'calendar_api_url':f'/api/calendari-gruppi/{category}/{group.id}'}
    return jsonify(calendari=list(calendars.values()))


@famiglie_bp.route('/registri-gruppi/<category>', methods=['GET'])
@login_required
def get_family_group_registers(category):
    from services.enrollment_options import GROUP_MODELS,manageable_people,person_groups
    from services.group_attendance import group_records
    if category not in GROUP_MODELS: return jsonify(error='Categoria non trovata'),404
    _,collection=GROUP_MODELS[category]
    groups={}
    for person in manageable_people():
        for group in person_groups(person,category):
            if group.id not in groups:
                groups[group.id]=group.to_dict(**({'include_studenti':False} if category=='doposcuola' else {'include_ragazzi':False}))
                groups[group.id]['componenti']=[]
            own=group_records(category,group,[person]);valid=[r for r in own if r.concorre_percentuale is not False]
            present=sum(r.presente for r in valid)
            groups[group.id]['componenti'].append({'nominativo':person.nominativo,'codice_fiscale':person.codice_fiscale,
                'presenti':sum(r.presente for r in own),'assenti':sum(not r.presente for r in own),'totale':len(own),
                'percentuale':round(100*present/len(valid)) if valid else None,
                'presenze':[r.to_dict() for r in sorted(own,key=lambda r:r.data,reverse=True)]})
    return jsonify(gruppi=list(groups.values()))
