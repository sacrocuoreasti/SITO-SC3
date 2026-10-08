from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Iscrizione, Persona, Presenza, GruppoCatechismo
from services.cf_validator import normalizza_cf
from datetime import date, datetime

catechismo_bp = Blueprint('catechismo_bp', __name__, url_prefix='/api/catechismo')

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
    gruppi = [g.to_dict(include_ragazzi=True) for g in gruppi_db]

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
        google_calendar_url=data.get('google_calendar_url', '').strip(),
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
    if 'google_calendar_url' in data: g.google_calendar_url = data['google_calendar_url'].strip()
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

    cf_ragazzi = [r.codice_fiscale for r in g.ragazzi]
    query = Presenza.query.filter_by(data=data_del)
    if g.attivita_id:
        query = query.filter_by(attivita_id=g.attivita_id)
    if cf_ragazzi:
        query = query.filter(Presenza.codice_fiscale_persona.in_(cf_ragazzi))

    deleted_count = query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Incontro del {data_str} cancellato con successo ({deleted_count} presenze rimosse)'
    })

@catechismo_bp.route('/presenze', methods=['POST'])
def save_presenze_catechismo():
    data = request.get_json() or {}
    gruppo_id = data.get('gruppo_id')
    attivita_id = data.get('attivita_id')
    data_str = data.get('data')
    elenco = data.get('presenze', [])
    concorre = data.get('concorre_percentuale', True)
    if concorre is None:
        concorre = True
    titolo_inc = data.get('titolo_incontro', '').strip()

    gruppo = None
    if gruppo_id:
        gruppo = db.session.get(GruppoCatechismo, int(gruppo_id))
        if gruppo and not attivita_id and gruppo.attivita_id:
            attivita_id = gruppo.attivita_id

    # Controllo isolamento catechista: può fare l'appello solo del suo gruppo
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        is_supervisor = any(r in ['admin', 'parroco', 'segreteria'] for r in roles)
        if not is_supervisor and ('catechista' in roles or current_user.ruolo == 'catechista'):
            user_cf = (current_user.codice_fiscale or '').strip().upper()
            cond = (GruppoCatechismo.catechista_utente_id == current_user.id)
            if user_cf:
                cond = cond | (GruppoCatechismo.catechista_cf == user_cf)
            gruppi_miei = GruppoCatechismo.query.filter(cond).all()
            miei_gruppi_ids = {g.id for g in gruppi_miei}
            attivita_autorizzate = {g.attivita_id for g in gruppi_miei if g.attivita_id}
            
            if gruppo_id and int(gruppo_id) not in miei_gruppi_ids:
                return jsonify({'error': 'Non sei autorizzato a registrare presenze per un gruppo diverso dal tuo'}), 403
            if attivita_id and attivita_autorizzate and attivita_id not in attivita_autorizzate:
                return jsonify({'error': 'Non sei autorizzato a registrare presenze per un gruppo diverso dal tuo'}), 403

    if not attivita_id:
        # Se l'attività non è ancora associata al gruppo, cerca o crea l'attività catechismo
        att_cat = Attivita.query.filter(
            (Attivita.categoria == 'catechismo') |
            (Attivita.titolo.ilike('%catechismo%'))
        ).first()
        if not att_cat:
            att_cat = Attivita(
                titolo=f"Incontri di Catechismo - {gruppo.nome if gruppo else 'Parrocchia'}",
                categoria='catechismo',
                anno_pastorale='2026/2027',
                is_attiva=True,
                is_pubblicato=True
            )
            db.session.add(att_cat)
            db.session.flush()
        attivita_id = att_cat.id
        if gruppo and not gruppo.attivita_id:
            gruppo.attivita_id = att_cat.id
        db.session.commit()

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
            rec.concorre_percentuale = bool(concorre)
            if titolo_inc:
                rec.titolo_incontro = titolo_inc
        else:
            rec = Presenza(
                attivita_id=attivita_id,
                codice_fiscale_persona=cf,
                data=data_presenza,
                presente=presente,
                concorre_percentuale=bool(concorre),
                titolo_incontro=titolo_inc or None
            )
            db.session.add(rec)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Presenze incontro catechismo salvate con successo'})

