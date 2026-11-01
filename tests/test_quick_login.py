import os
import unittest
from unittest.mock import patch
import test_stability as stability_tests
from models import db, Utente


class QuickLoginTests(unittest.TestCase):
    tearDown = stability_tests.StabilityTests.tearDown

    def setUp(self):
        stability_tests.StabilityTests.setUp(self)
        self.app.config['PUBLIC_QUICK_LOGIN'] = True
        with self.app.app_context():
            admin = Utente.query.filter_by(email='admin@example.test').one()
            admin.email = 'admin@sacrocuoreasti.com'
            user = Utente.query.filter_by(email='user@example.test').one()
            user.email = 'imparato.sacrocuore@gmail.com'
            self.original = {u.id:(u.password_hash,u.ruolo,u.privilegi_extra) for u in [admin,user]}
            db.session.commit()

    def test_public_aliases_open_exact_existing_accounts(self):
        with patch.dict(os.environ, {'RENDER':'true'}, clear=True):
            for alias,email,role in [(' A ','admin@sacrocuoreasti.com','admin'),('u','imparato.sacrocuore@gmail.com','utente')]:
                response=self.client.post('/api/auth/login',json={'email':alias,'password':''},environ_base={'REMOTE_ADDR':'203.0.113.1'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['user']['email'],email)
                self.assertEqual(response.json['user']['ruolo'],role)
                self.assertEqual(self.client.get('/api/auth/me').json['user']['email'],email)
        with self.app.app_context():
            self.assertEqual(Utente.query.count(),2)
            self.assertEqual({u.id:(u.password_hash,u.ruolo,u.privilegi_extra) for u in Utente.query.all()},self.original)

    def test_user_alias_does_not_gain_admin_privileges(self):
        self.client.post('/api/auth/login',json={'email':'a','password':''})
        self.assertEqual(self.client.get('/api/utenti').status_code,200)
        self.client.post('/api/auth/login',json={'email':'u','password':''})
        self.assertEqual(self.client.get('/api/utenti').status_code,403)

    def test_missing_and_disabled_accounts_are_not_created_or_reactivated(self):
        with self.app.app_context():
            user=Utente.query.filter_by(email='imparato.sacrocuore@gmail.com').one()
            user.is_attivo=False
            db.session.commit()
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'u','password':''}).status_code,403)
        with self.app.app_context():
            db.session.delete(Utente.query.filter_by(email='imparato.sacrocuore@gmail.com').one())
            db.session.commit()
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'u','password':''}).status_code,404)
        with self.app.app_context():self.assertEqual(Utente.query.count(),1)

    def test_normal_credentials_still_require_the_existing_password(self):
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'a','password':'wrong'}).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'other','password':''}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'admin@sacrocuoreasti.com','password':''}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'admin@sacrocuoreasti.com','password':'test-password-123'}).status_code,200)

    def test_shortcut_can_be_disabled_and_ui_matches_setting(self):
        self.assertIn(b'data-quick-login="true"',self.client.get('/').data)
        self.app.config['PUBLIC_QUICK_LOGIN']=False
        with patch.dict(os.environ, {'RENDER':'true','LOCAL_QUICK_LOGIN':'1'}, clear=True):
            self.assertEqual(self.client.post('/api/auth/login',json={'email':'a','password':''}).status_code,400)
            self.assertEqual(self.client.post('/api/auth/login',json={'email':'u','password':''}).status_code,400)
            self.assertIn(b'data-quick-login="false"',self.client.get('/').data)

    def test_switching_alias_clears_previous_remember_cookie(self):
        self.client.post('/api/auth/login',json={'email':'admin@sacrocuoreasti.com','password':'test-password-123'})
        self.assertIsNotNone(self.client.get_cookie('remember_token'))
        self.client.post('/api/auth/login',json={'email':'u','password':''})
        self.assertIsNone(self.client.get_cookie('remember_token'))
        self.assertEqual(self.client.get('/api/auth/me').json['user']['email'],'imparato.sacrocuore@gmail.com')
