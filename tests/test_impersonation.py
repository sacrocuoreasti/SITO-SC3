import unittest
import test_alpha_family as fixture
from models import db, Utente


class ImpersonationTests(unittest.TestCase):
    login = fixture.AlphaFamilyTests.login
    tearDown = fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        self.login('admin@example.test')

    def start(self, target=1):
        return self.client.post('/api/utenti/%s/impersona' % target, json={})

    def stop(self):
        return self.client.post('/api/auth/impersonazione/fine', json={})

    def test_only_admin_can_start_and_users_cannot_restore_an_admin_session(self):
        self.client.post('/api/auth/logout')
        self.assertEqual(self.start().status_code, 401)
        self.assertEqual(self.stop().status_code, 401)
        for role in ('utente', 'segreteria'):
            with self.app.app_context():
                db.session.get(Utente, 1).ruolo = role
                db.session.commit()
            self.login()
            self.assertEqual(self.start(2).status_code, 403)
            self.assertEqual(self.stop().status_code, 401)

    def test_preview_uses_target_permissions_and_keeps_account_data_unchanged(self):
        with self.app.app_context():
            target = db.session.get(Utente, 1)
            before = (target.password_hash, target.ruolo, target.privilegi_extra, target.last_login)
        response = self.start()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['impersonazione']['sola_lettura'])
        self.assertTrue(any('remember_token=;' in cookie for cookie in response.headers.getlist('Set-Cookie')))
        for _ in range(2):
            me = self.client.get('/api/auth/me').json
            self.assertEqual(me['user']['id'], 1)
            self.assertFalse(me['user']['is_admin'])
            self.assertTrue(me['impersonazione']['attiva'])
        self.assertEqual(self.client.get('/api/famiglie/mia').json['nucleo']['id'], self.family_id)
        self.assertEqual(self.client.get('/api/utenti').status_code, 403)
        self.assertEqual(self.client.get('/api/accessi').status_code, 403)
        with self.app.app_context():
            target = db.session.get(Utente, 1)
            self.assertEqual((target.password_hash, target.ruolo, target.privilegi_extra, target.last_login), before)
        self.assertEqual(self.stop().status_code, 200)
        me = self.client.get('/api/auth/me').json
        self.assertEqual(me['user']['id'], 3)
        self.assertTrue(me['user']['is_admin'])
        self.assertIsNone(me['impersonazione'])

    def test_all_mutations_and_nested_preview_are_blocked(self):
        self.assertEqual(self.start().status_code, 200)
        for path in ('/api/utenti/2/impersona', '/api/auth/login', '/api/auth/register',
                     '/api/iscrizioni', '/api/backup/prepare-release', '/api/accessi'):
            self.assertEqual(self.client.post(path, json={}).status_code, 403, path)
        self.assertEqual(self.client.put('/api/persone/'+self.head_cf, json={'nome':'Changed'}).status_code, 403)
        self.assertEqual(self.client.delete('/api/utenti/2').status_code, 403)
        self.assertEqual(self.client.get('/api/auth/me').json['user']['id'], 1)
        self.assertEqual(self.stop().status_code, 200)

    def test_missing_self_and_inactive_targets_leave_admin_session_intact(self):
        with self.app.app_context():
            db.session.get(Utente, 2).is_attivo = False
            db.session.commit()
        for target, status in ((99999,404), (3,400), (2,400)):
            self.assertEqual(self.start(target).status_code, status)
            self.assertEqual(self.client.get('/api/auth/me').json['user']['id'], 3)

    def test_return_is_available_after_target_is_disabled_or_deleted(self):
        for deleted in (False, True):
            self.assertEqual(self.start(2).status_code, 200)
            with self.app.app_context():
                target = db.session.get(Utente, 2)
                if deleted:
                    db.session.delete(target)
                else:
                    target.is_attivo = False
                db.session.commit()
            me = self.client.get('/api/auth/me').json
            self.assertFalse(me['authenticated'])
            self.assertTrue(me['impersonazione']['attiva'])
            self.assertEqual(self.stop().status_code, 200)
            self.assertEqual(self.client.get('/api/auth/me').json['user']['id'], 3)
            if not deleted:
                with self.app.app_context():
                    db.session.get(Utente, 2).is_attivo = True
                    db.session.commit()

    def test_revoked_original_admin_cannot_keep_or_restore_preview(self):
        self.assertEqual(self.start().status_code, 200)
        with self.app.app_context():
            db.session.get(Utente, 3).ruolo = 'utente'
            db.session.commit()
        self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
        self.assertEqual(self.stop().status_code, 401)
        self.assertFalse(self.client.get('/api/auth/me').json['authenticated'])

    def test_logout_discards_the_admin_return_context(self):
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 200)
        self.assertFalse(self.client.get('/api/auth/me').json['authenticated'])
        self.assertEqual(self.stop().status_code, 401)
