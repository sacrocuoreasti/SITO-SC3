from flask import Blueprint, request, jsonify, send_file
from models import db, Lista, Persona, Attivita, Iscrizione
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
        return jsonify({'error': 'Lista non trovata'}), 404
    return jsonify({'lista': l.to_dict(include_members=True)})

@liste_bp.route('', methods=['POST'])
def create_lista():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome della lista è obbligatorio'}), 400

    nuova = Lista(
        nome=nome,
        descrizione=data.get('descrizione', '').strip(),
        colore=data.get('colore', '#8B1E1E'),
        attivita_id=data.get('attivita_id')
    )
    db.session.add(nuova)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Lista "{nuova.nome}" creata con successo',
        'lista': nuova.to_dict(include_members=True)
    }), 201

@liste_bp.route('/<int:id>', methods=['PUT'])
def update_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista non trovata'}), 404

    data = request.get_json() or {}
    if 'nome' in data: l.nome = data['nome'].strip()
    if 'descrizione' in data: l.descrizione = data['descrizione'].strip()
    if 'colore' in data: l.colore = data['colore'].strip()
    if 'attivita_id' in data: l.attivita_id = data['attivita_id']

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Lista aggiornata con successo',
        'lista': l.to_dict(include_members=True)
    })

@liste_bp.route('/<int:id>', methods=['DELETE'])
def delete_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista non trovata'}), 404

    db.session.delete(l)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Lista eliminata con successo'})

@liste_bp.route('/<int:id>/membri', methods=['POST'])
def add_membro_lista(id):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista non trovata'}), 404

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
        'message': f'{persona.nominativo} aggiunto/a alla lista "{l.nome}"',
        'lista': l.to_dict(include_members=True)
    })

@liste_bp.route('/<int:id>/membri/<cf>', methods=['DELETE'])
def remove_membro_lista(id, cf):
    l = db.session.get(Lista, id)
    if not l:
        return jsonify({'error': 'Lista non trovata'}), 404

    cf = normalizza_cf(cf)
    persona = db.session.get(Persona, cf)
    if persona and persona in l.membri:
        l.membri.remove(persona)
        db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Rimosso dalla lista "{l.nome}"',
        'lista': l.to_dict(include_members=True)
    })

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

    # Trova o crea lista
    nome_lista = data.get('nome_lista') or f"Iscritti: {att.titolo}"
    lista = Lista.query.filter_by(attivita_id=attivita_id).first()
    if not lista:
        lista = Lista(
            nome=nome_lista,
            descrizione=f"Elenco dei partecipanti iscritti all'attività {att.titolo}",
            attivita_id=attivita_id,
            colore='#1d5f9e'
        )
        db.session.add(lista)
        db.session.flush()

    # Aggiungi tutti i partecipanti confermati dell'attività
    count_aggiunti = 0
    for isc in att.iscrizioni:
        if isc.stato in ['confermata', 'in_attesa'] and isc.partecipante not in lista.membri:
            lista.membri.append(isc.partecipante)
            count_aggiunti += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Lista "{lista.nome}" creata/aggiornata con {len(lista.membri)} partecipanti!',
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
