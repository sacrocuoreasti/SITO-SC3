import json
import unittest
import test_alpha_family as fixture
from models import db,DefinizioneAccesso
from services.access_control import DEFAULTS,subtree


class AccessViewUpgradeTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        self.login('admin@example.test')

    def old_profile(self,key,grants):
        encoded=json.dumps(sorted(grants))
        with self.app.app_context():
            db.session.add(DefinizioneAccesso(chiave=key,nome='Profilo esistente',tipo=DEFAULTS[key][1],permessi=encoded,versione_viste=0));db.session.commit()
        return encoded

    def test_old_user_profile_gets_only_new_views_without_rewriting_saved_choices(self):
        old=set(DEFAULTS['utente'][2])-subtree('giovani')-{'dashboard.bacheche','famiglia.salute','catechismo.calendario'}
        old={value for value in old if not value.endswith(('.bacheca','.avvisi'))}
        encoded=self.old_profile('utente',old)
        self.login();permissions=self.client.get('/api/auth/me').json['user']['permessi']
        for value in ('giovani','giovani.bacheca','dashboard.bacheche','catechismo.bacheca'):self.assertIn(value,permissions)
        for value in ('famiglia.salute','catechismo.calendario','giovani.staff','catechismo.avvisi'):self.assertNotIn(value,permissions)
        with self.app.app_context():
            row=db.session.get(DefinizioneAccesso,'utente');self.assertEqual(row.permessi,encoded);self.assertEqual(row.versione_viste,0)
        self.login('admin@example.test')
        self.assertEqual(self.client.put('/api/accessi/utente',json={'permessi':sorted(old)}).status_code,200)
        self.login();permissions=self.client.get('/api/auth/me').json['user']['permessi']
        self.assertNotIn('giovani',permissions);self.assertNotIn('dashboard.bacheche',permissions)

    def test_old_staff_gains_group_notice_controls_without_new_management_powers(self):
        old=set(DEFAULTS['catechista'][2])-{'catechismo.bacheca','catechismo.avvisi','dashboard.bacheche'}
        self.old_profile('catechista',old)
        data=self.client.get('/api/accessi').json['profili']
        grants=next(row['permessi'] for row in data if row['chiave']=='catechista')
        self.assertIn('catechismo.bacheca',grants);self.assertIn('catechismo.avvisi',grants)
        self.assertNotIn('catechismo.tutti',grants);self.assertNotIn('catechismo.gestione',grants)

    def test_previously_empty_role_stays_empty(self):
        self.old_profile('utente',set())
        self.login();self.assertEqual(self.client.get('/api/auth/me').json['user']['permessi'],[])

    def test_profile_already_containing_new_view_choices_is_not_expanded(self):
        old={'dashboard','catechismo','catechismo.bacheca'}
        self.old_profile('utente',old)
        self.login()
        self.assertEqual(set(self.client.get('/api/auth/me').json['user']['permessi']),old)

    def test_schema_upgrade_preserves_existing_profile_rows_and_creates_backup(self):
        import sqlite3
        from app import create_app
        old={'dashboard','dashboard.attivita','catechismo','catechismo.storico'}
        encoded=self.old_profile('utente',old)
        with self.app.app_context():
            db.session.remove();db.engine.dispose()
        with sqlite3.connect(str(self.directory/'test.db')) as connection:
            connection.executescript('ALTER TABLE definizione_accesso RENAME TO old_access; CREATE TABLE definizione_accesso (chiave VARCHAR(30) PRIMARY KEY,nome VARCHAR(100) NOT NULL,tipo VARCHAR(20) NOT NULL,permessi TEXT NOT NULL); INSERT INTO definizione_accesso SELECT chiave,nome,tipo,permessi FROM old_access; DROP TABLE old_access;')
        self.app=create_app(self.config);self.client=self.app.test_client()
        with self.app.app_context():
            row=db.session.get(DefinizioneAccesso,'utente')
            self.assertEqual(row.permessi,encoded);self.assertEqual(row.versione_viste,0)
        self.assertTrue(list((self.directory/'backups').glob('*.sqlite3')))
        self.login()
        self.assertIn('giovani',self.client.get('/api/auth/me').json['user']['permessi'])
