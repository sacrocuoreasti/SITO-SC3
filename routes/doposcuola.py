from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Persona, Presenza, GruppoDoposcuola, Utente
from services.cf_validator import normalizza_cf
from datetime import date, datetime

doposcuola_bp = Blueprint('doposcuola_bp', __name__, url_prefix='/api/doposcuola')

@doposcuola_bp.route('/educatori', methods=['GET'])
def get_educatori():
    """Ritorna tutti gli utenti che possono svolgere il ruolo di educatore/volontario per il doposcuola."""
    utenti = Utente.query.filter(Utente.is_attivo == True).all()
    educatori = []
    for u in utenti:
        roles = u.get_all_roles()
        if any(r in ['educatore', 'oratorio', 'catechista', 'admin', 'parroco', 'segreteria'] for r in roles) or u.ruolo in ['educatore', 'oratorio', 'catechista']:
            educatori.append({
                'id': u.id,
                'email': u.email,
                'codice_fiscale': u.codice_fiscale or '',
                'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                'telefono': u.persona.telefono if u.persona else ''
            })
    return jsonify({
        'total': len(educatori),
        'educatori': educatori
    })

@doposcuola_bp.route('/gruppi', methods=['GET'])
def get_gruppi_doposcuola():
    """Ritorna i gruppi del doposcuola configurati."""
    gruppi_db = GruppoDoposcuola.query.order_by(GruppoDoposcuola.id.asc()).all()

    # Ritorna i gruppi con studenti inclusi
    gruppi = [g.to_dict(include_studenti=True) for g in gruppi_db]
    return jsonify({
        'gruppi': gruppi,
        'totale': len(gruppi)
    })

@doposcuola_bp.route('/gruppi', methods=['POST'])
def create_gruppo():
    """Crea un nuovo gruppo di doposcuola."""
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome del gruppo di doposcuola è obbligatorio'}), 400

    nuovo = GruppoDoposcuola(
        nome=nome,
        anno_scolastico=data.get('anno_scolastico', data.get('anno_pastorale', '2026/2027')).strip(),
        fascia_eta=data.get('fascia_eta', '').strip(),
        educatore_nome=data.get('educatore_nome', '').strip(),
        educatore_cf=normalizza_cf(data.get('educatore_cf', '')) or None,
        educatore_utente_id=data.get('educatore_utente_id'),
        giorni_orari=data.get('giorni_orari', data.get('orario_incontri', '')).strip(),
        aula=data.get('aula', '').strip(),
        note=data.get('note', '').strip(),
        stato=data.get('stato', 'pubblico').strip(),
        attivita_id=data.get('attivita_id')
    )
    db.session.add(nuovo)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Gruppo di doposcuola "{nuovo.nome}" creato con successo',
        'gruppo': nuovo.to_dict(include_studenti=True)
    }), 201

@doposcuola_bp.route('/gruppi/<int:id>', methods=['PUT'])
def update_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo doposcuola non trovato'}), 404

    data = request.get_json() or {}
    if 'nome' in data: g.nome = data['nome'].strip()
    if 'anno_scolastico' in data: g.anno_scolastico = data['anno_scolastico'].strip()
    if 'anno_pastorale' in data: g.anno_scolastico = data['anno_pastorale'].strip()
    if 'fascia_eta' in data: g.fascia_eta = data['fascia_eta'].strip()
    if 'educatore_nome' in data: g.educatore_nome = data['educatore_nome'].strip()
    if 'educatore_cf' in data: g.educatore_cf = normalizza_cf(data['educatore_cf']) or None
    if 'educatore_utente_id' in data: g.educatore_utente_id = data['educatore_utente_id']
    if 'giorni_orari' in data: g.giorni_orari = data['giorni_orari'].strip()
    if 'orario_incontri' in data: g.giorni_orari = data['orario_incontri'].strip()
    if 'aula' in data: g.aula = data['aula'].strip()
    if 'note' in data: g.note = data['note'].strip()
    if 'stato' in data: g.stato = data['stato'].strip()
    if 'attivita_id' in data: g.attivita_id = data['attivita_id']

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Gruppo doposcuola aggiornato con successo',
        'gruppo': g.to_dict(include_studenti=True)
    })

