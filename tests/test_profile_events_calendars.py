import base64
import io
import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
import test_alpha_family as fixture
from models import db, Persona, Utente, Iscrizione, Attivita, Lista, DocumentoPersona, GruppoOratorio, GruppoCatechismo, GruppoDoposcuola


class ProfileEventsCalendarsTests(unittest.TestCase):
    setUp=fixture.AlphaFamilyTests.setUp
    tearDown=fixture.AlphaFamilyTests.tearDown
    login=fixture.AlphaFamilyTests.login
    activity=fixture.AlphaFamilyTests.activity

    def enroll(self,cf):
        event=self.activity(capacity=1)
        result=self.client.post('/api/iscrizioni',json={'attivita_id':event,'partecipanti':[cf]})
        self.assertEqual(result.status_code,201,result.json)
        return event,result.json['iscrizioni'][0]['id']

    def member_data(self):
        return {'nome':'Nuovo','cognome':'Membro','codice_fiscale':fixture.fiscal_code('VRDLGI10A01H501'),'ruolo_famiglia':'Figlio/a','consensi_registrazione':{'privacy':True,'foto_video':True}}

    def test_cancellation_keeps_payments_and_allows_reenrollment_same_record(self):
        event,ident=self.enroll(self.child_cf)
        with self.app.app_context():
            record=db.session.get(Iscrizione,ident);record.importo_pagato=5;record.stato_pagamento='acconto'
            db.session.commit()
        result=self.client.post(f'/api/iscrizioni/{ident}/disiscrivi')
        self.assertEqual(result.status_code,200,result.json)
        with self.app.app_context():
            record=db.session.get(Iscrizione,ident)
            self.assertEqual((record.stato,record.importo_pagato,record.stato_pagamento),('annullata',5,'acconto'))
            self.assertEqual(db.session.get(Attivita,event).posti_disponibili,1)
            self.assertNotIn(record.partecipante,Lista.query.filter_by(attivita_id=event).one().membri)
        options=self.client.get('/api/famiglie/opportunita').json['attivita'][str(event)]
        self.assertIn(self.child_cf,options['partecipanti'])
        result=self.client.post('/api/iscrizioni',json={'attivita_id':event,'partecipanti':[self.child_cf]})
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(result.json['iscrizioni'][0]['id'],ident)
        with self.app.app_context():
            record=db.session.get(Iscrizione,ident)
            self.assertEqual(record.importo_pagato,5)
            self.assertEqual(Iscrizione.query.filter_by(attivita_id=event).count(),1)
            self.assertIn(record.partecipante,Lista.query.filter_by(attivita_id=event).one().membri)

    def test_cancellation_permissions_for_self_head_and_admin(self):
        _,ident=self.enroll(self.child2_cf)
        self.login('child@example.test')
        self.assertEqual(self.client.post(f'/api/iscrizioni/{ident}/disiscrivi').status_code,403)
        self.assertEqual(self.client.put(f'/api/iscrizioni/{ident}/stato',json={'stato':'confermata'}).status_code,403)
        self.login('admin@example.test')
        self.assertEqual(self.client.post(f'/api/iscrizioni/{ident}/disiscrivi').status_code,200)
        self.login()
        _,own=self.enroll(self.child_cf)
        self.login('child@example.test')
        self.assertEqual(self.client.delete(f'/api/iscrizioni/{own}').status_code,200)
        with self.app.app_context(): self.assertEqual(db.session.get(Iscrizione,own).stato,'annullata')
        self.assertEqual(self.app.test_client().post(f'/api/iscrizioni/{ident}/disiscrivi').status_code,401)

    def test_consents_mandatory_even_without_account_and_recorded_on_member(self):
        root=f'/api/famiglie/{self.family_id}/membri'
        data=self.member_data()
        for flags in ({},{'privacy':True},{'privacy':True,'foto_video':False}):
            result=self.client.post(root,json=dict(data,consensi_registrazione=flags))
            self.assertEqual(result.status_code,400,result.json)
        data.update(email='contatto@example.test',civico_residenza='7/B',provincia_residenza='AL')
        result=self.client.post(root,json=data)
        self.assertEqual(result.status_code,201,result.json)
        with self.app.app_context():
            person=db.session.get(Persona,data['codice_fiscale'])
            consents=json.loads(person.consensi_aggiunta)
            self.assertTrue(consents['consensi']['privacy']['accettato'])
            self.assertTrue(consents['consensi']['foto_video']['accettato'])
            self.assertIsNotNone(consents['dichiarante_utente_id'])
            self.assertIsNone(person.utente)
            self.assertEqual((person.civico_residenza,person.provincia_residenza,person.email),('7/B','AL','contatto@example.test'))

    def test_multipart_profile_saves_address_photo_and_documents(self):
        data={'civico_residenza':'12/A','cap_residenza':'15000','provincia_residenza':'AL','luogo_nascita':'Asti','note_generali':'Nota conservata'}
        result=self.client.put('/api/persone/'+self.child_cf,data={'data':json.dumps(data),'documento_battesimo':(io.BytesIO(b'%PDF-1.4\nfixture'),'battesimo.pdf'),'foto':(io.BytesIO(b'\x89PNG\r\n\x1a\nfixture'),'foto.png')})
        self.assertEqual(result.status_code,200,result.json)
        person=result.json['persona']
        self.assertEqual((person['civico_residenza'],person['cap_residenza'],person['provincia_residenza']),('12/A','15000','AL'))
        self.assertEqual(len(person['documenti']),1)
        self.assertTrue(person['foto_profilo_url'].startswith('/uploads/foto_'))
        self.assertTrue((Path(self.config.UPLOAD_FOLDER)/person['foto_profilo_url'].split('/')[-1]).is_file())

    def test_bad_photo_does_not_partially_change_profile_or_save_document(self):
        result=self.client.put('/api/persone/'+self.child_cf,data={'data':json.dumps({'nome':'Non salvare'}),'documento_battesimo':(io.BytesIO(b'%PDF-1.4\nfixture'),'cert.pdf'),'foto':(io.BytesIO(b'not a png'),'foto.png')})
        self.assertEqual(result.status_code,400,result.json)
        with self.app.app_context():
            self.assertEqual(db.session.get(Persona,self.child_cf).nome,'Child')
            self.assertEqual(DocumentoPersona.query.count(),0)
        self.assertFalse(list(Path(self.config.UPLOAD_FOLDER).rglob('*.pdf')))

    def test_group_calendar_saved_normalized_and_available_to_enrolled_family(self):
        source='test-calendar@group.calendar.google.com'
        link='https://calendar.google.com/calendar/u/0?cid='+base64.urlsafe_b64encode(source.encode()).decode().rstrip('=')
        self.login('admin@example.test')
        for category in ('oratorio','catechismo','doposcuola'):
            result=self.client.post('/api/'+category+'/gruppi',json={'nome':'Calendario '+category,'google_calendar_url':link})
            self.assertEqual(result.status_code,201,result.json)
            group=result.json['gruppo']
            self.assertEqual(parse_qs(urlsplit(group['calendar_embed_url']).query)['src'],[source])
            ident=group['id']
            self.login()
            result=self.client.post('/api/famiglie/iscrizioni-gruppo',json={'categoria':category,'gruppo_id':ident,'partecipanti':[self.child2_cf]})
            self.assertEqual(result.status_code,200,result.json)
            calendars=self.client.get('/api/famiglie/calendari-gruppi').json['calendari']
            self.assertTrue(any(c['id']==category+':'+str(ident) for c in calendars))
            self.login('child@example.test')
            calendars=self.client.get('/api/famiglie/calendari-gruppi').json['calendari']
            self.assertFalse(any(c['id']==category+':'+str(ident) for c in calendars))
            self.login('admin@example.test')
            for invalid in ('https://example.test/calendar/embed?src=x@y.test','javascript:alert(1)','https://calendar.google.com.evil.test/calendar/embed?src=x@y.test','https://calendar.google.com/calendar/u/0'):
                self.assertEqual(self.client.put('/api/'+category+'/gruppi/'+str(ident),json={'google_calendar_url':invalid}).status_code,400)
            result=self.client.put('/api/'+category+'/gruppi/'+str(ident),json={'google_calendar_url':''})
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(result.json['gruppo']['google_calendar_url'],'')

    def test_failed_commit_cleans_new_files_and_preserves_existing_profile(self):
        before=set(Path(self.config.UPLOAD_FOLDER).rglob('*'))
        with patch('services.profile_files.db.session.commit',side_effect=IntegrityError('commit',{},Exception('conflict'))):
            result=self.client.put('/api/persone/'+self.child_cf,data={'data':json.dumps({'civico_residenza':'Non salvare'}),'documento_battesimo':(io.BytesIO(b'%PDF-1.4\nfixture'),'cert.pdf'),'foto':(io.BytesIO(b'\x89PNG\r\n\x1a\nfixture'),'foto.png')})
        self.assertEqual(result.status_code,409)
        with self.app.app_context():
            self.assertFalse(db.session.get(Persona,self.child_cf).civico_residenza)
            self.assertEqual(DocumentoPersona.query.count(),0)
        self.assertFalse([path for path in Path(self.config.UPLOAD_FOLDER).rglob('*') if path.is_file() and path not in before])

    def test_member_documents_and_consents_saved_together_without_account(self):
        data=self.member_data()
        result=self.client.post(f'/api/famiglie/{self.family_id}/membri',data={'data':json.dumps(data),'documento_battesimo':(io.BytesIO(b'%PDF-1.4\nfixture'),'battesimo.pdf')})
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(result.json['persona']['documenti'][0]['tipo'],'battesimo')
        with self.app.app_context():
            person=db.session.get(Persona,data['codice_fiscale'])
            self.assertIsNone(person.utente)
            self.assertTrue(json.loads(person.consensi_aggiunta)['consensi']['foto_video']['accettato'])
