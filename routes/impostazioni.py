from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, ImpostazioniSito, Attivita, NotiziaEvento

impostazioni_bp = Blueprint('impostazioni_bp', __name__, url_prefix='/api/impostazioni')

def get_or_create_impostazioni():
    imp = ImpostazioniSito.query.first()
    if not imp:
        imp = ImpostazioniSito()
        db.session.add(imp)
        db.session.commit()
    return imp

@impostazioni_bp.route('/homepage', methods=['GET'])
def get_homepage_settings():
    imp = get_or_create_impostazioni()
    return jsonify({'impostazioni': imp.to_dict()})

@impostazioni_bp.route('/homepage', methods=['PUT'])
def update_homepage_settings():
    imp = get_or_create_impostazioni()
    data = request.get_json() or {}

    if 'mostra_orari_messe' in data: imp.mostra_orari_messe = bool(data['mostra_orari_messe'])
    if 'mostra_attivita' in data: imp.mostra_attivita = bool(data['mostra_attivita'])
    if 'mostra_avvisi' in data: imp.mostra_avvisi = bool(data['mostra_avvisi'])
    if 'mostra_contatti' in data: imp.mostra_contatti = bool(data['mostra_contatti'])
    if 'mostra_banner' in data: imp.mostra_banner = bool(data['mostra_banner'])
    if 'testo_banner' in data: imp.testo_banner = data['testo_banner'].strip()
    if 'titolo_hero' in data: imp.titolo_hero = data['titolo_hero'].strip()
    if 'sottotitolo_hero' in data: imp.sottotitolo_hero = data['sottotitolo_hero'].strip()
    if 'testo_benvenuto' in data: imp.testo_benvenuto = data['testo_benvenuto'].strip()
    if 'segreteria_titolo' in data: imp.segreteria_titolo = data['segreteria_titolo'].strip()
    if 'segreteria_sottotitolo' in data: imp.segreteria_sottotitolo = data['segreteria_sottotitolo'].strip()
    if 'segreteria_indirizzo' in data: imp.segreteria_indirizzo = data['segreteria_indirizzo'].strip()
    if 'segreteria_telefono' in data: imp.segreteria_telefono = data['segreteria_telefono'].strip()
    if 'segreteria_email' in data: imp.segreteria_email = data['segreteria_email'].strip()
    if 'segreteria_orari' in data: imp.segreteria_orari = data['segreteria_orari'].strip()

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Impostazioni della Homepage pubblica salvate con successo!',
        'impostazioni': imp.to_dict()
    })

@impostazioni_bp.route('/dati-pubblici', methods=['GET'])
def get_dati_pubblici():
    """Ritorna solo le attività e gli avvisi contrassegnati come 'pubblicati' per la homepage."""
    imp = get_or_create_impostazioni()

    attivita = Attivita.query.filter_by(is_attiva=True, is_pubblicato=True).order_by(Attivita.id.desc()).all()
    avvisi = NotiziaEvento.query.filter_by(is_pubblicato=True).order_by(NotiziaEvento.id.desc()).all()

    return jsonify({
        'impostazioni': imp.to_dict(),
        'attivita': [a.to_dict() for a in attivita],
        'avvisi': [av.to_dict() for av in avvisi]
    })

# ---------------- GESTIONE EVENTI & AVVISI (PUBBLICATI VS BOZZE) ----------------
@impostazioni_bp.route('/eventi', methods=['GET'])
def get_eventi():
    """Ritorna tutti gli eventi e avvisi (anche bozze) per la gestione della segreteria."""
    solo_pubblicati = request.args.get('solo_pubblicati', 'false').lower() in ['true', '1']
    query = NotiziaEvento.query
    if solo_pubblicati:
        query = query.filter_by(is_pubblicato=True)
    eventi = query.order_by(NotiziaEvento.id.desc()).all()
    return jsonify({
        'total': len(eventi),
        'eventi': [e.to_dict() for e in eventi]
    })

@impostazioni_bp.route('/eventi', methods=['POST'])
def create_evento():
    data = request.get_json() or {}
    titolo = data.get('titolo', '').strip()
    contenuto = data.get('contenuto', '').strip()
    if not titolo or not contenuto:
        return jsonify({'error': 'Titolo e contenuto sono obbligatori'}), 400

    data_evento = None
    if data.get('data_evento'):
        try:
            data_evento = datetime.strptime(data['data_evento'], '%Y-%m-%d').date()
        except Exception:
            pass

    evento = NotiziaEvento(
        titolo=titolo,
        categoria=data.get('categoria', 'evento').strip(),
        contenuto=contenuto,
        data_evento=data_evento,
        in_evidenza=bool(data.get('in_evidenza', True)),
        is_pubblicato=bool(data.get('is_pubblicato', True))
    )
    db.session.add(evento)
    db.session.commit()

    stato_str = "Pubblicato" if evento.is_pubblicato else "In Bozza"
    return jsonify({
        'success': True,
        'message': f'Evento "{evento.titolo}" salvato con successo ({stato_str})',
        'evento': evento.to_dict()
    }), 201

@impostazioni_bp.route('/eventi/<int:id>/toggle-pubblicazione', methods=['PUT'])
def toggle_evento_pubblicazione(id):
    evento = db.session.get(NotiziaEvento, id)
    if not evento:
        return jsonify({'error': 'Evento non trovato'}), 404

    evento.is_pubblicato = not evento.is_pubblicato
    db.session.commit()

    stato_str = "Pubblicato sulla Homepage" if evento.is_pubblicato else "Messo in Bozza (non visibile al pubblico)"
    return jsonify({
        'success': True,
        'message': f'Stato evento modificato: {stato_str}',
        'evento': evento.to_dict()
    })

@impostazioni_bp.route('/eventi/<int:id>', methods=['PUT'])
def update_evento(id):
    evento = db.session.get(NotiziaEvento, id)
    if not evento:
        return jsonify({'error': 'Evento non trovato'}), 404

    data = request.get_json() or {}
    if 'titolo' in data: evento.titolo = data['titolo'].strip()
    if 'categoria' in data: evento.categoria = data['categoria'].strip()
    if 'contenuto' in data: evento.contenuto = data['contenuto'].strip()
    if 'in_evidenza' in data: evento.in_evidenza = bool(data['in_evidenza'])
    if 'is_pubblicato' in data: evento.is_pubblicato = bool(data['is_pubblicato'])
    if 'data_evento' in data:
        if data['data_evento']:
            try: evento.data_evento = datetime.strptime(data['data_evento'], '%Y-%m-%d').date()
            except Exception: pass
        else:
            evento.data_evento = None

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Evento aggiornato con successo',
        'evento': evento.to_dict()
    })

@impostazioni_bp.route('/eventi/<int:id>', methods=['DELETE'])
def delete_evento(id):
    evento = db.session.get(NotiziaEvento, id)
    if not evento:
        return jsonify({'error': 'Evento non trovato'}), 404

    db.session.delete(evento)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Evento eliminato con successo'})