@doposcuola_bp.route('/gruppi/<int:id>', methods=['DELETE'])
def delete_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    g.studenti = []
    db.session.delete(g)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Gruppo doposcuola eliminato con successo'})

@doposcuola_bp.route('/gruppi/<int:id>/studenti', methods=['POST'])
def add_studente_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': f'Persona con CF {cf} non trovata'}), 404

    if persona not in g.studenti:
        g.studenti.append(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{persona.nominativo} iscritto/a al doposcuola "{g.nome}"',
        'gruppo': g.to_dict(include_studenti=True)
    })

@doposcuola_bp.route('/gruppi/<int:id>/studenti/<cf>', methods=['DELETE'])
def remove_studente_gruppo(id, cf):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf = normalizza_cf(cf)
    persona = db.session.get(Persona, cf)
    if persona and persona in g.studenti:
        g.studenti.remove(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Rimosso dal doposcuola "{g.nome}"',
        'gruppo': g.to_dict(include_studenti=True)
    })

@doposcuola_bp.route('/presenze', methods=['POST'])
def save_presenze_doposcuola():
    """Registra l'appello delle presenze/assenze per il gruppo di doposcuola."""
    data = request.get_json() or {}
    gruppo_id = data.get('gruppo_id')
    attivita_id = data.get('attivita_id')
    data_str = data.get('data')
    elenco = data.get('presenze', [])

    gruppo = None
    if gruppo_id:
        gruppo = db.session.get(GruppoDoposcuola, int(gruppo_id))
        if gruppo and not attivita_id and gruppo.attivita_id:
            attivita_id = gruppo.attivita_id

    if not attivita_id:
        att_dop = Attivita.query.filter(
            (Attivita.categoria == 'doposcuola') |
            (Attivita.titolo.ilike('%doposcuola%'))
        ).first()
        if not att_dop:
            att_dop = Attivita(
                titolo=f"Doposcuola e Studio - {gruppo.nome if gruppo else 'Parrocchia'}",
                categoria='doposcuola',
                anno_pastorale='2025/2026',
                is_attiva=True,
                is_pubblicato=False
            )
            db.session.add(att_dop)
            db.session.flush()
        attivita_id = att_dop.id
        if gruppo and not gruppo.attivita_id:
            gruppo.attivita_id = att_dop.id
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
        else:
            rec = Presenza(
                attivita_id=attivita_id,
                codice_fiscale_persona=cf,
                data=data_presenza,
                presente=presente
            )
            db.session.add(rec)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Presenze doposcuola salvate con successo'})

