import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app
from config import Config
from models import db, Persona, Utente, NucleoFamiliare, RichiestaNucleo, Attivita, Iscrizione, ClausolaIscrizione
from services.cf_validator import ODD_VALUES, EVEN_VALUES
from services.backup_service import create_backup, verify_backup


def fiscal_code(prefix):
    return prefix + chr(ord('A') + sum((ODD_VALUES if i % 2 == 0 else EVEN_VALUES)[c] for i, c in enumerate(prefix)) % 26)


class AlphaFamilyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        class TestConfig(Config):
            TESTING = True
            PUBLIC_QUICK_LOGIN = False
            SECRET_KEY = 'test-key'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(self.directory / 'test.db')
            SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 5}}
            UPLOAD_FOLDER = str(self.directory / 'uploads')
            SESSION_COOKIE_SECURE = False
            REMEMBER_COOKIE_SECURE = False
        self.config = TestConfig
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.head_cf = fiscal_code('RSSMRA80A01H501')
        self.child_cf = fiscal_code('RSSLGI14A01H501')
        self.child2_cf = fiscal_code('RSSNNA16A41H501')
        with self.app.app_context():
            head = Persona(codice_fiscale=self.head_cf, nome='Test', cognome='Head', data_nascita=date(1980,1,1), ruolo_famiglia='Figlio/a', indirizzo_residenza='Via di prova 1', comune_residenza='Comune Test', cap_residenza='12345', allergie='Nota sanitaria precedente')
            db.session.add(head)
            db.session.flush()
            family = NucleoFamiliare(nome_famiglia='Famiglia Test', codice_fiscale_capofamiglia=self.head_cf)
            db.session.add(family)
            db.session.flush()
            head.nucleo_id = family.id
            self.family_id = family.id
            self.code = family.codice_invito
            for cf, born in [(self.child_cf, date(2014,1,1)), (self.child2_cf, date(2016,1,1))]:
                db.session.add(Persona(codice_fiscale=cf, nome='Child', cognome='Test', data_nascita=born, ruolo_famiglia='Figlio/a', nucleo_id=family.id))
            for email, cf, role in [('head@example.test', self.head_cf, 'utente'), ('child@example.test', self.child_cf, 'utente'), ('admin@example.test', None, 'admin')]:
                user = Utente(email=email, codice_fiscale=cf, ruolo=role)
                user.set_password('password-test-123')
                db.session.add(user)
            db.session.commit()
            self.clauses = {str(c.id): True for c in ClausolaIscrizione.query.filter_by(is_attiva=True).all()}
        self.login()

    def login(self, email='head@example.test', client=None):
        response = (client or self.client).post('/api/auth/login', json={'email':email, 'password':'password-test-123'})
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temporary.cleanup()

    def registration(self, **extra):
        return dict({'nome':'New', 'cognome':'Test', 'codice_fiscale':fiscal_code('VRDLGI90A01H501'), 'email':'new@example.test', 'password':'password-test-123', 'ruolo_famiglia':'Madre', 'consensi_registrazione':{'privacy':True, 'foto_video':True}}, **extra)

    def test_version_and_family_head_independent_of_role(self):
        self.assertIn((Path(__file__).resolve().parents[1]/'VERSION').read_text().strip().encode(), self.client.get('/').data)
        self.assertEqual(self.client.get('/health').json['version'], (Path(__file__).resolve().parents[1]/'VERSION').read_text().strip())
        me = self.client.get('/api/auth/me').json['user']
        self.assertTrue(me['is_capofamiglia'])
        self.assertEqual(me['persona']['ruolo_famiglia'], 'Figlio/a')
        family = self.client.get('/api/famiglie/mia').json
        self.assertTrue(family['puo_gestire'])
        self.assertRegex(family['nucleo']['codice_invito'], r'^[A-Z0-9]{3}$')

    def test_registration_requires_explicit_both_consents(self):
        for flags in [{}, {'privacy':True}, {'privacy':'true', 'foto_video':True}, {'privacy':True, 'foto_video':False}]:
            self.assertEqual(self.client.post('/api/auth/register', json=self.registration(consensi_registrazione=flags)).status_code, 400)
        response = self.client.post('/api/auth/register', json=self.registration())
        self.assertEqual(response.status_code, 201)
        with self.app.app_context():
            user = Utente.query.filter_by(email='new@example.test').one()
            record = json.loads(user.consensi_registrazione)
            self.assertEqual(record['ambito'], 'famiglia')
            self.assertTrue(record['consensi']['foto_video']['accettato'])
            self.assertEqual(user.persona.ruolo_famiglia, 'Madre')

    def test_new_member_inherits_residence_and_gets_managed_login(self):
        cf = fiscal_code('BNCPLA12A01H501')
        response = self.client.post(f'/api/famiglie/{self.family_id}/membri', json={'nome':'New', 'cognome':'Member', 'codice_fiscale':cf, 'email':'member@example.test', 'password':'member-password-123', 'consensi_registrazione':{'privacy':True,'foto_video':True}, 'allergie':'Polline', 'terapie_medicinali':'Terapia descritta dal referente'})
        self.assertEqual(response.status_code, 201, response.json)
        person = response.json['persona']
        self.assertEqual(person['indirizzo_residenza'], 'Via di prova 1')
        self.assertEqual(person['cap_residenza'], '12345')
        self.assertEqual(person['terapie_medicinali'], 'Terapia descritta dal referente')
        self.assertEqual(person['allergie'], 'Polline')
        with self.app.app_context():
            user = Utente.query.filter_by(email='member@example.test').one()
            self.assertTrue(user.gestito_da_id)
            self.assertEqual(user.ruolo, 'utente')
        login = self.app.test_client().post('/api/auth/login', json={'email':'member@example.test','password':'member-password-123'})
        self.assertEqual(login.status_code, 200)

    def test_existing_person_not_moved_or_overwritten(self):
        response = self.client.post(f'/api/famiglie/{self.family_id}/membri', json={'nome':'Changed', 'cognome':'Changed','codice_fiscale':self.child_cf})
        self.assertEqual(response.status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.get(Persona,self.child_cf).nome, 'Child')

    def test_non_head_cannot_manage_other_members_or_accounts(self):
        self.login('child@example.test')
        self.assertEqual(self.client.put('/api/persone/'+self.head_cf, json={'nome':'Changed'}).status_code,403)
        self.assertEqual(self.client.put(f'/api/famiglie/{self.family_id}/membri/{self.head_cf}/account', json={'email':'changed@example.test'}).status_code,403)
        self.assertEqual(self.client.post(f'/api/famiglie/{self.family_id}/membri', json={}).status_code,403)
        self.assertEqual(self.client.put('/api/persone/'+self.child_cf, json={'terapie_medicinali':'Note personali'}).status_code,200)

    def test_head_role_changes_without_changing_responsibility(self):
        response = self.client.put('/api/persone/'+self.head_cf, json={'ruolo_famiglia':'Padre','is_capofamiglia':True,'terapie_medicinali':'Nuova nota'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['persona']['is_capofamiglia'])
        self.assertEqual(response.json['persona']['allergie'],'Nota sanitaria precedente')
        self.assertEqual(response.json['persona']['ruolo_famiglia'],'Padre')

    def test_invitation_waits_for_approval_and_does_not_expose_family(self):
        invited = self.app.test_client()
        result = invited.post('/api/auth/register',json=self.registration(codice_invito=self.code.lower()))
        self.assertEqual(result.status_code,201)
        pending = invited.get('/api/famiglie/mia').json
        self.assertTrue(pending['richiesta_in_attesa'])
        self.assertIsNone(pending['nucleo'])
        self.assertEqual(invited.get('/api/famiglie/'+str(self.family_id)).status_code,403)
        requests = self.client.get('/api/famiglie/mia').json['richieste_ingresso']
        self.assertEqual(len(requests),1)
        approved = self.client.put(f'/api/famiglie/{self.family_id}/richieste/{requests[0]["id"]}',json={'azione':'approva'})
        self.assertEqual(approved.status_code,200)
        self.assertEqual(invited.get('/api/famiglie/mia').json['nucleo']['id'],self.family_id)
        self.assertEqual(self.client.put(f'/api/famiglie/{self.family_id}/richieste/{requests[0]["id"]}',json={'azione':'approva'}).status_code,404)

    def activity(self, capacity=3, fields=None):
        with self.app.app_context():
            activity=Attivita(titolo='Evento Test',categoria='evento',eta_min=6,eta_max=16,posti_massimi=capacity,quota_iscrizione=10,is_attiva=True,is_pubblicato=True)
            if fields: activity.campi_personalizzati=fields
            db.session.add(activity); db.session.commit()
            return activity.id

    def enrollment(self, activity, participants, **extra):
        return self.client.post('/api/iscrizioni',json=dict({'attivita_id':activity,'partecipanti':participants,'clausole_accettate':self.clauses},**extra))

    def test_batch_enrollment_and_individual_event_answers(self):
        activity=self.activity(fields=[{'nome':'Taglia','chiave':'taglia','obbligatorio':True}])
        response=self.enrollment(activity,[self.child_cf,self.child2_cf],campi_personalizzati_per_partecipante={self.child_cf:{'taglia':'M'},self.child2_cf:{'taglia':'S'}})
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(len(response.json['iscrizioni']),2)
        self.assertEqual({r['campi_personalizzati']['taglia'] for r in response.json['iscrizioni']},{'M','S'})

    def test_batch_capacity_failure_rolls_back_every_participant(self):
        response=self.enrollment(self.activity(capacity=1),[self.child_cf,self.child2_cf])
        self.assertEqual(response.status_code,400)
        with self.app.app_context(): self.assertEqual(Iscrizione.query.count(),0)

    def test_batch_age_or_missing_fields_failure_rolls_back(self):
        response=self.enrollment(self.activity(),[self.child_cf,self.head_cf])
        self.assertEqual(response.status_code,400)
        with self.app.app_context(): self.assertEqual(Iscrizione.query.count(),0)
        activity=self.activity(fields=[{'nome':'Taglia','chiave':'taglia','obbligatorio':True}])
        response=self.enrollment(activity,[self.child_cf,self.child2_cf],campi_personalizzati_per_partecipante={self.child_cf:{'taglia':'M'}})
        self.assertEqual(response.status_code,400)
        with self.app.app_context(): self.assertEqual(Iscrizione.query.count(),0)

    def test_member_cannot_enroll_sibling(self):
        self.login('child@example.test')
        response=self.enrollment(self.activity(),[self.child_cf,self.child2_cf])
        self.assertEqual(response.status_code,403)
        with self.app.app_context(): self.assertEqual(Iscrizione.query.count(),0)

    def test_complete_backup_is_private_and_preserves_uploads(self):
        uploads=self.directory/'uploads'; (uploads/'test.txt').write_text('attachment-test')
        self.assertEqual(self.client.get('/api/backup/export').status_code,403)
        self.login('admin@example.test')
        response=self.client.get('/api/backup/export')
        self.assertEqual(response.status_code,200)
        path=self.directory/'test-backup.zip'; path.write_bytes(response.data)
        manifest=verify_backup(path)
        response.close()
        self.assertIn('uploads/test.txt',manifest['files'])
        self.assertEqual(manifest['tables']['utente'],3)
        import subprocess, sys
        destination = self.directory / 'restored'
        subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'scripts/restore_backup.py'), str(path), '--data-dir', str(destination), '--server-stopped'], check=True, capture_output=True)
        self.assertEqual((destination/'uploads/test.txt').read_text(), 'attachment-test')
        with sqlite3.connect(str(destination/'database/sacro_cuore.db')) as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM utente').fetchone()[0],3)

    def test_migration_from_existing_database_preserves_every_original_value(self):
        original=Path(__file__).resolve().parents[1]/'database/sacro_cuore.db'
        copied=self.directory/'legacy.db'; shutil.copyfile(original,copied)
        records={}
        with sqlite3.connect(str(copied)) as connection:
            for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                columns=[r[1] for r in connection.execute('PRAGMA table_info("'+table+'")')]
                quoted=','.join('"'+c+'"' for c in columns)
                rows=connection.execute('SELECT '+quoted+' FROM "'+table+'"').fetchall()
                records[table]=(quoted,hashlib.sha256(repr(rows).encode()).hexdigest())
        class LegacyConfig(self.config): SQLALCHEMY_DATABASE_URI='sqlite:///'+str(copied)
        app=create_app(LegacyConfig)
        with app.app_context(): db.session.remove(); db.engine.dispose()
        with sqlite3.connect(str(copied)) as connection:
            for table,(columns,digest) in records.items():
                rows=connection.execute('SELECT '+columns+' FROM "'+table+'"').fetchall()
                self.assertEqual(hashlib.sha256(repr(rows).encode()).hexdigest(),digest,table)
        self.assertTrue(list((self.directory/'backups').glob('pre-alpha-2.0.0-*.sqlite3')))
