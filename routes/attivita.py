from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Attivita, Iscrizione
from datetime import datetime

attivita_bp = Blueprint('attivita_bp', __name__, url_prefix='/api/attivita')

@attivita_bp.route('', methods=['GET'])
def get_attivita():
    categoria = request.args.get('categoria', '').strip()
    solo_attive = request.args.get('solo_attive', 'true').lower() in ['true', '1']
    include_bozze = request.args.get('include_bozze', 'false').lower() in ['true', '1']

    # Se l'utente è segreteria/admin/parroco, può richiedere anche le bozze
    is_staff = current_user.is_authenticated and current_user.has_role('segreteria', 'admin', 'parroco')

    query = Attivita.query
    if solo_attive:
        query = query.filter(Attivita.is_attiva == True)

    # Chi non è staff o non ha richiesto le bozze vede solo quelle pubblicate
    if not (is_staff and include_bozze):
        query = query.filter(Attivita.is_pubblicato == True)

    if categoria:
        query = query.filter(Attivita.categoria == categoria)

    attivita = query.order_by(Attivita.id.desc()).all()
    return jsonify({
        'total': len(attivita),
        'attivita': [a.to_dict() for a in attivita]
    })

@attivita_bp.route('/<int:id>', methods=['GET'])
def get_attivita_detail(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    d = a.to_dict()
    d['iscritti'] = [i.to_dict() for i in a.iscrizioni]
    return jsonify({'attivita': d})

@attivita_bp.route('', methods=['POST'])
def create_attivita():
    data = request.get_json() or {}
    titolo = data.get('titolo', '').strip()
    categoria = data.get('categoria', 'oratorio').strip()

    if not titolo:
        return jsonify({'error': 'Il titolo dell\'attività è obbligatorio'}), 400

    data_inizio = None
    data_fine = None
    if data.get('data_inizio'):
        try: data_inizio = datetime.strptime(data['data_inizio'], '%Y-%m-%d').date()
        except Exception: pass
    if data.get('data_fine'):
        try: data_fine = datetime.strptime(data['data_fine'], '%Y-%m-%d').date()
        except Exception: pass

    nuova = Attivita(
        titolo=titolo,
        categoria=categoria,
        descrizione=data.get('descrizione', '').strip(),
        anno_pastorale=data.get('anno_pastorale', '2025/2026').strip(),
        eta_min=int(data.get('eta_min', 0)),
        eta_max=int(data.get('eta_max', 99)),
        quota_iscrizione=float(data.get('quota_iscrizione', 0.0)),
        posti_massimi=int(data['posti_massimi']) if data.get('posti_massimi') else None,
        data_inizio=data_inizio,
        data_fine=data_fine,
        is_attiva=data.get('is_attiva', True),
        is_pubblicato=data.get('is_pubblicato', True)
    )
    if 'campi_extra' in data:
        nuova.campi_extra = data['campi_extra']
    if 'campi_personalizzati' in data:
        nuova.campi_personalizzati = data['campi_personalizzati']

    db.session.add(nuova)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Attività "{nuova.titolo}" creata con successo ({ "Pubblicata" if nuova.is_pubblicato else "In Bozza" })',
        'attivita': nuova.to_dict()
    }), 201

@attivita_bp.route('/<int:id>', methods=['PUT'])
def update_attivita(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    data = request.get_json() or {}
    if 'titolo' in data: a.titolo = data['titolo'].strip()
    if 'categoria' in data: a.categoria = data['categoria'].strip()
    if 'descrizione' in data: a.descrizione = data['descrizione'].strip()
    if 'anno_pastorale' in data: a.anno_pastorale = data['anno_pastorale'].strip()
    if 'eta_min' in data: a.eta_min = int(data['eta_min'])
    if 'eta_max' in data: a.eta_max = int(data['eta_max'])
    if 'quota_iscrizione' in data: a.quota_iscrizione = float(data['quota_iscrizione'])
    if 'posti_massimi' in data:
        a.posti_massimi = int(data['posti_massimi']) if data['posti_massimi'] is not None else None
    if 'is_attiva' in data: a.is_attiva = bool(data['is_attiva'])
    if 'is_pubblicato' in data: a.is_pubblicato = bool(data['is_pubblicato'])
    if 'campi_extra' in data: a.campi_extra = data['campi_extra']
    if 'campi_personalizzati' in data: a.campi_personalizzati = data['campi_personalizzati']

    if 'data_inizio' in data:
        if data['data_inizio']:
            try: a.data_inizio = datetime.strptime(data['data_inizio'], '%Y-%m-%d').date()
            except Exception: pass
        else:
            a.data_inizio = None
    if 'data_fine' in data:
        if data['data_fine']:
            try: a.data_fine = datetime.strptime(data['data_fine'], '%Y-%m-%d').date()
            except Exception: pass
        else:
            a.data_fine = None

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Attività "{a.titolo}" aggiornata con successo',
        'attivita': a.to_dict()
    })

@attivita_bp.route('/<int:id>/locandina', methods=['POST'])
def upload_locandina(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    if 'locandina' not in request.files:
        return jsonify({'error': 'Nessun file selezionato'}), 400

    file = request.files['locandina']
    if not file or file.filename == '':
        return jsonify({'error': 'File non valido'}), 400

    import os
    from flask import current_app
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.pdf']:
        return jsonify({'error': 'Formato file non supportato. Carica un\'immagine (JPG, PNG, WebP) o PDF.'}), 400

    filename = f"locandina_{id}_{int(datetime.utcnow().timestamp())}{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    if a.locandina_path and a.locandina_path != filename:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], a.locandina_path)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except Exception: pass

    a.locandina_path = filename
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Locandina per "{a.titolo}" caricata con successo',
        'attivita': a.to_dict()
    })

@attivita_bp.route('/<int:id>/locandina', methods=['DELETE'])
def delete_locandina(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    if a.locandina_path:
        import os
        from flask import current_app
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], a.locandina_path)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except Exception: pass
        a.locandina_path = None
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Locandina rimossa con successo',
        'attivita': a.to_dict()
    })

@attivita_bp.route('/<int:id>/toggle-pubblicazione', methods=['PUT'])
def toggle_pubblicazione(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    a.is_pubblicato = not a.is_pubblicato
    db.session.commit()

    stato_str = "Pubblicata" if a.is_pubblicato else "In Bozza"
    return jsonify({
        'success': True,
        'message': f'Stato pubblicazione modificato: {stato_str}',
        'attivita': a.to_dict()
    })

@attivita_bp.route('/<int:id>', methods=['DELETE'])
def delete_attivita(id):
    a = db.session.get(Attivita, id)
    if not a:
        return jsonify({'error': 'Attività non trovata'}), 404

    try:
        from models import Presenza, Lista, GruppoCatechismo
        Presenza.query.filter_by(attivita_id=id).delete()
        for l in Lista.query.filter_by(attivita_id=id).all():
            db.session.delete(l)
        for g in GruppoCatechismo.query.filter_by(attivita_id=id).all():
            g.attivita_id = None

        if a.locandina_path:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], a.locandina_path)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        db.session.delete(a)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Attività eliminata con successo'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Impossibile eliminare l'attività: {str(e)}"}), 500