@doposcuola_bp.route('/gruppi/<int:id>/registro', methods=['GET'])
def get_registro_elettronico_gruppo(id):
    """
    Ritorna i dati per il registro elettronico del doposcuola:
    studenti, date degli incontri svolti, matrice presenze e statistiche.
    """
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo doposcuola non trovato'}), 404

    cf_studenti = [s.codice_fiscale for s in g.studenti]
    query = Presenza.query
    if g.attivita_id:
        query = query.filter(Presenza.attivita_id == g.attivita_id)
    if cf_studenti:
        query = query.filter(Presenza.codice_fiscale_persona.in_(cf_studenti))

    presenze = query.order_by(Presenza.data.asc()).all()

    # Mappa presenze per CF e Data
    matrice = {cf: {} for cf in cf_studenti}
    date_info_map = {}

    for p in presenze:
        d_str = p.data.strftime('%Y-%m-%d')
        if d_str not in date_info_map:
            date_info_map[d_str] = {
                'data': d_str,
                'data_it': p.data.strftime('%d/%m/%Y'),
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

    studenti_data = []
    for s in g.studenti:
        cf = s.codice_fiscale
        p_rag = [p for p in presenze if p.codice_fiscale_persona == cf]
        tot_inc = len(p_rag)
        pres_inc = sum(1 for p in p_rag if p.presente)
        perc = round((pres_inc / tot_inc) * 100) if tot_inc > 0 else 0
        studenti_data.append({
            'codice_fiscale': cf,
            'nominativo': s.nominativo,
            'eta': s.eta,
            'presenze_map': matrice.get(cf, {}),
            'totale_incontri': tot_inc,
            'presenti': pres_inc,
            'assenti': tot_inc - pres_inc,
            'percentuale': perc
        })

    return jsonify({
        'gruppo': g.to_dict(include_studenti=False),
        'date_incontri': sorted_dates,
        'studenti': studenti_data,
        'totale_date': len(sorted_dates),
        'data_odierna': date.today().strftime('%Y-%m-%d')
    })

@doposcuola_bp.route('/gruppi/<int:id>/storico', methods=['GET'])
def get_storico_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    cf_studenti = [s.codice_fiscale for s in g.studenti]
    query = Presenza.query
    if g.attivita_id:
        query = query.filter(Presenza.attivita_id == g.attivita_id)
    if cf_studenti:
        query = query.filter(Presenza.codice_fiscale_persona.in_(cf_studenti))

    presenze = query.order_by(Presenza.data.desc()).all()

    date_map = {}
    for p in presenze:
        d_str = p.data.strftime('%Y-%m-%d')
        if d_str not in date_map:
            date_map[d_str] = {
                'data': d_str,
                'data_it': p.data.strftime('%d/%m/%Y'),
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

    stats_studenti = []
    tot_date = len(date_map)
    for s in g.studenti:
        p_rag = [p for p in presenze if p.codice_fiscale_persona == s.codice_fiscale]
        tot_inc = len(p_rag)
        pres_inc = sum(1 for p in p_rag if p.presente)
        perc = round((pres_inc / tot_inc) * 100) if tot_inc > 0 else 0
        stats_studenti.append({
            'cf': s.codice_fiscale,
            'codice_fiscale': s.codice_fiscale,
            'nominativo': s.nominativo,
            'eta': s.eta,
            'totale_incontri': tot_inc,
            'presenti': pres_inc,
            'assenti': tot_inc - pres_inc,
            'presente_incontri': pres_inc,
            'assente_incontri': tot_inc - pres_inc,
            'percentuale': perc,
            'percentuale_presenza': perc
        })

    return jsonify({
        'gruppo': g.to_dict(include_studenti=False),
        'totale_incontri': tot_date,
        'totale_incontri_svolti': tot_date,
        'incontri': list(date_map.values()),
        'statistiche_ragazzi': stats_studenti
    })

@doposcuola_bp.route('/gruppi/<int:id>/allergie', methods=['GET'])
def get_allergie_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    ragazzi_allergie = []
    for s in g.studenti:
        ha_condizioni = bool(s.allergie or s.intolleranze_alimentari or s.note_mediche)
        telefono_genitore = ''
        nominativo_genitore = ''
        if s.nucleo and s.nucleo.capofamiglia:
            telefono_genitore = s.nucleo.capofamiglia.telefono or ''
            nominativo_genitore = s.nucleo.capofamiglia.nominativo or ''
        elif s.telefono:
            telefono_genitore = s.telefono

        ragazzi_allergie.append({
            'codice_fiscale': s.codice_fiscale,
            'nominativo': s.nominativo,
            'eta': s.eta,
            'allergie': s.allergie or '',
            'intolleranze_alimentari': s.intolleranze_alimentari or '',
            'note_mediche': s.note_mediche or '',
            'ha_condizioni': ha_condizioni,
            'telefono_genitore': telefono_genitore,
            'nominativo_genitore': nominativo_genitore
        })

    return jsonify({
        'gruppo': g.to_dict(include_studenti=False),
        'totale_studenti': len(g.studenti),
        'con_allergie_count': sum(1 for x in ragazzi_allergie if x['ha_condizioni']),
        'ragazzi': ragazzi_allergie
    })


@doposcuola_bp.route('/gruppi/<int:id>/studenti/batch', methods=['POST'])
def add_studenti_batch(id):
    """Assegnazione di massa di più persone ad un gruppo di doposcuola."""
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo doposcuola non trovato'}), 404

    data = request.get_json() or {}
    cfs = data.get('codici_fiscali', [])
    if not isinstance(cfs, list) or not cfs:
        return jsonify({'error': 'Nessun codice fiscale fornito'}), 400

    current_cfs = {s.codice_fiscale for s in g.studenti}
    added_count = 0
    for cf_raw in cfs:
        cf = normalizza_cf(cf_raw)
        if cf and cf not in current_cfs:
            p = db.session.get(Persona, cf)
            if p:
                g.studenti.append(p)
                current_cfs.add(cf)
                added_count += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'{added_count} studenti assegnati al doposcuola "{g.nome}" con successo',
        'count': added_count,
        'gruppo': g.to_dict(include_studenti=True)
    })


