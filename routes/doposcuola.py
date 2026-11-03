from services.group_attendance import can_record, group_records, save_group_records, registry_data
from werkzeug.exceptions import Forbidden
from services.group_calendar import apply_calendar
from services.group_age_service import apply_age_range, register_age_guard
from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Persona, Presenza, GruppoDoposcuola, Utente
from services.cf_validator import normalizza_cf
from datetime import date, datetime
from services.doposcuola_staff import apply_educators

doposcuola_bp = Blueprint('doposcuola_bp', __name__, url_prefix='/api/doposcuola')
register_age_guard(doposcuola_bp, GruppoDoposcuola, 'studenti')


@doposcuola_bp.route('/educatori', methods=['GET'])
def get_educatori():
    """Ritorna tutti gli utenti che possono svolgere il ruolo di educatore/volontario per il doposcuola."""
    utenti = Utente.query.filter(Utente.is_attivo == True).all()
    educatori = []
    from services.access_control import can
    for u in utenti:
        if can('doposcuola.staff',u):
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
    from services.access_control import can,is_admin
    if not is_admin() and can('doposcuola.staff') and not can('doposcuola.tutti'):
        gruppi_db=[group for group in gruppi_db if can_record('doposcuola',group)]

    # Ritorna i gruppi con studenti inclusi
    gruppi = [g.to_dict(include_studenti=bool(can_record('doposcuola',g))) for g in gruppi_db]
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
    apply_calendar(nuovo, data)
    apply_age_range(nuovo, data)
    apply_educators(nuovo,data)
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
    apply_calendar(g, data)
    apply_age_range(g, data)
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

    apply_educators(g,data)

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
    data=request.get_json() or {}
    group=db.session.get(GruppoDoposcuola,data.get('gruppo_id'))
    if not group: return jsonify(error='Gruppo non trovato'),404
    save_group_records('doposcuola',group,data)
    return jsonify(success=True,message='Presenze salvate: un appello per gruppo e giornata')


@doposcuola_bp.route('/gruppi/<int:id>/registro', methods=['GET'])
def get_registro_elettronico_gruppo(id):
    group=db.session.get(GruppoDoposcuola,id)
    if not group: return jsonify(error='Gruppo non trovato'),404
    if not can_record('doposcuola',group): raise Forbidden('Registro non disponibile per questo profilo')
    return jsonify(registry_data('doposcuola',group,request.args.get('mese')))


@doposcuola_bp.route('/gruppi/<int:id>/storico', methods=['GET'])
def get_storico_gruppo(id):
    g = db.session.get(GruppoDoposcuola, id)
    if not g:
        return jsonify({'error': 'Gruppo non trovato'}), 404

    if not can_record('doposcuola',g): raise Forbidden('Storico non disponibile per questo profilo')
    presenze=list(reversed(group_records('doposcuola',g)))

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
        note_med = getattr(s, 'note_generali', '') or ''
        ha_condizioni = bool(s.allergie or s.intolleranze_alimentari or note_med)
        telefono_genitore = ''
        nominativo_genitore = ''
        nome_famiglia = ''
        if s.nucleo:
            nome_famiglia = s.nucleo.nome_famiglia or ''
            if s.nucleo.capofamiglia:
                telefono_genitore = s.nucleo.capofamiglia.telefono or ''
                nominativo_genitore = s.nucleo.capofamiglia.nominativo or ''
        if not telefono_genitore and s.telefono:
            telefono_genitore = s.telefono

        ragazzi_allergie.append({
            'codice_fiscale': s.codice_fiscale,
            'nominativo': s.nominativo,
            'eta': s.eta,
            'sesso': s.sesso or 'M',
            'allergie': s.allergie or '',
            'intolleranze_alimentari': s.intolleranze_alimentari or '',
            'note_mediche': note_med,
            'ha_condizioni': ha_condizioni,
            'ha_segnalazione': ha_condizioni,
            'telefono_genitore': telefono_genitore,
            'nominativo_genitore': nominativo_genitore,
            'famiglia_nome': nome_famiglia,
            'capofamiglia_nome': nominativo_genitore,
            'telefono_famiglia': telefono_genitore,
            'cellulare': s.telefono or '',
            'indirizzo': s.indirizzo_residenza or ''
        })

    con_allergie = sum(1 for x in ragazzi_allergie if x['ha_condizioni'])
    return jsonify({
        'gruppo': g.to_dict(include_studenti=False),
        'totale_studenti': len(g.studenti),
        'con_allergie_count': con_allergie,
        'ragazzi_con_segnalazioni': con_allergie,
        'ragazzi': ragazzi_allergie,
        'segnalazioni': ragazzi_allergie
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

            presenze=sorted(group_records('doposcuola',gruppo_assegnato,[f]),key=lambda row:row.data,reverse=True)

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
