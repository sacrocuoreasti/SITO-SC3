import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.abspath(os.environ.get('DATA_DIR', BASE_DIR))
DATABASE_URL = os.environ.get('DATABASE_URL') or f"sqlite:///{os.path.join(DATA_DIR, 'database', 'sacro_cuore.db')}"
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)


class Config:
    PUBLIC_QUICK_LOGIN = os.environ.get('PUBLIC_QUICK_LOGIN', '1') == '1'
    # In produzione impostare una chiave stabile, condivisa tra riavvii.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    if DATABASE_URL.startswith('sqlite:'):
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {
            'timeout': 30, 'check_same_thread': False
        }
    UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', os.path.join(DATA_DIR, 'uploads')))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    TEMPLATE_EXCEL_PATH = os.path.join(BASE_DIR, 'template_anagrafica_sacro_cuore.xlsx')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('RENDER') == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = 86400 * 7