@doposcuola_bp.route('/miei-figli', methods=['GET'])
def get_miei_figli_doposcuola():
    """
    Ritorna SOLO i figli/minori della famiglia dell'utente autenticato per il doposcuola:
    - Informazioni gruppo, orari ed educatore di riferimento
    - Registro presenze e storico incontri del singolo figlio
    - Possibilità di iscrizione se non ancora assegnato
    Non mostra mai gli altri studenti del doposcuola.
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

    # Trova tutti i gruppi di doposcuola esistenti per controllare assegnazioni
    tutti_gruppi = GruppoDoposcuola.query.order_by(GruppoDoposcuola.nome.asc()).all()

    risultato_figli = []
    for f in figli_list:
        cf = f.codice_fiscale
        gruppo_assegnato = None
        for g in tutti_gruppi:
            if any(s.codice_fiscale == cf for s in g.studenti):
                gruppo_assegnato = g
                break

        info_gruppo = None
        statistiche = {'totale_incontri': 0, 'presenti': 0, 'assenti': 0, 'percentuale': 0}
        storico_presenze = []

        if gruppo_assegnato:
            info_gruppo = {
                'id': gruppo_assegnato.id,
                'nome': gruppo_assegnato.nome,
                'anno_scolastico': gruppo_assegnato.anno_scolastico,
                'fascia_eta': gruppo_assegnato.fascia_eta or '',
                'educatore_nome': gruppo_assegnato.educatore_nome or 'Da assegnare',
                'giorni_orari': gruppo_assegnato.giorni_orari or '',
                'aula': gruppo_assegnato.aula or '',
                'note': gruppo_assegnato.note or ''
            }

            query_p = Presenza.query.filter_by(codice_fiscale_persona=cf)
            if gruppo_assegnato.attivita_id:
                query_p = query_p.filter_by(attivita_id=gruppo_assegnato.attivita_id)
            presenze = query_p.order_by(Presenza.data.desc()).all()

            tot = len(presenze)
            pres = sum(1 for p in presenze if p.presente)
            perc = round((pres / tot) * 100) if tot > 0 else 0
            statistiche = {
                'totale_incontri': tot,
                'presenti': pres,
                'assenti': tot - pres,
                'percentuale': perc
            }
            storico_presenze = [
                {
                    'data': p.data.strftime('%Y-%m-%d'),
                    'data_it': p.data.strftime('%d/%m/%Y'),
                    'presente': p.presente,
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

    tutti_gruppi = GruppoDoposcuola.query.filter(GruppoDoposcuola.stato == 'pubblico').order_by(GruppoDoposcuola.nome.asc()).all()
    gruppi_disp = [
        {
            'id': g.id,
            'nome': g.nome,
            'anno_scolastico': g.anno_scolastico,
            'fascia_eta': g.fascia_eta or '',
            'giorni_orari': g.giorni_orari or '',
            'aula': g.aula or '',
            'educatore_nome': g.educatore_nome or 'Da assegnare',
            'stato': g.stato or 'pubblico'
        } for g in tutti_gruppi
    ]

    return jsonify({
        'ha_famiglia': True,
        'ha_figli': len(figli_list) > 0,
        'figli': risultato_figli,
        'gruppi_disponibili': gruppi_disp
    })


@doposcuola_bp.route('/iscrivi-figlio', methods=['POST'])
def iscrivi_figlio_doposcuola():
    """Permette al genitore di iscrivere il proprio figlio ad un gruppo di doposcuola."""
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

    studente = db.session.get(Persona, cf)
    gruppo = db.session.get(GruppoDoposcuola, gruppo_id)
    if not studente or not gruppo:
        return jsonify({'error': 'Studente o gruppo doposcuola non trovato'}), 404

    if gruppo.stato == 'chiuso':
        return jsonify({'error': 'Le iscrizioni a questo gruppo di doposcuola sono chiuse.'}), 400
    if gruppo.stato == 'bozza':
        return jsonify({'error': 'Questo gruppo di doposcuola è in bozza e non è disponibile per le iscrizioni.'}), 400

    if studente not in gruppo.studenti:
        gruppo.studenti.append(studente)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{studente.nominativo} è stato iscritto al gruppo di doposcuola "{gruppo.nome}" con successo!'
    })
