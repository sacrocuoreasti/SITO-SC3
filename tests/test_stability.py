import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError, OperationalError

from app import create_app
from config import Config
from models import db, Utente, GruppoOratorio, Attivita


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = 'test-only-key'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(self.directory.name, 'test.db')
            SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 1}}
            UPLOAD_FOLDER = os.path.join(self.directory.name, 'uploads')
            SESSION_COOKIE_SECURE = False
            REMEMBER_COOKIE_SECURE = False

        self.config = TestConfig
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = Utente(email='admin@example.test', ruolo='admin', is_attivo=True)
            user.set_password('test-password-123')
            db.session.add(user)
            user = Utente(email='user@example.test', ruolo='utente', is_attivo=True)
            user.set_password('test-password-123')
            db.session.add(user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.directory.cleanup()

    def login(self, email='admin@example.test'):
        response = self.client.post('/api/auth/login', json={'email': email, 'password': 'test-password-123'})
        self.assertEqual(response.status_code, 200)

    def test_public_home_and_read_apis(self):
        for path in ['/', '/health', '/api/auth/me', '/api/impostazioni/dati-pubblici',
                     '/api/attivita', '/api/celebrazioni', '/api/configurazioni/campi-account']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get('/health').headers['Cache-Control'], 'no-store')

    def test_anonymous_cannot_read_private_data_or_write_settings(self):
        for path in ['/api/persone', '/api/utenti', '/api/famiglie', '/api/iscrizioni']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.put('/api/impostazioni/homepage', json={}).status_code, 401)

    def test_regular_user_cannot_manage_users_or_settings(self):
        self.login('user@example.test')
        self.assertEqual(self.client.get('/api/utenti').status_code, 403)
        self.assertEqual(self.client.put('/api/impostazioni/homepage', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/attivita', json={}).status_code, 403)

    def test_admin_can_manage_settings(self):
        self.login()
        response = self.client.put('/api/impostazioni/homepage', json={'titolo_hero': 'Prova'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/utenti').status_code, 200)

    def test_invalid_json_and_missing_resources_are_json(self):
        for payload in [[], 'invalid', None, 123]:
            response = self.client.post('/api/auth/login', data=__import__('json').dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response.is_json)
        for path in ['/api/does-not-exist', '/static/does-not-exist.js']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/api/auth/login').status_code, 405)

    def test_oversized_upload_is_json(self):
        self.login()
        self.app.config['MAX_CONTENT_LENGTH'] = 10
        response = self.client.post('/api/persone', data='x' * 20, content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.is_json)

    def test_invalid_or_disabled_session_is_anonymous(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = 'invalid'
        self.assertFalse(self.client.get('/api/auth/me').json['authenticated'])
        self.login()
        with self.app.app_context():
            Utente.query.filter_by(email='admin@example.test').first().is_attivo = False
            db.session.commit()
        self.assertFalse(self.client.get('/api/auth/me').json['authenticated'])

    def test_restart_preserves_password_account_state_and_closed_groups(self):
        with self.app.app_context():
            user = Utente.query.filter_by(email='admin@example.test').first()
            user.set_password('changed-password-123')
            user.is_attivo = False
            for group in GruppoOratorio.query.all():
                group.stato = 'chiuso'
            db.session.commit()
            db.session.remove()
            db.engine.dispose()
        app = create_app(self.config)
        with app.app_context():
            user = Utente.query.filter_by(email='admin@example.test').first()
            self.assertTrue(user.check_password('changed-password-123'))
            self.assertFalse(user.is_attivo)
            self.assertTrue(all(g.stato == 'chiuso' for g in GruppoOratorio.query.all()))
            self.assertEqual(db.session.execute(db.text('PRAGMA journal_mode')).scalar(), 'wal')
            db.session.remove()
            db.engine.dispose()

    def test_database_failure_marks_health_unavailable_then_recovers(self):
        with patch.object(db.session, 'execute', side_effect=OperationalError('select', {}, Exception('unavailable'))):
            response = self.client.get('/health')
            self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get('/health').status_code, 200)

    def test_database_handlers_rollback_and_allow_next_request(self):
        self.login()
        with patch.object(db.session, 'commit', side_effect=IntegrityError('insert', {}, Exception('duplicate'))):
            response = self.client.put('/api/impostazioni/homepage', json={'titolo_hero': 'Conflitto'})
            self.assertEqual(response.status_code, 409)
        with patch.object(db.session, 'commit', side_effect=OperationalError('update', {}, Exception('locked'))):
            response = self.client.put('/api/impostazioni/homepage', json={'titolo_hero': 'Occupato'})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers['Retry-After'], '5')
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertNotEqual(self.client.get('/api/impostazioni/homepage').json['impostazioni']['titolo_hero'], 'Occupato')

    def test_parallel_public_requests(self):
        def request_page(_):
            with self.app.test_client() as client:
                return client.get('/api/impostazioni/dati-pubblici').status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(request_page, range(20))), [200] * 20)

    def test_activity_detail_hides_drafts_and_members(self):
        with self.app.app_context():
            activity = Attivita(titolo='Prova', categoria='oratorio', is_pubblicato=True, is_attiva=True)
            db.session.add(activity)
            db.session.commit()
            activity_id = activity.id
        response = self.client.get('/api/attivita/' + str(activity_id))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('iscritti', response.json['attivita'])
        with self.app.app_context():
            db.session.get(Attivita, activity_id).is_pubblicato = False
            db.session.commit()
        self.assertEqual(self.client.get('/api/attivita/' + str(activity_id)).status_code, 404)

    def test_first_public_registration_cannot_become_admin(self):
        with self.app.app_context():
            Utente.query.delete()
            db.session.commit()
        with patch('routes.auth.valida_cf', return_value=True), patch('routes.auth.estrai_dati_cf', return_value={}):
            response = self.client.post('/api/auth/register', json={
                'email': 'first@example.test', 'password': 'test-password-123',
                'nome': 'Persona', 'cognome': 'Test', 'codice_fiscale': 'RSSMRA80A01H501U',
                'ruolo': 'admin', 'privilegi': ['admin'], 'consensi_registrazione': {'privacy': True, 'foto_video': True},
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['user']['ruolo'], 'utente')
        self.assertEqual(self.client.get('/api/utenti').status_code, 403)

    def test_mail_failure_does_not_report_success_or_leave_usable_token(self):
        from models import PasswordResetToken
        with patch('services.email_service.invia_codice_recupero_password', return_value=(False, 'offline')):
            response = self.client.post('/api/auth/recupera-password/richiedi', json={'email': 'admin@example.test'})
        self.assertEqual(response.status_code, 503)
        with self.app.app_context():
            self.assertEqual(PasswordResetToken.query.filter_by(is_used=False).count(), 0)

    def test_no_default_accounts_created_at_restart(self):
        app = create_app(self.config)
        with app.app_context():
            self.assertEqual(Utente.query.count(), 2)
            db.session.remove()
            db.engine.dispose()

    def test_compression_reduces_public_assets_and_preserves_payload(self):
        import gzip
        for path in ['/', '/static/js/app.js?v=test', '/static/css/style.css?v=test']:
            plain = self.client.get(path)
            compressed = self.client.get(path, headers={'Accept-Encoding': 'gzip'})
            self.assertEqual(compressed.headers.get('Content-Encoding'), 'gzip')
            self.assertEqual(gzip.decompress(compressed.data), plain.data)
            self.assertLess(len(compressed.data), len(plain.data) * 0.35)
            self.assertIn('Accept-Encoding', compressed.headers['Vary'])
        self.assertNotIn('Content-Encoding', self.client.get('/api/auth/me', headers={'Accept-Encoding': 'gzip'}).headers)
        self.assertNotIn('Content-Encoding', self.client.get('/', headers={'Accept-Encoding': 'gzip;q=0'}).headers)

    def test_homepage_has_no_external_render_blockers(self):
        html = self.client.get('/').data.decode()
        self.assertNotIn('fonts.googleapis.com', html)
        iframe = html.split('id="publicGoogleCalendarIframe"', 1)[1].split('</iframe>', 1)[0]
        self.assertNotIn('src=', iframe)
        self.assertIn('Mostra il calendario', html)
        self.assertIn('defer></script>', html)
        data = self.client.get('/api/impostazioni/dati-pubblici').json
        self.assertIsInstance(data['calendari'], list)
        self.assertIsInstance(data['celebrazioni'], list)

    def test_email_diagnostic_requires_staff_and_exposes_no_secret(self):
        self.assertEqual(self.client.get('/api/utenti/email-status').status_code, 401)
        self.login('user@example.test')
        self.assertEqual(self.client.get('/api/utenti/email-status').status_code, 403)
        self.login()
        with patch.dict(os.environ, {'GOOGLE_SCRIPT_URL': 'https://script.google.com/macros/s/test/exec', 'GOOGLE_SCRIPT_SECRET': 'test-private-key' * 4}, clear=True):
            response = self.client.get('/api/utenti/email-status')
            self.assertTrue(response.json['configured'])
            self.assertNotIn('test-private-key', response.data.decode())

    def test_quick_login_is_local_opt_in_and_always_disabled_on_render(self):
        with self.app.app_context():
            user = Utente.query.filter_by(email='admin@example.test').first()
            user.email = 'admin@sacrocuoreasti.com'
            db.session.commit()
        payload = {'email': 'a', 'password': ''}
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.client.post('/api/auth/login', json=payload).status_code, 400)
        with patch.dict(os.environ, {'LOCAL_QUICK_LOGIN': '1', 'RENDER': 'true'}, clear=True):
            self.assertEqual(self.client.post('/api/auth/login', json=payload).status_code, 400)
        with patch.dict(os.environ, {'LOCAL_QUICK_LOGIN': '1'}, clear=True):
            self.assertEqual(self.client.post('/api/auth/login', json=payload, environ_base={'REMOTE_ADDR': '192.0.2.1'}, headers={'X-Forwarded-For': '127.0.0.1'}).status_code, 400)
            self.assertEqual(self.client.post('/api/auth/login', json=payload).status_code, 200)


if __name__ == '__main__':
    unittest.main()
