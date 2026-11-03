from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, Celebrazione, NotiziaEvento
from services.access_control import can
from datetime import date
import re
from werkzeug.exceptions import BadRequest

celebrazioni_bp = Blueprint('celebrazioni_bp', __name__, url_prefix='/api/celebrazioni')

def check_staff():
    return can('segreteria.celebrazioni')


def parse_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise BadRequest('Indica una data valida nel formato AAAA-MM-GG')
    try:return date.fromisoformat(value)
    except ValueError:raise BadRequest('La data indicata non è valida')


def apply_specific_date(celebration,data,creating=False):
    if celebration.sezione=='avvenimenti':
        if 'data_specifica' in data:
            celebration.data_specifica=parse_date(data['data_specifica'])
            celebration.giorno=''
        elif creating or ('sezione' in data and not celebration.data_specifica):
            raise BadRequest('Per un avvenimento seleziona una data specifica')
    elif 'data_specifica' in data or 'sezione' in data:
        celebration.data_specifica=None

@celebrazioni_bp.route('', methods=['GET'])
def get_celebrazioni():
    sezione = request.args.get('sezione', '').strip().lower()
    include_inattivi = check_staff()
    query = Celebrazione.query
    if not include_inattivi:
        query = query.filter_by(is_attivo=True)
    if sezione:
        query = query.filter_by(sezione=sezione)
    
    tutte = query.order_by(Celebrazione.sezione.asc(), Celebrazione.ordine.asc(), Celebrazione.id.asc()).all()
    
    messe = [c.to_dict() for c in tutte if c.sezione == 'messe']
    liturgia = [c.to_dict() for c in tutte if c.sezione == 'liturgia']
    avvenimenti = [c.to_dict() for c in tutte if c.sezione == 'avvenimenti']
    
    return jsonify({
        'total': len(tutte),
        'celebrazioni': [c.to_dict() for c in tutte],
        'messe': messe,
        'liturgia': liturgia,
        'avvenimenti': avvenimenti,
        'avvisi':[n.to_dict() for n in NotiziaEvento.query.filter_by(categoria='avviso').order_by(NotiziaEvento.id.desc()).all() if include_inattivi or n.is_pubblicato]
    })

@celebrazioni_bp.route('', methods=['POST'])
def create_celebrazione():
    if not check_staff():
        return jsonify({'error': 'Accesso riservato alla segreteria parrocchiale'}), 403
    
    data = request.get_json(silent=True) or {}
    sezione = data.get('sezione', 'messe').strip().lower()
    titolo = data.get('titolo', '').strip()
    
    if not titolo:
        return jsonify({'error': 'Il titolo della celebrazione è obbligatorio'}), 400
    
    if sezione not in ['messe', 'liturgia', 'avvenimenti']:
        sezione = 'messe'
        
    c = Celebrazione(
        sezione=sezione,
        titolo=titolo,
        descrizione=data.get('descrizione', '').strip(),
        giorno=data.get('giorno', '').strip(),
        orario=data.get('orario', '').strip(),
        luogo=data.get('luogo', 'Chiesa Parrocchiale').strip() or 'Chiesa Parrocchiale',
        ordine=int(data.get('ordine', 0)),
        is_attivo=bool(data.get('is_attivo', True))
    )
    apply_specific_date(c,data,creating=True)
    db.session.add(c)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'"{c.titolo}" aggiunto alle {c.sezione}',
        'celebrazione': c.to_dict()
    }), 201

@celebrazioni_bp.route('/<int:id>', methods=['PUT'])
def update_celebrazione(id):
    if not check_staff():
        return jsonify({'error': 'Accesso riservato alla segreteria parrocchiale'}), 403
    
    c = db.session.get(Celebrazione, id)
    if not c:
        return jsonify({'error': 'Celebrazione non trovata'}), 404
        
    data = request.get_json(silent=True) or {}
    if 'sezione' in data:
        sez = data['sezione'].strip().lower()
        if sez in ['messe', 'liturgia', 'avvenimenti']:
            c.sezione = sez
    if 'titolo' in data: c.titolo = data['titolo'].strip()
    if 'descrizione' in data: c.descrizione = data['descrizione'].strip()
    if 'giorno' in data: c.giorno = data['giorno'].strip()
    if 'orario' in data: c.orario = data['orario'].strip()
    if 'luogo' in data: c.luogo = data['luogo'].strip() or 'Chiesa Parrocchiale'
    if 'ordine' in data: c.ordine = int(data['ordine'])
    if 'is_attivo' in data: c.is_attivo = bool(data['is_attivo'])
    apply_specific_date(c,data)
    
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'"{c.titolo}" aggiornato con successo',
        'celebrazione': c.to_dict()
    })

@celebrazioni_bp.route('/<int:id>', methods=['DELETE'])
def delete_celebrazione(id):
    if not check_staff():
        return jsonify({'error': 'Accesso riservato alla segreteria parrocchiale'}), 403
    
    c = db.session.get(Celebrazione, id)
    if not c:
        return jsonify({'error': 'Celebrazione non trovata'}), 404
        
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Celebrazione eliminata con successo'})


@celebrazioni_bp.route('/avvisi',methods=['POST'])
def create_notice():
    data=request.get_json() or {}
    title=data.get('titolo','');body=data.get('contenuto','')
    if not isinstance(title,str) or not title.strip() or len(title)>150 or not isinstance(body,str) or not body.strip():
        raise BadRequest('Indica titolo e contenuto dell’avviso (titolo: massimo 150 caratteri)')
    notice=NotiziaEvento(titolo=title.strip(),contenuto=body.strip(),categoria='avviso',
                        data_evento=parse_date(data['data_evento']) if data.get('data_evento') else None,
                        is_pubblicato=bool(data.get('is_pubblicato',True)),in_evidenza=True)
    db.session.add(notice);db.session.commit()
    return jsonify(success=True,message='Avviso salvato',avviso=notice.to_dict()),201
