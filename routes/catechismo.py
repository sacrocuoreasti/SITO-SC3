from services.group_attendance import can_record, group_records, save_group_records, registry_data
from werkzeug.exceptions import Forbidden
from services.group_calendar import apply_calendar
from services.group_age_service import apply_age_range, register_age_guard
from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Iscrizione, Persona, Presenza, GruppoCatechismo
from services.cf_validator import normalizza_cf
from datetime import date, datetime

catechismo_bp = Blueprint('catechismo_bp', __name__, url_prefix='/api/catechismo')
register_age_guard(catechismo_bp, GruppoCatechismo, 'ragazzi')


@catechismo_bp.route('/catechisti', methods=['GET'])
def get_catechisti():
    """Ritorna tutti gli utenti o persone registrate che hanno il ruolo/privilegio di catechista."""
    from models import Utente
    utenti = Utente.query.filter(Utente.is_attivo == True).all()
    catechisti = []
    for u in utenti:
        roles = u.get_all_roles()
        if 'catechista' in roles or u.ruolo == 'catechista':
            catechisti.append({
                'id': u.id,
                'email': u.email,
                'codice_fiscale': u.codice_fiscale or '',
                'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                'telefono': u.persona.telefono if u.persona else ''
            })
    return jsonify({
        'total': len(catechisti),
        'catechisti': catechisti
    })

@catechismo_bp.route('/gruppi', methods=['GET'])
def get_gruppi_catechismo():
    """
    Ritorna i gruppi di catechismo configurati.
    Regola di accesso: un catechista assegnato ad un gruppo può vedere i dati
    e fare l'appello SOLO del suo gruppo. I supervisori (admin, parroco, segreteria)
    vedono tutti i gruppi.
    """
    gruppi_query = GruppoCatechismo.query.order_by(GruppoCatechismo.id.asc())
    gruppi_db = gruppi_query.all()

    is_catechista_only = False
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_supervisor = any(r in ['admin', 'parroco', 'segreteria'] for r in roles)
        if not is_supervisor and ('catechista' in roles or current_user.ruolo == 'catechista'):
            is_catechista_only = True
            user_cf = (current_user.codice_fiscale or '').upper()
            user_id = current_user.id
            user_nom = (current_user.persona.nominativo if current_user.persona else current_user.email.split('@')[0]).lower()
            user_email = current_user.email.lower()

            filtered = []
            for g in gruppi_db:
                match = False
                if hasattr(g, 'catechisti') and any(u.id == user_id for u in g.catechisti):
                    match = True
                elif g.catechista_utente_id and g.catechista_utente_id == user_id:
                    match = True
                elif user_cf and g.catechista_cf and g.catechista_cf.upper() == user_cf:
                    match = True
                elif g.catechista_nome:
                    gn = g.catechista_nome.lower()
                    if user_nom in gn or gn in user_nom or user_email in gn:
                        match = True
                if match:
                    filtered.append(g)
            gruppi_db = filtered

    # Ritorna i gruppi specifici configurati
    gruppi = [g.to_dict(include_ragazzi=bool(can_record('catechismo',g))) for g in gruppi_db]

    # Attività associate ai gruppi visibili
    attivita_ids = {g['attivita_id'] for g in gruppi if g.get('attivita_id')}
    if is_catechista_only:
        attivita_catechismo = Attivita.query.filter(Attivita.id.in_(attivita_ids)).all() if attivita_ids else []
    else:
        attivita_catechismo = Attivita.query.filter_by(categoria='catechismo').all()

    attivita_list = [a.to_dict() for a in attivita_catechismo]

    return jsonify({
        'gruppi': gruppi,
        'attivita_catechismo': attivita_list,
        'is_catechista_only': is_catechista_only
    })

@catechismo_bp.route('/gruppi', methods=['POST'])
def create_gruppo():
    """Permette alla segreteria o al parroco di creare molteplici gruppi del catechismo."""
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome del gruppo di catechismo è obbligatorio'}), 400

    nuovo = GruppoCatechismo(
        nome=nome,
        anno_pastorale=data.get('anno_pastorale', '2026/2027').strip(),
        anno_catechismo=data.get('anno_catechismo', '').strip(),
        catechista_nome=data.get('catechista_nome', '').strip(),
        catechista_cf=normalizza_cf(data.get('catechista_cf', '')) or None,
        catechista_utente_id=data.get('catechista_utente_id'),
        orario_incontri=data.get('orario_incontri', '').strip(),
        aula=data.get('aula', '').strip(),
        note=data.get('note', '').strip(),
        stato=data.get('stato', 'pubblico').strip(),
        attivita_id=data.get('attivita_id')
    )

    catechisti_ids = data.get('catechisti_ids') or []
    if catechisti_ids:
        from models import Utente
        cat_users = Utente.query.filter(Utente.id.in_(catechisti_ids)).all()
        nuovo.catechisti = cat_users
        nomi = [u.persona.nominativo if u.persona else u.email.split('@')[0] for u in cat_users]
        if nomi:
            nuovo.catechista_nome = ", ".join(nomi)

    apply_calendar(nuovo, data)
    apply_age_range(nuovo, data)
    db.session.add(nuovo)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Gruppo di catechismo "{nuovo.nome}" creato con successo',
        'gruppo': nuovo.to_dict(include_ragazzi=True)
    }), 201

