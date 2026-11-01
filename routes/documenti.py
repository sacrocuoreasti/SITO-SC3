from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import current_user
from models import db, Persona, DocumentoPersona
from services.cf_validator import normalizza_cf
from services.family_service import staff_user, can_manage_family
from services.documents_service import prepare_documents, save_documents, remove_document_files

documenti_bp = Blueprint('documenti_bp', __name__, url_prefix='/api')


def can_access(person):
    return current_user.is_authenticated and (staff_user() or current_user.codice_fiscale == person.codice_fiscale or (person.nucleo and can_manage_family(person.nucleo)))


@documenti_bp.route('/persone/<cf>/documenti', methods=['POST'])
def upload_documents(cf):
    person = db.session.get(Persona, normalizza_cf(cf))
    if not person:
        return jsonify(error='Persona non trovata'),404
    if not can_access(person):
        return jsonify(error='Non autorizzato a gestire questi documenti'),403
    drafts = prepare_documents(request.files, request.form)
    if not drafts:
        return jsonify(error='Seleziona almeno un documento'),400
    records = save_documents(person,drafts)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        remove_document_files(records)
        raise
    return jsonify(success=True,documenti=[record.to_dict() for record in records]),201


@documenti_bp.route('/documenti/<int:id>/download', methods=['GET'])
def download_document(id):
    record = db.session.get(DocumentoPersona,id)
    if not record or not can_access(record.persona):
        return jsonify(error='Documento non disponibile'),404
    response = send_from_directory(current_app.config['UPLOAD_FOLDER'], record.percorso,
                                   as_attachment=True, download_name=record.nome_originale)
    response.headers['Cache-Control']='private, no-store'
    return response
