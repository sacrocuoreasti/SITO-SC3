from flask import Blueprint, request, jsonify, send_file
from models import db, Lista, Persona, Attivita, Iscrizione, GruppoCatechismo, GruppoDoposcuola, GruppoOratorio
from services.cf_validator import normalizza_cf
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

liste_bp = Blueprint('liste_bp', __name__, url_prefix='/api/liste')

@liste_bp.route('', methods=['GET'])
def get_liste():
    liste = Lista.query.order_by(Lista.id.desc()).all()
    return jsonify({
        'total': len(liste),
        'liste': [l.to_dict(include_members=False) for l in liste]
    })

@liste_bp.route('/<int:id>', methods=['GET'])
def get_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista / Badge non trovato'}), 404
    return jsonify({'lista': l.to_dict(include_members=True)})

@liste_bp.route('', methods=['POST'])
def create_lista():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome della lista / badge è obbligatorio'}), 400

    nuova = Lista(
        nome=nome,
        descrizione=data.get('descrizione', '').strip(),
        colore=data.get('colore', '#8B1E1E'),
        icona=data.get('icona', '🏅').strip() or '🏅',
        categoria=data.get('categoria', 'badge').strip() or 'badge',
        attivita_id=data.get('attivita_id')
    )
    db.session.add(nuova)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Badge / Lista "{nuova.nome}" creato con successo',
        'lista': nuova.to_dict(include_members=True)
    }), 201

@liste_bp.route('/<int:id>', methods=['PUT'])
def update_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista / Badge non trovato'}), 404

    data = request.get_json() or {}
    if 'nome' in data: l.nome = data['nome'].strip()
    if 'descrizione' in data: l.descrizione = data['descrizione'].strip()
    if 'colore' in data: l.colore = data['colore'].strip()
    if 'icona' in data: l.icona = data['icona'].strip() or '🏅'
    if 'categoria' in data: l.categoria = data['categoria'].strip() or 'badge'
    if 'attivita_id' in data: l.attivita_id = data['attivita_id']

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Badge / Lista "{l.nome}" aggiornato con successo',
        'lista': l.to_dict(include_members=True)
    })

@liste_bp.route('/<int:id>', methods=['DELETE'])
def delete_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista / Badge non trovato'}), 404

    db.session.delete(l)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Lista / Badge eliminato con successo'})

@liste_bp.route('/<int:id>/membri', methods=['POST'])
def add_membro_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista / Badge non trovato'}), 404

    data = request.get_json() or {}
    cf = normalizza_cf(data.get('codice_fiscale', ''))
    persona = db.session.get(Persona, cf)
    if not persona:
        return jsonify({'error': f'Nessuna persona trovata con Codice Fiscale {cf}'}), 404

    if persona not in l.membri:
        l.membri.append(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'{persona.nominativo} aggiunto/a al badge/lista "{l.nome}"',
        'lista': l.to_dict(include_members=True)
    })

@liste_bp.route('/<int:id>/membri/<cf>', methods=['DELETE'])
def remove_membro_lista(id, cf):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista / Badge non trovato'}), 404

    cf = normalizza_cf(cf)
    persona = db.session.get(Persona, cf)
    if persona and persona in l.membri:
        l.membri.remove(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Rimosso/a dal badge/lista "{l.nome}"',
        'lista': l.to_dict(include_members=True)
    })