@catechismo_bp.route('/gruppi/<int:id>', methods=['PUT'])
def update_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    apply_calendar(g, data)
    apply_age_range(g, data)
    if 'nome' in data: g.nome = data['nome'].strip()
    if 'anno_pastorale' in data: g.anno_pastorale = data['anno_pastorale'].strip()
    if 'anno_catechismo' in data: g.anno_catechismo = data['anno_catechismo'].strip()
    if 'catechista_nome' in data: g.catechista_nome = data['catechista_nome'].strip()
    if 'catechista_cf' in data: g.catechista_cf = normalizza_cf(data['catechista_cf']) or None
    if 'catechista_utente_id' in data: g.catechista_utente_id = data['catechista_utente_id']
    if 'orario_incontri' in data: g.orario_incontri = data['orario_incontri'].strip()
    if 'aula' in data: g.aula = data['aula'].strip()
    if 'note' in data: g.note = data['note'].strip()
    if 'stato' in data: g.stato = data['stato'].strip()
    if 'attivita_id' in data: g.attivita_id = data['attivita_id']

    if 'catechisti_ids' in data:
        catechisti_ids = data.get('catechisti_ids') or []
        from models import Utente
        cat_users = Utente.query.filter(Utente.id.in_(catechisti_ids)).all() if catechisti_ids else []
        g.catechisti = cat_users
        nomi = [u.persona.nominativo if u.persona else u.email.split('@')[0] for u in cat_users]
        if nomi:
            g.catechista_nome = ", ".join(nomi)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Gruppo aggiornato con successo',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@catechismo_bp.route('/gruppi/<int:id>', methods=['DELETE'])
def delete_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    g.ragazzi = []
    db.session.delete(g)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Gruppo eliminato con successo'})

@catechismo_bp.route('/gruppi/<int:id>/ragazzi', methods=['POST'])
def add_ragazzo_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': f'Persona con CF {cf} non trovata'}), 404

    if persona not in g.ragazzi:
        g.ragazzi.append(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{persona.nominativo} aggiunto/a al gruppo "{g.nome}"',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@catechismo_bp.route('/gruppi/<int:id>/ragazzi/<cf>', methods=['DELETE'])
def remove_ragazzo_gruppo(id, cf):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf = normalizza_cf(cf)
    persona = db.session.get(Persona, cf)
    if persona and persona in g.ragazzi:
        g.ragazzi.remove(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Rimosso dal gruppo "{g.nome}"',
        'gruppo': g.to_dict(include_ragazzi=True)
    })

@catechismo_bp.route('/gruppi/<int:id>/incontri/<data_str>', methods=['DELETE'])
def delete_incontro_catechismo(id, data_str):
    """Permette di cancellare un incontro di catechismo dal registro presenze."""
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_supervisor = any(r in ['admin', 'parroco', 'segreteria'] for r in roles)
        if not is_supervisor:
            return jsonify({'error': 'Solo la segreteria o l\'amministratore possono cancellare incontri'}), 403

    try:
        data_del = datetime.strptime(data_str, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'error': 'Formato data non valido (richiesto YYYY-MM-DD)'}), 400

    records=[record for record in group_records('catechismo',g) if record.data==data_del]
    deleted_count=len(records)
    for record in records: db.session.delete(record)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Incontro del {data_str} cancellato con successo ({deleted_count} presenze rimosse)'
    })

@catechismo_bp.route('/presenze', methods=['POST'])
def save_presenze_catechismo():
    data=request.get_json() or {}
    group=db.session.get(GruppoCatechismo,data.get('gruppo_id'))
    if not group: return jsonify(error='Gruppo non trovato'),404
    save_group_records('catechismo',group,data)
    return jsonify(success=True,message='Presenze salvate: un appello per gruppo e giornata')


