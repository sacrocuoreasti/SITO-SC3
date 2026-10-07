import re
from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, CategoriaAttivita, AllergiaConfig, ClausolaIscrizione, CampoPersonalizzato

configurazioni_bp = Blueprint('configurazioni_bp', __name__, url_prefix='/api/configurazioni')

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

# ================= 1. CATEGORIE ATTIVITÀ =================
@configurazioni_bp.route('/categorie', methods=['GET'])
def get_categorie():
    solo_attive = request.args.get('solo_attive', 'false').lower() in ['true', '1']
    query = CategoriaAttivita.query
    if solo_attive:
        query = query.filter_by(is_attiva=True)
    cats = query.order_by(CategoriaAttivita.ordine.asc(), CategoriaAttivita.id.asc()).all()
    return jsonify({
        'total': len(cats),
        'categorie': [c.to_dict() for c in cats]
    })

@configurazioni_bp.route('/categorie', methods=['POST'])
def create_categoria():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome della categoria è obbligatorio'}), 400

    codice = slugify(data.get('codice') or nome)
    if CategoriaAttivita.query.filter_by(codice=codice).first():
        codice = f"{codice}_{CategoriaAttivita.query.count() + 1}"

    nuova = CategoriaAttivita(
        codice=codice,
        nome=nome,
        icona=data.get('icona', '✦').strip(),
        is_attiva=bool(data.get('is_attiva', True)),
        ordine=int(data.get('ordine', 0))
    )
    db.session.add(nuova)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Categoria "{nuova.nome}" creata', 'categoria': nuova.to_dict()}), 201

@configurazioni_bp.route('/categorie/<identifier>', methods=['PUT'])
def update_categoria(identifier):
    if str(identifier).isdigit():
        c = db.session.get(CategoriaAttivita, int(identifier))
    else:
        c = CategoriaAttivita.query.filter_by(codice=identifier).first()
    if not c:
        return jsonify({'error': 'Categoria non trovata'}), 404

    data = request.get_json() or {}
    if 'nome' in data: c.nome = data['nome'].strip()
    if 'icona' in data: c.icona = data['icona'].strip()
    if 'is_attiva' in data: c.is_attiva = bool(data['is_attiva'])
    if 'ordine' in data: c.ordine = int(data['ordine'])
    db.session.commit()
    return jsonify({'success': True, 'message': 'Categoria aggiornata', 'categoria': c.to_dict()})

@configurazioni_bp.route('/categorie/<identifier>', methods=['DELETE'])
def delete_categoria(identifier):
    if str(identifier).isdigit():
        c = db.session.get(CategoriaAttivita, int(identifier))
    else:
        c = CategoriaAttivita.query.filter_by(codice=identifier).first()
    if not c:
        return jsonify({'error': 'Categoria non trovata'}), 404

    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Categoria eliminata'})


# ================= 2. ALLERGIE & INTOLLERANZE SUGGERITE =================
@configurazioni_bp.route('/allergie', methods=['GET'])
def get_allergie():
    solo_attive = request.args.get('solo_attive', 'true').lower() in ['true', '1']
    query = AllergiaConfig.query
    if solo_attive:
        query = query.filter_by(is_attiva=True)
    items = query.order_by(AllergiaConfig.ordine.asc(), AllergiaConfig.id.asc()).all()
    return jsonify({
        'total': len(items),
        'allergie': [a.to_dict() for a in items]
    })

@configurazioni_bp.route('/allergie', methods=['POST'])
def create_allergia():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome dell\'allergia/intolleranza è obbligatorio'}), 400

    esistente = AllergiaConfig.query.filter(AllergiaConfig.nome.ilike(nome)).first()
    if esistente:
        return jsonify({'error': f'L\'opzione "{nome}" esiste già'}), 409

    nuova = AllergiaConfig(
        nome=nome,
        categoria=data.get('categoria', 'alimentare').strip(),
        is_attiva=bool(data.get('is_attiva', True)),
        ordine=int(data.get('ordine', 0))
    )
    db.session.add(nuova)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Voce sanitaria "{nuova.nome}" aggiunta', 'allergia': nuova.to_dict()}), 201

@configurazioni_bp.route('/allergie/<int:id>', methods=['PUT'])
def update_allergia(id):
    a = db.session.get(AllergiaConfig, id)
    if not a:
        return jsonify({'error': 'Voce non trovata'}), 404
    data = request.get_json() or {}
    if 'nome' in data: a.nome = data['nome'].strip()
    if 'categoria' in data: a.categoria = data['categoria'].strip()
    if 'is_attiva' in data: a.is_attiva = bool(data['is_attiva'])
    if 'ordine' in data: a.ordine = int(data['ordine'])
    db.session.commit()
    return jsonify({'success': True, 'message': 'Opzione sanitaria aggiornata', 'allergia': a.to_dict()})

@configurazioni_bp.route('/allergie/<int:id>', methods=['DELETE'])
def delete_allergia(id):
    a = db.session.get(AllergiaConfig, id)
    if not a:
        return jsonify({'error': 'Voce non trovata'}), 404
    db.session.delete(a)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Opzione sanitaria eliminata'})


