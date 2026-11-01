import hashlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from cryptography.exceptions import InvalidTag
import test_alpha_family as family_tests
from services.deployment_backup import encrypt_archive, decrypt_archive, restore_snapshot, validate_release_files, verify_restored_data, ReleaseGate


class DeploymentBackupTests(unittest.TestCase):
    setUp = family_tests.AlphaFamilyTests.setUp
    tearDown = family_tests.AlphaFamilyTests.tearDown
    login = family_tests.AlphaFamilyTests.login

    def target(self):
        version = self.app.config['APP_VERSION'].split(' ')[1].split('.')
        return 'alpha ' + '.'.join(version[:2] + [str(int(version[2]) + 1)])

    def prepare(self):
        self.login('admin@example.test')
        response = self.client.post('/api/backup/prepare-release', json={'target_version': self.target()})
        self.assertEqual(response.status_code, 200, response.data[:100])
        data = response.data
        response.close()
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            return bundle.read('backup.zip'), bundle.read('restore.enc'), json.loads(bundle.read('manifest.json'))

    def test_encryption_authenticates_key_and_release_metadata(self):
        manifest = {'target_version':'alpha 2.0.1', 'release_id':'test-release'}
        secret = b's' * 64
        first = encrypt_archive(b'private database', secret, manifest)
        second = encrypt_archive(b'private database', secret, manifest)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt_archive(first, secret, manifest), b'private database')
        for encrypted, key, meta in [(first,b'x'*64,manifest),(first[:-1]+bytes([first[-1]^1]),secret,manifest),(first,secret,dict(manifest,target_version='alpha 2.0.2'))]:
            with self.assertRaises(InvalidTag): decrypt_archive(encrypted,key,meta)

    def test_release_freezes_writes_and_cancel_reopens_without_changes(self):
        with patch.dict(os.environ, {'GOOGLE_SCRIPT_SECRET':'s'*64}):
            self.prepare()
            self.assertTrue(self.client.get('/health').json['maintenance'])
            self.assertEqual(self.client.post('/api/attivita',json={'titolo':'Must not be saved'}).status_code,503)
            self.assertEqual(self.client.get('/api/attivita').status_code,503)
            self.assertEqual(self.client.get('/api/auth/me').status_code,200)
            self.assertEqual(self.client.post('/api/backup/cancel-release',json={}).status_code,200)
            self.assertEqual(self.client.get('/api/attivita').status_code,200)

    def test_full_restore_and_comparison_preserve_data_passwords_and_uploads(self):
        with patch.dict(os.environ, {'GOOGLE_SCRIPT_SECRET':'s'*64}):
            (self.directory/'uploads/document.txt').write_text('private attachment')
            plain, encrypted, manifest = self.prepare()
            deployment = self.directory/'deployment'; deployment.mkdir()
            (deployment/'restore.enc').write_bytes(encrypted)
            (deployment/'manifest.json').write_text(json.dumps(manifest))
            target = self.directory/'new-instance/database/sacro_cuore.db'
            uploads = self.directory/'new-instance/uploads'
            restore_snapshot(deployment, self.target(), target, uploads, b's'*64)
            self.assertTrue(verify_restored_data(deployment,target,uploads,b's'*64)['matches'])
            with sqlite3.connect(str(target)) as connection:
                connection.execute("UPDATE utente SET last_login='2030-01-01' WHERE email='admin@example.test'")
                connection.commit()
            self.assertTrue(verify_restored_data(deployment,target,uploads,b's'*64)['matches'])
            with sqlite3.connect(str(target)) as connection:
                connection.execute("UPDATE persona SET nome='modified' WHERE nome='Child'")
                connection.commit()
            self.assertFalse(verify_restored_data(deployment,target,uploads,b's'*64)['matches'])
            # Un riavvio del worker sulla stessa istanza non deve cancellare nuove scritture.
            restore_snapshot(deployment,self.target(),target,uploads,b's'*64)
            with sqlite3.connect(str(target)) as connection:
                self.assertTrue(connection.execute("SELECT COUNT(*) FROM persona WHERE nome='modified'").fetchone()[0])
            self.client.post('/api/backup/cancel-release',json={})

    def test_new_instance_stays_closed_until_verified_and_worker_restart_keeps_new_writes(self):
        from app import create_app
        from models import db, Persona
        with patch.dict(os.environ, {'GOOGLE_SCRIPT_SECRET':'s'*64}):
            plain, encrypted, manifest = self.prepare()
        deployment = self.directory/'new-deployment'; deployment.mkdir()
        (deployment/'restore.enc').write_bytes(encrypted)
        (deployment/'manifest.json').write_text(json.dumps(manifest))
        target = self.directory/'complete-instance/database/site.db'
        target_uploads = self.directory/'complete-instance/uploads'
        class TargetConfig(self.config):
            APP_VERSION = manifest['target_version']
            SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(target)
            UPLOAD_FOLDER = str(target_uploads)
            DEPLOYMENT_DIRECTORY = str(deployment)
            DEPLOYMENT_RESTORE_IN_TESTS = True
        with patch.dict(os.environ, {'RENDER':'true','GOOGLE_SCRIPT_SECRET':'s'*64}):
            new = create_app(TargetConfig)
            client = new.test_client()
            self.assertTrue(client.get('/health').json['maintenance'])
            self.login('admin@example.test', client)
            self.assertEqual(client.post('/api/backup/cancel-release',json={}).status_code,409)
            result = client.post('/api/backup/complete-release',json={})
            self.assertEqual(result.status_code,200,result.json)
            self.assertTrue(result.json['matches'])
            self.assertFalse(client.get('/health').json['maintenance'])
            with new.app_context():
                db.session.get(Persona,self.head_cf).nome='Updated after deployment'
                db.session.commit(); db.session.remove(); db.engine.dispose()
            restarted = create_app(TargetConfig)
            self.assertFalse(restarted.test_client().get('/health').json['maintenance'])
            with restarted.app_context():
                self.assertEqual(db.session.get(Persona,self.head_cf).nome,'Updated after deployment')
                db.session.remove(); db.engine.dispose()
        self.client.post('/api/backup/cancel-release',json={})

    def test_future_version_without_snapshot_is_blocked(self):
        directory=self.directory/'deployment'; directory.mkdir()
        (directory/'bootstrap.json').write_text(json.dumps({'format':1,'bootstrap_version':'alpha 2.0.0'}))
        self.assertIsNone(validate_release_files(directory,'alpha 2.0.0'))
        with self.assertRaises(ValueError):validate_release_files(directory,'alpha 2.0.1')

    def test_freeze_waits_for_active_requests_and_rejects_new_admissions(self):
        gate=ReleaseGate()
        self.assertTrue(gate.admit())
        finished=threading.Event()
        thread=threading.Thread(target=lambda:(gate.freeze('alpha 2.0.1'),finished.set()))
        thread.start()
        deadline=time.monotonic()+2
        while not gate.state and time.monotonic()<deadline: time.sleep(0.01)
        self.assertFalse(gate.admit())
        self.assertFalse(finished.is_set())
        gate.leave(); thread.join(timeout=2)
        self.assertTrue(finished.is_set())
        gate.resume(); self.assertTrue(gate.admit()); gate.leave()

    def test_only_admin_can_prepare_and_missing_secret_does_not_freeze(self):
        self.assertEqual(self.client.post('/api/backup/prepare-release',json={'target_version':self.target()}).status_code,403)
        self.login('admin@example.test')
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(self.client.post('/api/backup/prepare-release',json={'target_version':self.target()}).status_code,503)
        self.assertFalse(self.client.get('/health').json['maintenance'])