@liste_bp.route('/assegna-massa', methods=['POST'])
def assegna_badge_massa():
    """
    Assegna o rimuove uno o più Badge / Liste a un elenco di persone selezionate via checkbox.
    Body: {
      "codici_fiscali": ["CF1", "CF2"],
      "lista_ids_aggiungi": [1, 2],
      "lista_ids_rimuovi": [3]
    }
    """
    data = request.get_json() or {}
    cfs = data.get('codici_fiscali', [])
    aggiungi_ids = data.get('lista_ids_aggiungi', [])
    rimuovi_ids = data.get('lista_ids_rimuovi', [])

    if not isinstance(cfs, list) or not cfs:
        return jsonify({'error': 'Nessuna persona selezionata'}), 400

    persone = []
    for raw_cf in cfs:
        cf = normalizza_cf(raw_cf)
        p = db.session.get(Persona, cf)
        if p:
            persone.append(p)

    if not persone:
        return jsonify({'error': 'Nessuna persona valida trovata'}), 404

    # Liste da aggiungere
    liste_agg = Lista.query.filter(Lista.id.in_(aggiungi_ids)).all() if aggiungi_ids else []
    # Liste da rimuovere
    liste_rim = Lista.query.filter(Lista.id.in_(rimuovi_ids)).all() if rimuovi_ids else []

    for p in persone:
        for l in liste_agg:
            if p not in l.membri:
                l.membri.append(p)
        for l in liste_rim:
            if p in l.membri:
                l.membri.remove(p)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Badge / Liste aggiornati con successo per {len(persone)} persone!'
    })

@liste_bp.route('/genera-automatica', methods=['POST'])
def genera_automatica():
    """
    Genera un Badge / Lista popolato automaticamente in base a:
    - sorgente: 'catechismo', 'doposcuola', 'oratorio_estivo', 'oratorio_invernale', 'attivita', 'anagrafica_filtri'
    - opzioni aggiuntive: gruppo_id, anno_pastorale, attivita_id, sesso, eta_min, eta_max
    """
    data = request.get_json() or {}
    sorgente = data.get('sorgente', 'catechismo').strip().lower()
    nome_badge = data.get('nome', '').strip()
    colore = data.get('colore', '#8B1E1E')
    icona = data.get('icona', '🏅')
    descrizione = data.get('descrizione', '').strip()

    persone_match = set()

    if sorgente == 'catechismo':
        gruppo_id = data.get('gruppo_id')
        anno = data.get('anno_pastorale')
        query = GruppoCatechismo.query
        if gruppo_id: query = query.filter_by(id=gruppo_id)
        if anno: query = query.filter_by(anno_pastorale=anno)
        for g in query.all():
            for r in g.ragazzi: persone_match.add(r)
        if not nome_badge:
            nome_badge = f"Catechismo {anno or 'Comunità'}"
        if not descrizione:
            descrizione = f"Iscritti al cammino di Catechismo {anno or ''}".strip()

    elif sorgente == 'doposcuola':
        gruppo_id = data.get('gruppo_id')
        anno = data.get('anno_scolastico') or data.get('anno_pastorale')
        query = GruppoDoposcuola.query
        if gruppo_id: query = query.filter_by(id=gruppo_id)
        if anno: query = query.filter_by(anno_scolastico=anno)
        for g in query.all():
            for s in g.studenti: persone_match.add(s)
        if not nome_badge:
            nome_badge = f"Doposcuola {anno or 'Studio'}"
        if not descrizione:
            descrizione = f"Studenti del Doposcuola & Studio Pomeridiano {anno or ''}".strip()

    elif sorgente in ['oratorio_estivo', 'oratorio_invernale']:
        tipo = 'estivo' if sorgente == 'oratorio_estivo' else 'invernale'
        gruppo_id = data.get('gruppo_id')
        anno = data.get('anno_pastorale')
        query = GruppoOratorio.query.filter_by(tipo_oratorio=tipo)
        if gruppo_id: query = query.filter_by(id=gruppo_id)
        if anno: query = query.filter_by(anno_pastorale=anno)
        for g in query.all():
            for r in g.ragazzi: persone_match.add(r)
        if not nome_badge:
            nome_badge = f"Oratorio {'Estivo (Estate Ragazzi)' if tipo == 'estivo' else 'Invernale'} {anno or ''}".strip()
        if not descrizione:
            descrizione = f"Partecipanti Oratorio {tipo.capitalize()} {anno or ''}".strip()

    elif sorgente == 'attivita':
        att_id = data.get('attivita_id')
        if not att_id:
            return jsonify({'error': 'ID attività obbligatorio'}), 400
        att = db.session.get(Attivita, att_id)
        if not att:
            return jsonify({'error': 'Attività non trovata'}), 404
        for isc in att.iscrizioni:
            if isc.stato in ['confermata', 'in_attesa'] and isc.partecipante:
                persone_match.add(isc.partecipante)
        if not nome_badge:
            nome_badge = f"Iscritti: {att.titolo}"
        if not descrizione:
            descrizione = f"Partecipanti iscritti a {att.titolo}"

    # Filtri opzionali anagrafici (Età, Sesso)
    sesso = data.get('sesso')
    eta_min = data.get('eta_min')
    eta_max = data.get('eta_max')

    filtrati = []
    for p in persone_match:
        if sesso and p.sesso != sesso:
            continue
        if eta_min is not None and (p.eta is None or p.eta < int(eta_min)):
            continue
        if eta_max is not None and (p.eta is None or p.eta > int(eta_max)):
            continue
        filtrati.append(p)

    if not nome_badge:
        nome_badge = "Nuovo Badge Parrocchiale"

    nuova_lista = Lista(
        nome=nome_badge,
        descrizione=descrizione,
        colore=colore,
        icona=icona,
        categoria='badge'
    )
    for p in filtrati:
        nuova_lista.membri.append(p)

    db.session.add(nuova_lista)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Badge "{nuova_lista.nome}" generato con successo con {len(filtrati)} partecipanti!',
        'lista': nuova_lista.to_dict(include_members=True)
    }), 201

