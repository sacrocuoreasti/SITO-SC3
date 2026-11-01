import json
import os
import smtplib
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from services.email_service import invia_email, email_configuration_status


class EmailTests(unittest.TestCase):
    def test_missing_configuration_never_opens_network(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as network, patch('smtplib.SMTP') as smtp:
            self.assertFalse(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])
            network.assert_not_called()
            smtp.assert_not_called()

    def test_google_script_confirmation_payload_and_signature(self):
        import hashlib
        import hmac
        settings = {'EMAIL_PROVIDER': 'google_apps_script', 'GOOGLE_SCRIPT_SECRET': 's' * 64,
                    'GOOGLE_SCRIPT_URL': 'https://script.google.com/macros/s/test-deployment/exec'}
        def accepted(request, timeout):
            envelope = json.loads(request.data)
            signed = envelope['timestamp'] + '.' + envelope['nonce'] + '.' + envelope['payload']
            expected = hmac.new(settings['GOOGLE_SCRIPT_SECRET'].encode(), signed.encode(), hashlib.sha256).hexdigest()
            self.assertEqual(envelope['signature'], expected)
            self.assertNotIn(settings['GOOGLE_SCRIPT_SECRET'], request.data.decode())
            mail = json.loads(envelope['payload'])
            self.assertEqual(mail['to'], 'person@example.test')
            self.assertEqual(mail['html'], '<p>È un test</p>')
            self.assertEqual(timeout, 15)
            response = MagicMock()
            response.read.return_value = json.dumps({'ok': True, 'id': envelope['nonce']}).encode()
            response.__enter__.return_value = response
            return response
        with patch.dict(os.environ, settings, clear=True), patch('urllib.request.urlopen', side_effect=accepted):
            self.assertTrue(invia_email('person@example.test', 'Oggetto', '<p>È un test</p>', 'Test')[0])
            self.assertNotIn('s' * 64, str(email_configuration_status()))

    def test_google_script_errors_never_report_success(self):
        settings = {'GOOGLE_SCRIPT_SECRET': 's' * 64, 'GOOGLE_SCRIPT_URL': 'https://script.google.com/macros/s/test/exec'}
        errors = [urllib.error.HTTPError('https://script.google.com', 403, 'Forbidden', {}, None), TimeoutError(), urllib.error.URLError('offline')]
        with patch.dict(os.environ, settings, clear=True):
            for error in errors:
                with self.subTest(error=type(error).__name__), patch('urllib.request.urlopen', side_effect=error):
                    self.assertFalse(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])
            for result in [{'ok': False, 'error': 'unauthorized'}, {'ok': False, 'error': 'quota_exceeded'}, {'ok': True, 'id': 'wrong'}, {}, []]:
                response = MagicMock()
                response.read.return_value = json.dumps(result).encode()
                response.__enter__.return_value = response
                with self.subTest(result=result), patch('urllib.request.urlopen', return_value=response):
                    self.assertFalse(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])
            response.read.return_value = b'<html>Sign in to Google</html>'
            with patch('urllib.request.urlopen', return_value=response):
                self.assertFalse(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])

    def test_smtp_starttls_and_tls(self):
        for port in ['587', '465']:
            settings = {'EMAIL_PROVIDER': 'smtp', 'SMTP_USER': 'sender@example.test', 'SMTP_PASS': 'test-pass', 'SMTP_PORT': port}
            with patch.dict(os.environ, settings, clear=True), patch('smtplib.SMTP') as smtp, patch('smtplib.SMTP_SSL') as tls:
                server = (tls if port == '465' else smtp).return_value
                server.sendmail.return_value = {}
                self.assertTrue(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])
                server.login.assert_called_once_with('sender@example.test', 'test-pass')
                if port == '587':
                    server.starttls.assert_called_once()
                else:
                    server.starttls.assert_not_called()

    def test_smtp_authentication_failure(self):
        with patch.dict(os.environ, {'SMTP_USER': 'sender@example.test', 'SMTP_PASS': 'wrong'}, clear=True), patch('smtplib.SMTP') as smtp:
            smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'wrong')
            self.assertFalse(invia_email('person@example.test', 'Test', '<p>Test</p>')[0])

    def test_invalid_provider_and_partial_config(self):
        for settings in [{'EMAIL_PROVIDER': 'unknown'}, {'GOOGLE_SCRIPT_URL': 'https://script.google.com/macros/s/test/exec'}, {'GOOGLE_SCRIPT_URL': 'https://example.test/not-google', 'GOOGLE_SCRIPT_SECRET': 's' * 64}]:
            with patch.dict(os.environ, settings, clear=True):
                self.assertFalse(email_configuration_status()['configured'])