# ================= 3. CLAUSOLE ISCRIZIONE (OBBLIGATORIE / FACOLTATIVE) =================
@configurazioni_bp.route('/clausole', methods=['GET'])
def get_clausole():
    solo_attive = request.args.get('solo_attive', 'true').lower() in ['true', '1']
    query = ClausolaIscrizione.query
    if solo_attive:
        query = query.filter_by(is_attiva=True)
    items = query.order_by(ClausolaIscrizione.ordine.asc(), ClausolaIscrizione.id.asc()).all()
    return jsonify({
        'total': len(items),
        'clausole': [c.to_dict() for c in items]
    })

@configurazioni_bp.route('/clausole', methods=['POST'])
def create_clausola():
    data = request.get_json() or {}
    titolo = data.get('titolo', '').strip()
    testo = data.get('testo', '').strip()
    if not titolo or not testo:
        return jsonify({'error': 'Titolo e testo della clausola sono obbligatori'}), 400

    nuova = ClausolaIscrizione(
        titolo=titolo,
        testo=testo,
        is_obbligatoria=bool(data.get('is_obbligatoria', True)),
        is_attiva=bool(data.get('is_attiva', True)),
        ordine=int(data.get('ordine', 0))
    )
    db.session.add(nuova)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Clausola "{nuova.titolo}" creata', 'clausola': nuova.to_dict()}), 201

@configurazioni_bp.route('/clausole/<int:id>', methods=['PUT'])
def update_clausola(id):
    c = db.session.get(ClausolaIscrizione, id)
    if not c:
        return jsonify({'error': 'Clausola non trovata'}), 404
    data = request.get_json() or {}
    if 'titolo' in data: c.titolo = data['titolo'].strip()
    if 'testo' in data: c.testo = data['testo'].strip()
    if 'is_obbligatoria' in data: c.is_obbligatoria = bool(data['is_obbligatoria'])
    if 'is_attiva' in data: c.is_attiva = bool(data['is_attiva'])
    if 'ordine' in data: c.ordine = int(data['ordine'])
    db.session.commit()
    return jsonify({'success': True, 'message': 'Clausola aggiornata', 'clausola': c.to_dict()})

@configurazioni_bp.route('/clausole/<int:id>', methods=['DELETE'])
def delete_clausola(id):
    c = db.session.get(ClausolaIscrizione, id)
    if not c:
        return jsonify({'error': 'Clausola non trovata'}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Clausola eliminata'})


# ================= 4. CAMPI PERSONALIZZATI ACCOUNT / UTENTE =================
@configurazioni_bp.route('/campi-account', methods=['GET'])
def get_campi_account():
    solo_attive = request.args.get('solo_attive', 'true').lower() in ['true', '1']
    query = CampoPersonalizzato.query
    if solo_attive:
        query = query.filter_by(is_attivo=True)
    items = query.order_by(CampoPersonalizzato.ordine.asc(), CampoPersonalizzato.id.asc()).all()
    return jsonify({
        'total': len(items),
        'campi': [cp.to_dict() for cp in items]
    })

@configurazioni_bp.route('/campi-account', methods=['POST'])
def create_campo_account():
    data = request.get_json() or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'error': 'Il nome del campo è obbligatorio'}), 400

    chiave = slugify(data.get('chiave') or nome)
    if CampoPersonalizzato.query.filter_by(chiave=chiave).first():
        chiave = f"{chiave}_{CampoPersonalizzato.query.count() + 1}"

    nuovo = CampoPersonalizzato(
        nome=nome,
        chiave=chiave,
        tipo=data.get('tipo', 'testo').strip(),
        obbligatorio=bool(data.get('obbligatorio', False)),
        opzioni=data.get('opzioni', '').strip(),
        is_attivo=bool(data.get('is_attivo', True)),
        ordine=int(data.get('ordine', 0))
    )
    db.session.add(nuovo)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Campo personalizzato "{nuovo.nome}" creato', 'campo': nuovo.to_dict()}), 201

@configurazioni_bp.route('/campi-account/<int:id>', methods=['PUT'])
def update_campo_account(id):
    cp = db.session.get(CampoPersonalizzato, id)
    if not cp:
        return jsonify({'error': 'Campo non trovato'}), 404
    data = request.get_json() or {}
    if 'nome' in data: cp.nome = data['nome'].strip()
    if 'tipo' in data: cp.tipo = data['tipo'].strip()
    if 'obbligatorio' in data: cp.obbligatorio = bool(data['obbligatorio'])
    if 'opzioni' in data: cp.opzioni = data['opzioni'].strip()
    if 'is_attivo' in data: cp.is_attivo = bool(data['is_attiva'])
    if 'ordine' in data: cp.ordine = int(data['ordine'])
    db.session.commit()
    return jsonify({'success': True, 'message': 'Campo personalizzato aggiornato', 'campo': cp.to_dict()})

@configurazioni_bp.route('/campi-account/<int:id>', methods=['DELETE'])
def delete_campo_account(id):
    cp = db.session.get(CampoPersonalizzato, id)
    if not cp:
        return jsonify({'error': 'Campo non trovato'}), 404
    db.session.delete(cp)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Campo personalizzato eliminato'})