@catechismo_bp.route('/gruppi/<int:id>/storico', methods=['GET'])
def get_storico_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    if not can_record('catechismo',g): raise Forbidden('Storico non disponibile per questo profilo')
    presenze=list(reversed(group_records('catechismo',g)))

    # Raggruppa per data incontro
    date_map = {}
    for p in presenze:
        d_str = p.data.strftime('%Y-%m-%d')
        if d_str not in date_map:
            date_map[d_str] = {
                'data': d_str,
                'data_it': p.data.strftime('%d/%m/%Y'),
                'titolo_incontro': p.titolo_incontro or '',
                'concorre_percentuale': p.concorre_percentuale if p.concorre_percentuale is not None else True,
                'presenti': 0,
                'assenti': 0,
                'presenti_count': 0,
                'assenti_count': 0,
                'dettaglio': []
            }
        nom = p.persona.nominativo if p.persona else p.codice_fiscale_persona
        if p.presente:
            date_map[d_str]['presenti'] += 1
            date_map[d_str]['presenti_count'] += 1
        else:
            date_map[d_str]['assenti'] += 1
            date_map[d_str]['assenti_count'] += 1
        date_map[d_str]['dettaglio'].append({
            'cf': p.codice_fiscale_persona,
            'nominativo': nom,
            'presente': p.presente
        })

    # Statistiche di presenza per ciascun ragazzo del gruppo (escludendo incontri che non concorrono alla percentuale)
    stats_ragazzi = []
    tot_date = len(date_map)
    from services.catechismo_parents import members
    for r in members(g):
        p_rag = [p for p in presenze if p.codice_fiscale_persona == r.codice_fiscale]
        tot_inc = len(p_rag)
        pres_inc = sum(1 for p in p_rag if p.presente)

        # Incontri validi per la percentuale (concorre_percentuale != False)
        p_rag_validi = [p for p in p_rag if p.concorre_percentuale is not False]
        tot_inc_validi = len(p_rag_validi)
        pres_inc_validi = sum(1 for p in p_rag_validi if p.presente)

        perc = round((pres_inc_validi / tot_inc_validi) * 100) if tot_inc_validi > 0 else 0
        stats_ragazzi.append({
            'cf': r.codice_fiscale,
            'codice_fiscale': r.codice_fiscale,
            'nominativo': r.nominativo,
            'eta': r.eta,
            'totale_incontri': tot_inc,
            'presenti': pres_inc,
            'assenti': tot_inc - pres_inc,
            'presente_incontri': pres_inc,
            'assente_incontri': tot_inc - pres_inc,
            'totale_incontri_validi': tot_inc_validi,
            'presenti_validi': pres_inc_validi,
            'percentuale': perc,
            'percentuale_presenza': perc
        })

    return jsonify({
        'gruppo': g.to_dict(include_ragazzi=False),
        'totale_incontri': tot_date,
        'totale_incontri_svolti': tot_date,
        'incontri': list(date_map.values()),
        'statistiche_ragazzi': stats_ragazzi
    })

@catechismo_bp.route('/gruppi/<int:id>/allergie', methods=['GET'])
def get_allergie_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    if not can_record('catechismo',g): raise Forbidden('Elenco non disponibile per questo profilo')
    from services.catechismo_parents import members,parents_of
    people=[]
    for person in members(g):
        parents=parents_of(person)
        people.append({'codice_fiscale':person.codice_fiscale,'nome':person.nome,'cognome':person.cognome,
            'nominativo':person.nominativo,'eta':person.eta,'allergie':person.allergie or '',
            'intolleranze_alimentari':person.intolleranze_alimentari or '',
            'terapie_medicinali':person.terapie_medicinali or '', 'note_mediche':person.note_generali or '',
            'ha_segnalazione':bool(person.allergie or person.intolleranze_alimentari or person.terapie_medicinali or person.note_generali),
            'genitori':[{'nominativo':p.nominativo,'telefono':p.telefono or '','ruolo':p.ruolo_famiglia} for p in parents],
            'referente':({'nominativo':person.nucleo.capofamiglia.nominativo,'telefono':person.nucleo.capofamiglia.telefono or ''} if not parents and person.nucleo and person.nucleo.capofamiglia and person.nucleo.capofamiglia!=person else None)})
    return jsonify(gruppo=g.to_dict(include_ragazzi=False),ragazzi=people,totale_ragazzi=len(people))


