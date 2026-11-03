"""Salvataggio atomico della scheda e dei suoi nuovi allegati."""
import json
import os
import uuid
from pathlib import Path
from flask import request, current_app
from werkzeug.exceptions import BadRequest
from models import db
from services.documents_service import prepare_documents, save_documents, remove_document_files


def profile_payload():
    try:
        data=request.get_json() if request.is_json else json.loads(request.form.get('data','{}'))
    except (ValueError,TypeError):
        raise BadRequest('Dati anagrafici non validi')
    if not isinstance(data,dict): raise BadRequest('Dati anagrafici non validi')
    from services.access_control import restrict_profile_data
    return restrict_profile_data(data)


def commit_profile(person,data):
    from services.access_control import can,is_admin,profile_prefix
    from werkzeug.exceptions import Forbidden
    if not is_admin() and not can(profile_prefix()+'.documenti') and any(key.startswith('documento_') and value.filename for key,value in request.files.items()):
        raise Forbidden('Caricamento documenti disattivato per questo profilo')
    drafts=prepare_documents(request.files,data)
    photo=request.files.get('foto')
    photo_bytes=None
    suffix=''
    if photo and photo.filename:
        suffix=Path(photo.filename).suffix.lower()
        photo_bytes=photo.read(3*1024*1024+1)
        valid=(suffix in ('.jpg','.jpeg') and photo_bytes.startswith(b'\xff\xd8\xff')) or (suffix=='.png' and photo_bytes.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix=='.webp' and photo_bytes.startswith(b'RIFF') and photo_bytes[8:12]==b'WEBP')
        if not valid or len(photo_bytes)>3*1024*1024:
            raise BadRequest('La foto deve essere JPG, PNG o WebP, fino a 3 MB')
    records=save_documents(person,drafts)
    path=None
    try:
        if photo_bytes:
            name='foto_'+uuid.uuid4().hex+suffix
            path=Path(current_app.config['UPLOAD_FOLDER'])/name
            with path.open('xb') as output: output.write(photo_bytes)
            os.chmod(path,0o600)
            person.foto_profilo_url='/uploads/'+name
        db.session.commit()
    except Exception:
        db.session.rollback()
        remove_document_files(records)
        if path: path.unlink(missing_ok=True)
        raise
