import os
import io
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']
DEFAULT_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '1Lh28l0YAWOXLn3uMBimBP5e_3XyIokVl')

def get_drive_service():
    """
    Inizializza e restituisce il client autenticato per Google Drive API v3.
    Cerca le credenziali in:
    1. Variabile d'ambiente GOOGLE_CREDENTIALS_JSON (stringa JSON della chiave)
    2. File indicato in GOOGLE_APPLICATION_CREDENTIALS
    3. File 'google_credentials.json' o 'service_account.json' nella root del progetto
    """
    creds = None
    
    # 1. Variabile d'ambiente con JSON raw (ideale per Render.com)
    json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if json_str:
        try:
            info = json.loads(json_str)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Errore parsing GOOGLE_CREDENTIALS_JSON: {e}")

    # 2. File da GOOGLE_APPLICATION_CREDENTIALS
    env_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if env_file and os.path.exists(env_file):
        try:
            creds = service_account.Credentials.from_service_account_file(env_file, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Errore caricamento credenziali da {env_file}: {e}")

    # 3. File locali standard
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for filename in ['google_credentials.json', 'service_account.json', 'credentials.json']:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                creds = service_account.Credentials.from_service_account_file(filepath, scopes=SCOPES)
                return build('drive', 'v3', credentials=creds)
            except Exception as e:
                logger.error(f"Errore caricamento credenziali da {filepath}: {e}")

    return None

def is_google_drive_configured():
    """Verifica se il servizio Google Drive è pronto all'uso"""
    service = get_drive_service()
    return service is not None

def upload_file_to_drive(file_storage_or_bytes, filename, mimetype='application/octet-stream', folder_id=None, make_public=True):
    """
    Carica un file su Google Drive nella cartella specificata.
    Rende il file visualizzabile tramite link se make_public=True.
    
    Returns:
        dict: {
            'success': True/False,
            'file_id': '...',
            'url': 'https://drive.google.com/file/d/.../view',
            'view_url': '...',
            'direct_url': 'https://lh3.googleusercontent.com/d/...',
            'download_url': '...'
        }
    """
    service = get_drive_service()
    target_folder = folder_id or DEFAULT_FOLDER_ID

    if not service:
        logger.warning("Google Drive non configurato: credenziali mancanti. Fallback su storage locale.")
        return {'success': False, 'error': 'Credenziali Google Drive non configurate'}

    try:
        # Se è un FileStorage di Flask o ha il metodo read()
        if hasattr(file_storage_or_bytes, 'read'):
            file_storage_or_bytes.seek(0)
            file_bytes = file_storage_or_bytes.read()
            media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=True)
        else:
            media = MediaIoBaseUpload(io.BytesIO(file_storage_or_bytes), mimetype=mimetype, resumable=True)

        file_metadata = {
            'name': filename,
            'parents': [target_folder] if target_folder else []
        }

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink, thumbnailLink'
        ).execute()

        file_id = uploaded_file.get('id')

        # Rendi il file accessibile in sola lettura a chi ha il link
        if make_public and file_id:
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'},
                    fields='id'
                ).execute()
            except Exception as pe:
                logger.warning(f"Impostazione permessi pubblici per file {file_id}: {pe}")

        view_url = uploaded_file.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view"
        direct_url = f"https://lh3.googleusercontent.com/d/{file_id}"

        return {
            'success': True,
            'file_id': file_id,
            'url': view_url,
            'view_url': view_url,
            'direct_url': direct_url,
            'download_url': uploaded_file.get('webContentLink')
        }

    except Exception as e:
        logger.error(f"Errore durante l'upload su Google Drive: {e}")
        return {'success': False, 'error': str(e)}

def delete_file_from_drive(file_id_or_url):
    """Elimina un file da Google Drive dato il suo ID o URL"""
    service = get_drive_service()
    if not service or not file_id_or_url:
        return False

    file_id = file_id_or_url
    if 'drive.google.com' in file_id_or_url:
        import re
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', file_id_or_url)
        if match:
            file_id = match.group(1)

    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception as e:
        logger.error(f"Errore eliminazione file {file_id} da Drive: {e}")
        return False