@catechismo_bp.route('/gruppi/<int:id>/registro', methods=['GET'])
def get_registro_elettronico_gruppo(id):
    group=db.session.get(GruppoCatechismo,id)
    if not group: return jsonify(error='Gruppo non trovato'),404
    if not can_record('catechismo',group): raise Forbidden('Registro non disponibile per questo profilo')
    result=registry_data('catechismo',group,request.args.get('mese'),whole_year=request.args.get('periodo')=='anno')
    from services.catechismo_parents import is_parent_group,expected_members
    day=request.args.get('giorno')
    if is_parent_group(group) and day:
        from werkzeug.exceptions import BadRequest
        try:
            if date.fromisoformat(day).isoformat()!=day: raise ValueError()
        except ValueError: raise BadRequest('Data non valida')
        expected={p.codice_fiscale for p in expected_members(group,day)}
        expected.update(r.codice_fiscale_persona for r in group_records('catechismo',group) if r.data.isoformat()==day)
        result['studenti']=[p for p in result['studenti'] if p['codice_fiscale'] in expected]
    return jsonify(result)


@catechismo_bp.route('/gruppi/<int:id>/ragazzi/batch', methods=['POST'])
def add_ragazzi_batch(id):
    """Assegnazione di massa di più persone ad un gruppo di catechismo."""
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    cfs = data.get('codici_fiscali', [])
    if not isinstance(cfs, list) or not cfs:
        return jsonify({'error': 'Nessun codice fiscale fornito'}), 400

    current_cfs = {r.codice_fiscale for r in g.ragazzi}
    added_count = 0
    for cf_raw in cfs:
        cf = normalizza_cf(cf_raw)
        if cf and cf not in current_cfs:
            p = db.session.get(Persona, cf)
            if p:
                g.ragazzi.append(p)
                current_cfs.add(cf)
                added_count += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{added_count} fedeli assegnati al gruppo "{g.nome}" con successo',
        'count': added_count,
        'gruppo': g.to_dict(include_ragazzi=True)
    })


@catechismo_bp.route('/gruppi/<int:id>/assegnabili', methods=['GET'])
def assignable_people(id):
    from services.family_service import staff_user
    from services.enrollment_options import age_eligible
    from services.catechismo_parents import members,is_parent_group
    if not staff_user(): raise Forbidden('Assegnazione riservata alla segreteria')
    group=db.session.get(GruppoCatechismo,id)
    if not group: return jsonify(error='Gruppo non trovato'),404
    existing={p.codice_fiscale for p in members(group)}
    candidates=[] if is_parent_group(group) else [p.to_dict() for p in Persona.query.order_by(Persona.cognome,Persona.nome).all() if p.codice_fiscale not in existing and age_eligible(p,group)]
    return jsonify(persone=candidates,total=len(candidates))