@catechismo_bp.route('/gruppi/<int:id>/storico', methods=['GET'])
def get_storico_gruppo(id):
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf_ragazzi = [r.codice_fiscale for r in g.ragazzi]
    query = Presenza.query
    if g.attivita_id:
        query = query.filter(Presenza.attivita_id == g.attivita_id)
    if cf_ragazzi:
        query = query.filter(Presenza.codice_fiscale_persona.in_(cf_ragazzi))

    presenze = query.order_by(Presenza.data.desc()).all()

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
    for r in g.ragazzi:
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

    ragazzi_allergie = []
    for r in g.ragazzi:
        note_med = getattr(r, 'note_generali', '') or ''
        ha_condizioni = bool(r.allergie or r.intolleranze_alimentari or note_med)
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
            'allergie': r.allergie or '',
            'intolleranze_alimentari': r.intolleranze_alimentari or '',
            'note_mediche': note_med,
            'ha_condizioni': ha_condizioni,
            'ha_segnalazione': ha_condizioni,
            'telefono_genitore': telefono_genitore,
            'nominativo_genitore': nominativo_genitore,
            'famiglia_nome': nome_famiglia,
            'capofamiglia_nome': nominativo_genitore,
            'telefono_famiglia': telefono_genitore,
            'cellulare': r.telefono or '',
            'indirizzo': r.indirizzo_residenza or ''
        })

    con_allergie = sum(1 for x in ragazzi_allergie if x['ha_condizioni'])
    return jsonify({
        'gruppo': g.to_dict(include_ragazzi=False),
        'totale_ragazzi': len(g.ragazzi),
        'con_allergie_count': con_allergie,
        'ragazzi_con_segnalazioni': con_allergie,
        'ragazzi': ragazzi_allergie,
        'segnalazioni': ragazzi_allergie
    })


@catechismo_bp.route('/gruppi/<int:id>/registro', methods=['GET'])
def get_registro_elettronico_gruppo(id):
    """
    Ritorna i dati per il registro elettronico del gruppo:
    elenco ragazzi, date degli incontri svolti, matrice delle presenze/assenze e statistiche.
    """
    g = db.session.get(GruppoCatechismo, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf_ragazzi = [r.codice_fiscale for r in g.ragazzi]
    query = Presenza.query
    if g.attivita_id:
        query = query.filter(Presenza.attivita_id == g.attivita_id)
    if cf_ragazzi:
        query = query.filter(Presenza.codice_fiscale_persona.in_(cf_ragazzi))

    presenze = query.order_by(Presenza.data.asc()).all()

    # Mappa presenze per CF e Data: matrice[cf][data_str] = True/False
    matrice = {cf: {} for cf in cf_ragazzi}
    date_info_map = {}

    for p in presenze:
        d_str = p.data.strftime('%Y-%m-%d')
        if d_str not in date_info_map:
            date_info_map[d_str] = {
                'data': d_str,
                'data_it': p.data.strftime('%d/%m/%Y'),
                'titolo_incontro': p.titolo_incontro or '',
                'concorre_percentuale': p.concorre_percentuale if p.concorre_percentuale is not None else True,
                'presenti_count': 0,
                'assenti_count': 0
            }
        if p.presente:
            date_info_map[d_str]['presenti_count'] += 1
        else:
            date_info_map[d_str]['assenti_count'] += 1
        if p.codice_fiscale_persona in matrice:
            matrice[p.codice_fiscale_persona][d_str] = p.presente

    sorted_dates = sorted(list(date_info_map.values()), key=lambda x: x['data'])

    # Statistiche per ciascun ragazzo (calcolando percentuale solo su incontri validi)
    studenti = []
    for r in g.ragazzi:
        cf = r.codice_fiscale
        p_rag = [p for p in presenze if p.codice_fiscale_persona == cf]
        tot_inc = len(p_rag)
        pres_inc = sum(1 for p in p_rag if p.presente)

        p_rag_validi = [p for p in p_rag if p.concorre_percentuale is not False]
        tot_inc_validi = len(p_rag_validi)
        pres_inc_validi = sum(1 for p in p_rag_validi if p.presente)

        perc = round((pres_inc_validi / tot_inc_validi) * 100) if tot_inc_validi > 0 else 0
        studenti.append({
            'codice_fiscale': cf,
            'nominativo': r.nominativo,
            'eta': r.eta,
            'presenze_map': matrice.get(cf, {}),
            'totale_incontri': tot_inc,
            'presenti': pres_inc,
            'assenti': tot_inc - pres_inc,
            'totale_incontri_validi': tot_inc_validi,
            'presenti_validi': pres_inc_validi,
            'percentuale': perc
        })

    return jsonify({
        'gruppo': g.to_dict(include_ragazzi=False),
        'date_incontri': sorted_dates,
        'studenti': studenti,
        'totale_date': len(sorted_dates),
        'data_odierna': date.today().strftime('%Y-%m-%d')
    })


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

            query_p = Presenza.query.filter_by(codice_fiscale_persona=cf)
            if gruppo_assegnato.attivita_id:
                query_p = query_p.filter_by(attivita_id=gruppo_assegnato.attivita_id)
            presenze = query_p.order_by(Presenza.data.desc()).all()

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