@liste_bp.route('/genera-da-attivita', methods=['POST'])
def genera_da_attivita():
    """Crea o sincronizza automaticamente una lista a partire dagli iscritti di un'attività."""
    data = request.get_json() or {}
    attivita_id = data.get('attivita_id')
    if not attivita_id:
        return jsonify({'error': 'ID attività obbligatorio'}), 400

    att = db.session.get(Attivita, attivita_id)
    if not att:
        return jsonify({'error': 'Attività non trovata'}), 404

    nome_lista = data.get('nome_lista') or f"Iscritti: {att.titolo}"
    lista = Lista.query.filter_by(attivita_id=attivita_id).first()
    if not lista:
        lista = Lista(
            nome=nome_lista,
            descrizione=f"Elenco dei partecipanti iscritti all'attività {att.titolo}",
            attivita_id=attivita_id,
            colore='#1d5f9e',
            icona='🏅',
            categoria='badge'
        )
        db.session.add(lista)
        db.session.flush()

    for isc in att.iscrizioni:
        if isc.stato in ['confermata', 'in_attesa'] and isc.partecipante not in lista.membri:
            lista.membri.append(isc.partecipante)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Lista / Badge "{lista.nome}" sincronizzato con {len(lista.membri)} partecipanti!',
        'lista': lista.to_dict(include_members=True)
    })

@liste_bp.route('/<int:id>/export-excel', methods=['GET'])
def export_excel_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista non trovata'}), 404

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Lista {l.nome[:25]}"

    header_fill = PatternFill(start_color="8B1E1E", end_color="8B1E1E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    headers = ["Codice Fiscale", "Cognome", "Nome", "Sesso", "Età", "Telefono", "Email", "Famiglia", "Note Sanitarie"]
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, p in enumerate(l.membri, start=2):
        ws.cell(row=row_idx, column=1, value=p.codice_fiscale)
        ws.cell(row=row_idx, column=2, value=p.cognome)
        ws.cell(row=row_idx, column=3, value=p.nome)
        ws.cell(row=row_idx, column=4, value=p.sesso or "")
        ws.cell(row=row_idx, column=5, value=p.eta if p.eta is not None else "")
        ws.cell(row=row_idx, column=6, value=p.telefono or "")
        ws.cell(row=row_idx, column=7, value=p.email or "")
        ws.cell(row=row_idx, column=8, value=p.nucleo.nome_famiglia if p.nucleo else "")
        ws.cell(row=row_idx, column=9, value=f"{p.intolleranze_alimentari or ''} {p.allergie or ''}".strip())

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    nome_clean = "".join(c for c in l.nome if c.isalnum() or c in (' ', '_', '-')).strip()
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'lista_{nome_clean}.xlsx'
    )