@catechismo_bp.route('/miei-figli', methods=['GET'])
def get_miei_figli_catechismo():
    """
    Ritorna SOLO i figli/minori della famiglia dell'utente autenticato per il catechismo:
    - Informazioni gruppo e catechista di riferimento (con link google calendar)
    - Registro presenze e storico incontri del singolo figlio
    - Disponibilità per l'iscrizione se non ancora assegnato
    Non mostra mai gli altri partecipanti parrocchiali.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Accesso negato'}), 401

    persona = current_user.persona
    if not persona or not persona.nucleo:
        return jsonify({
            'ha_famiglia': False,
            'ha_figli': False,
            'figli': [],
            'gruppi_disponibili': []
        })

    nucleo = persona.nucleo
    componenti = nucleo.componenti
    figli_list = []
    for c in componenti:
        if c.codice_fiscale == persona.codice_fiscale:
            continue
        is_figlio = (c.ruolo_famiglia in ['Figlio/a', 'Figlio', 'Figlia']) or (c.eta is not None and c.eta < 18)
        if not is_figlio and c.ruolo_famiglia in ['Padre', 'Madre', 'Capofamiglia', 'Coniuge']:
            continue
        figli_list.append(c)

    if not figli_list:
        for c in componenti:
            if c.codice_fiscale != persona.codice_fiscale and (c.eta is not None and c.eta < 18):
                figli_list.append(c)

    risultato_figli = []
    for f in figli_list:
        cf = f.codice_fiscale
        gruppo_assegnato = None
        if f.gruppi_catechismo:
            gruppo_assegnato = f.gruppi_catechismo[-1]

        info_gruppo = None
        statistiche = {'totale_incontri': 0, 'presenti': 0, 'assenti': 0, 'percentuale': 0}
        storico_presenze = []

        if gruppo_assegnato:
            info_gruppo = {
                'id': gruppo_assegnato.id,
                'nome': gruppo_assegnato.nome,
                'anno_pastorale': gruppo_assegnato.anno_pastorale,
                'anno_catechismo': gruppo_assegnato.anno_catechismo or '',
                'catechista_nome': gruppo_assegnato.catechista_nome or 'Da assegnare',
                'google_calendar_url': gruppo_assegnato.google_calendar_url or '',
                'catechisti': [
                    {
                        'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                        'email': u.email,
                        'telefono': u.persona.telefono if u.persona else ''
                    } for u in gruppo_assegnato.catechisti
                ] if gruppo_assegnato.catechisti else [],
                'orario_incontri': gruppo_assegnato.orario_incontri or '',
                'aula': gruppo_assegnato.aula or '',
                'note': gruppo_assegnato.note or ''
            }

            presenze=sorted(group_records('catechismo',gruppo_assegnato,[f]),key=lambda row:row.data,reverse=True)

            tot = len(presenze)
            pres = sum(1 for p in presenze if p.presente)
            
            p_validi = [p for p in presenze if p.concorre_percentuale is not False]
            tot_val = len(p_validi)
            pres_val = sum(1 for p in p_validi if p.presente)
            perc = round((pres_val / tot_val) * 100) if tot_val > 0 else 0

            statistiche = {
                'totale_incontri': tot,
                'presenti': pres,
                'assenti': tot - pres,
                'totale_incontri_validi': tot_val,
                'presenti_validi': pres_val,
                'percentuale': perc
            }
            storico_presenze = [
                {
                    'data': p.data.strftime('%Y-%m-%d'),
                    'data_it': p.data.strftime('%d/%m/%Y'),
                    'presente': p.presente,
                    'concorre_percentuale': p.concorre_percentuale if p.concorre_percentuale is not None else True,
                    'titolo_incontro': p.titolo_incontro or '',
                    'note': p.note or ''
                } for p in presenze
            ]

        risultato_figli.append({
            'codice_fiscale': cf,
            'nominativo': f.nominativo,
            'nome': f.nome,
            'cognome': f.cognome,
            'eta': f.eta,
            'data_nascita_it': f.data_nascita.strftime('%d/%m/%Y') if f.data_nascita else '',
            'is_assegnato': gruppo_assegnato is not None,
            'gruppo': info_gruppo,
            'statistiche': statistiche,
            'storico_presenze': storico_presenze
        })

    tutti_gruppi = GruppoCatechismo.query.filter(GruppoCatechismo.stato == 'pubblico').order_by(GruppoCatechismo.nome.asc()).all()
    gruppi_disp = [
        {
            'id': g.id,
            'nome': g.nome,
            'anno_pastorale': g.anno_pastorale,
            'anno_catechismo': g.anno_catechismo or '',
            'orario_incontri': g.orario_incontri or '',
            'aula': g.aula or '',
            'catechista_nome': g.catechista_nome or 'Da assegnare',
            'google_calendar_url': g.google_calendar_url or '',
            'stato': g.stato or 'pubblico'
        } for g in tutti_gruppi
    ]

    return jsonify({
        'ha_famiglia': True,
        'ha_figli': len(figli_list) > 0,
        'figli': risultato_figli,
        'gruppi_disponibili': gruppi_disp
    })


@catechismo_bp.route('/iscrivi-figlio', methods=['POST'])
def iscrivi_figlio_catechismo():
    """Permette al genitore di iscrivere il proprio figlio ad un gruppo di catechismo."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Accesso negato'}), 401

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    gruppo_id = data.get('gruppo_id')

    if not cf or not gruppo_id:
        return jsonify({'error': 'Dati incompleti'}), 400

    persona = current_user.persona
    if not persona or not persona.nucleo:
        return jsonify({'error': 'Nessun nucleo familiare associato'}), 403

    cfs_famiglia = {c.codice_fiscale for c in persona.nucleo.componenti}
    if cf not in cfs_famiglia:
        return jsonify({'error': 'Non sei autorizzato ad iscrivere questa persona'}), 403

    ragazzo = db.session.get(Persona, cf)
    gruppo = db.session.get(GruppoCatechismo, gruppo_id)
    if not ragazzo or not gruppo:
        return jsonify({'error': 'Ragazzo o gruppo non trovato'}), 404

    if gruppo.stato == 'chiuso':
        return jsonify({'error': 'Le iscrizioni a questo gruppo di catechismo sono chiuse.'}), 400
    if gruppo.stato == 'bozza':
        return jsonify({'error': 'Questo gruppo è in bozza e non è disponibile per le iscrizioni.'}), 400

    if ragazzo not in gruppo.ragazzi:
        gruppo.ragazzi.append(ragazzo)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{ragazzo.nominativo} è stato iscritto al gruppo "{gruppo.nome}" con successo!'
    })
