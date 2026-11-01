"""Documenti personali conservati negli upload privati e inclusi nei backup."""
import os
import uuid
from datetime import datetime
from pathlib import Path
from flask import current_app
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
from models import db, DocumentoPersona

DOCUMENT_TYPES = {'identita':'Carta d’identità', 'battesimo':'Certificato di battesimo', 'comunione':'Certificato di comunione', 'cresima':'Certificato di cresima', 'matrimonio':'Certificato di matrimonio'}
IDENTITY_FIELDS = ('numero_documento', 'rilasciato_da', 'data_rilascio', 'data_scadenza')


def prepare_documents(files, data):
    drafts = []
    for kind in DOCUMENT_TYPES:
        file = files.get('documento_' + kind)
        if not file or not file.filename:
            continue
        original = secure_filename(file.filename)
        extension = Path(original).suffix.lower()
        content = file.read(5 * 1024 * 1024 + 1)
        signatures = {'.pdf':content.startswith(b'%PDF-'), '.png':content.startswith(b'\x89PNG\r\n\x1a\n'),
                      '.jpg':content.startswith(b'\xff\xd8\xff'), '.jpeg':content.startswith(b'\xff\xd8\xff'),
                      '.webp':content.startswith(b'RIFF') and content[8:12] == b'WEBP'}
        if not content or len(content) > 5 * 1024 * 1024 or not signatures.get(extension, False):
            raise BadRequest('Carica documenti PDF, JPG, PNG o WebP validi, fino a 5 MB ciascuno (16 MB totali).')
        draft = {'tipo':kind, 'nome_originale':original, 'content':content, 'extension':extension}
        if kind == 'identita':
            metadata = {key:str(data.get('documento_' + key, '')).strip() for key in IDENTITY_FIELDS}
            if not all(metadata.values()) or len(metadata['numero_documento']) > 100 or len(metadata['rilasciato_da']) > 200:
                raise BadRequest('Per la carta d’identità compila numero, ente di rilascio ed entrambe le date.')
            for key in ('data_rilascio','data_scadenza'):
                try:
                    metadata[key] = datetime.strptime(metadata[key], '%Y-%m-%d').date()
                except ValueError:
                    raise BadRequest('Data del documento non valida')
            if metadata['data_scadenza'] < metadata['data_rilascio']:
                raise BadRequest('La scadenza non può precedere la data di rilascio')
            draft.update(metadata)
        drafts.append(draft)
    if any(data.get('documento_' + key) for key in IDENTITY_FIELDS) and not any(d['tipo']=='identita' for d in drafts):
        raise BadRequest('Carica anche il file della carta d’identità')
    return drafts


def save_documents(person, drafts):
    records = []
    try:
        for draft in drafts:
            relative = 'private/' + uuid.uuid4().hex + draft['extension']
            path = Path(current_app.config['UPLOAD_FOLDER']) / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(draft['content'])
            record = DocumentoPersona(codice_fiscale=person.codice_fiscale, tipo=draft['tipo'],
                                      nome_originale=draft['nome_originale'], percorso=relative,
                                      **{key:draft.get(key) for key in IDENTITY_FIELDS})
            records.append(record)
            db.session.add(record)
        db.session.flush()
        return records
    except Exception:
        remove_document_files(records)
        raise


def remove_document_files(records):
    for record in records:
        (Path(current_app.config['UPLOAD_FOLDER']) / record.percorso).unlink(missing_ok=True)
