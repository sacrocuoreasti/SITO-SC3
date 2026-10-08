from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_login import current_user
from models import db, ImpostazioniSito, Attivita, NotiziaEvento, CalendarioComunita

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
    if 'iban' in data: imp.iban = data['iban'].strip()
    if 'satispay_url' in data: imp.satispay_url = data['satispay_url'].strip()
    if 'intestatario_offerte' in data: imp.intestatario_offerte = data['intestatario_offerte'].strip()
    if 'causale_predefinita_offerte' in data: imp.causale_predefinita_offerte = data['causale_predefinita_offerte'].strip()

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Impostazioni della Homepage pubblica salvate con successo!',
        'impostazioni': imp.to_dict()
    })

@impostazioni_bp.route('/dati-pubblici', methods=['GET'])
def get_dati_pubblici():
    """Ritorna solo le attività, avvisi e calendari contrassegnati come 'pubblicati' per la homepage."""
    imp = get_or_create_impostazioni()

    attivita = Attivita.query.filter_by(is_attiva=True, is_pubblicato=True).order_by(Attivita.id.desc()).all()
    avvisi = NotiziaEvento.query.filter_by(is_pubblicato=True).order_by(NotiziaEvento.id.desc()).all()
    calendari = CalendarioComunita.query.filter_by(is_pubblico=True).order_by(CalendarioComunita.ordine.asc(), CalendarioComunita.id.asc()).all()

    return jsonify({
        'impostazioni': imp.to_dict(),
        'attivita': [a.to_dict() for a in attivita],
        'avvisi': [av.to_dict() for av in avvisi],
        'calendari': [c.to_dict() for c in calendari]
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


# ---------------- GESTIONE CALENDARI GOOGLE COMUNITARI ----------------
@impostazioni_bp.route('/calendari', methods=['GET'])
def get_calendari():
    """Ritorna i calendari google parrocchiali configurati."""
    solo_pubblici = request.args.get('solo_pubblici', 'false').lower() in ['true', '1']
    query = CalendarioComunita.query
    if solo_pubblici:
        query = query.filter_by(is_pubblico=True)
    calendari = query.order_by(CalendarioComunita.ordine.asc(), CalendarioComunita.id.asc()).all()
    return jsonify({
        'total': len(calendari),
        'calendari': [c.to_dict() for c in calendari]
    })

@impostazioni_bp.route('/calendari', methods=['POST'])
def create_calendario():
    data = request.get_json() or {}
    titolo = data.get('titolo', '').strip()
    url = data.get('google_calendar_url', '').strip()
    if not titolo or not url:
        return jsonify({'error': 'Titolo e Link Google Calendar sono obbligatori'}), 400

    cal = CalendarioComunita(
        titolo=titolo,
        descrizione=data.get('descrizione', '').strip(),
        google_calendar_url=url,
        colore=data.get('colore', '#8B1E1E').strip() or '#8B1E1E',
        icona=data.get('icona', '📅').strip() or '📅',
        categoria=data.get('categoria', 'parrocchia').strip() or 'parrocchia',
        is_pubblico=bool(data.get('is_pubblico', True)),
        ordine=int(data.get('ordine', 0) or 0)
    )
    db.session.add(cal)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Calendario "{cal.titolo}" aggiunto con successo!',
        'calendario': cal.to_dict()
    }), 201

@impostazioni_bp.route('/calendari/<int:id>', methods=['PUT'])
def update_calendario(id):
    cal = db.session.get(CalendarioComunita, id)
    if not cal:
        return jsonify({'error': 'Calendario non trovato'}), 404

    data = request.get_json() or {}
    if 'titolo' in data: cal.titolo = data['titolo'].strip()
    if 'descrizione' in data: cal.descrizione = data['descrizione'].strip()
    if 'google_calendar_url' in data: cal.google_calendar_url = data['google_calendar_url'].strip()
    if 'colore' in data: cal.colore = data['colore'].strip() or '#8B1E1E'
    if 'icona' in data: cal.icona = data['icona'].strip() or '📅'
    if 'categoria' in data: cal.categoria = data['categoria'].strip() or 'parrocchia'
    if 'is_pubblico' in data: cal.is_pubblico = bool(data['is_pubblico'])
    if 'ordine' in data: cal.ordine = int(data['ordine'] or 0)

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Calendario "{cal.titolo}" aggiornato con successo!',
        'calendario': cal.to_dict()
    })

@impostazioni_bp.route('/calendari/<int:id>', methods=['DELETE'])
def delete_calendario(id):
    cal = db.session.get(CalendarioComunita, id)
    if not cal:
        return jsonify({'error': 'Calendario non trovato'}), 404

    db.session.delete(cal)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Calendario eliminato con successo'})

