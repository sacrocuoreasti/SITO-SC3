import os
from flask import Blueprint, request, jsonify, send_file, current_app
from models import Persona, Attivita
from services.excel_service import (
    genera_template_excel,
    esporta_anagrafica_excel,
    esporta_iscritti_attivita_excel,
    importa_da_excel
)
from werkzeug.utils import secure_filename
from io import BytesIO

excel_bp = Blueprint('excel_bp', __name__, url_prefix='/api/excel')

from flask_login import current_user

def check_staff_excel():
    if current_user.is_authenticated:
        roles = current_user.get_all_roles()
        return any(r in ['admin', 'segreteria', 'parroco'] for r in roles)
    return False

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@excel_bp.route('/template', methods=['GET'])
def download_template():
    """Scarica il file Excel modello per l'importazione parrocchiale."""
    if not check_staff_excel():
        return jsonify({'error': 'Funzionalità riservata alla segreteria parrocchiale'}), 403
    template_stream = genera_template_excel()
    return send_file(
        template_stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='template_anagrafica_sacro_cuore.xlsx'
    )

@excel_bp.route('/import', methods=['POST'])
def import_excel():
    """
    Riceve un file Excel (.xlsx o .xls) o CSV caricato dall'utente ed esegue l'importazione
    con inserimento e aggiornamento (upsert) su Codice Fiscale, creando anagrafiche,
    nuclei familiari e iscrizioni.
    """
    if not check_staff_excel():
        return jsonify({'error': 'Funzionalità riservata alla segreteria parrocchiale'}), 403
    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file caricato'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nessun file selezionato'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Formato non supportato. Carica un file .xlsx, .xls o .csv'}), 400

    try:
        stream = BytesIO(file.read())
        risultati = importa_da_excel(stream)
        return jsonify({
            'success': True,
            'message': 'File Excel elaborato con successo!',
            'dettagli': risultati
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore durante la lettura del file Excel: {str(e)}'
        }), 500

@excel_bp.route('/import-sample', methods=['POST'])
def import_sample():
    """
    Carica ed elabora istantaneamente il file Excel parrocchiale di esempio preconfigurato
    ('template_anagrafica_sacro_cuore.xlsx') nel database.
    """
    if not check_staff_excel():
        return jsonify({'error': 'Funzionalità riservata alla segreteria parrocchiale'}), 403
    sample_path = current_app.config.get('TEMPLATE_EXCEL_PATH')
    if not sample_path or not os.path.exists(sample_path):
        # Genera al volo
        stream = genera_template_excel()
        risultati = importa_da_excel(stream)
    else:
        with open(sample_path, 'rb') as f:
            stream = BytesIO(f.read())
            risultati = importa_da_excel(stream)

    return jsonify({
        'success': True,
        'message': 'Dati parrocchiali importati dall\'Excel modello!',
        'dettagli': risultati
    })

@excel_bp.route('/export-anagrafica', methods=['GET'])
def export_anagrafica():
    """Esporta l'intera anagrafica parrocchiale o i codici fiscali selezionati in formato Excel formattato."""
    if not check_staff_excel():
        return jsonify({'error': 'Funzionalità riservata alla segreteria parrocchiale'}), 403

    cfs_param = request.args.get('cfs', '').strip()
    if cfs_param:
        cf_list = [c.strip().upper() for c in cfs_param.split(',') if c.strip()]
        persone = Persona.query.filter(Persona.codice_fiscale.in_(cf_list)).order_by(Persona.cognome.asc(), Persona.nome.asc()).all()
    else:
        persone = Persona.query.order_by(Persona.cognome.asc(), Persona.nome.asc()).all()

    stream = esporta_anagrafica_excel(persone)
    return send_file(
        stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='anagrafica_sacro_cuore_asti.xlsx'
    )

@excel_bp.route('/export-attivita/<int:id>', methods=['GET'])
def export_attivita(id):
    """Esporta l'elenco iscritti con relative quote e informazioni per una specifica attività."""
    if not check_staff_excel():
        return jsonify({'error': 'Funzionalità riservata alla segreteria parrocchiale'}), 403
    att = Attivita.query.get(id)
    if not att:
        return jsonify({'error': 'Attività non trovata'}), 404

    stream = esporta_iscritti_attivita_excel(att)
    nome_sanitizzato = "".join(c for c in att.titolo if c.isalnum() or c in (' ', '_', '-')).strip()
    return send_file(
        stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'iscritti_{nome_sanitizzato[:30]}.xlsx'
    )
