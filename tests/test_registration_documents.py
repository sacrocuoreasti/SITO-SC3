import io
import json
import unittest
import zipfile
from pathlib import Path
import test_alpha_family as family_fixture
from models import db, Persona, Utente, DocumentoPersona, GruppoOratorio, GruppoCatechismo, GruppoDoposcuola, Iscrizione
from services.backup_service import verify_backup


class RegistrationDocumentTests(unittest.TestCase):
    setUp=family_fixture.AlphaFamilyTests.setUp
    tearDown=family_fixture.AlphaFamilyTests.tearDown
    login=family_fixture.AlphaFamilyTests.login
    registration=family_fixture.AlphaFamilyTests.registration
    activity=family_fixture.AlphaFamilyTests.activity

    def document(self, metadata=True):
        data={'documento_identita':(io.BytesIO(b'%PDF-1.4\nfixture'), 'carta.pdf')}
        if metadata:
            data.update(documento_numero_documento='AB12345',documento_rilasciato_da='Comune di prova',documento_data_rilascio='2024-01-01',documento_data_scadenza='2034-01-01')
        return data

    def test_password_confirmation_required_and_no_partial_registration(self):
        for confirmation in ('', 'diversa'):
            response=self.client.post('/api/auth/register',json=self.registration(conferma_password=confirmation))
            self.assertEqual(response.status_code,400)
        with self.app.app_context(): self.assertIsNone(Utente.query.filter_by(email='new@example.test').first())

    def test_multipart_registration_saves_all_five_private_documents(self):
        files=self.document()
        values=self.registration()
        values.update({k:v for k,v in files.items() if isinstance(v,str)})
        files['data']=json.dumps(values)
        for kind in ('battesimo','comunione','cresima','matrimonio'):
            files['documento_'+kind]=(io.BytesIO(b'%PDF-1.4\nfixture'), kind+'.pdf')
        response=self.client.post('/api/auth/register',data=files)
        self.assertEqual(response.status_code,201,response.json)
        documents=response.json['user']['persona']['documenti']
        self.assertEqual(len(documents),5)
        identity=next(d for d in documents if d['tipo']=='identita')
        self.assertEqual(identity['numero_documento'],'AB12345')
        download=self.client.get(identity['download_url']); self.assertEqual(download.status_code,200); download.close()
        with self.app.app_context():
            record=db.session.get(DocumentoPersona,identity['id'])
            self.assertTrue((Path(self.config.UPLOAD_FOLDER)/record.percorso).is_file())
            path=record.percorso
        anonymous=self.app.test_client()
        self.assertEqual(anonymous.get(identity['download_url']).status_code,401)
        self.assertEqual(anonymous.get('/uploads/'+path).status_code,404)
        self.assertEqual(anonymous.get('/uploads/other/../'+path).status_code,404)
        other=self.app.test_client(); self.login(client=other)
        self.assertEqual(other.get(identity['download_url']).status_code,404)
        self.login('admin@example.test')
        backup=self.client.get('/api/backup/export')
        archive=self.directory/'documents-backup.zip';archive.write_bytes(backup.data); backup.close()
        verify_backup(archive)
        with zipfile.ZipFile(archive) as z: self.assertTrue(any(name.endswith(path) for name in z.namelist()))

    def test_documents_validation_leaves_no_record_or_file(self):
        endpoint=f'/api/persone/{self.head_cf}/documenti'
        data=self.document(metadata=False)
        self.assertEqual(self.client.post(endpoint,data=data).status_code,400)
        data=self.document();data['documento_data_scadenza']='2020-01-01'
        self.assertEqual(self.client.post(endpoint,data=data).status_code,400)
        data={'documento_battesimo':(io.BytesIO(b'<script>invalid</script>'),'fake.pdf')}
        self.assertEqual(self.client.post(endpoint,data=data).status_code,400)
        with self.app.app_context(): self.assertEqual(DocumentoPersona.query.count(),0)
        self.assertFalse(list(Path(self.config.UPLOAD_FOLDER).rglob('*.pdf')))

    def test_head_manages_child_documents_but_sibling_cannot_download(self):
        endpoint=f'/api/persone/{self.child2_cf}/documenti'
        response=self.client.post(endpoint,data={'documento_comunione':(io.BytesIO(b'%PDF-1.4\nfixture'),'cert.pdf')})
        self.assertEqual(response.status_code,201,response.json)
        url=response.json['documenti'][0]['download_url']
        download=self.client.get(url); self.assertEqual(download.status_code,200); download.close()
        self.login('child@example.test')
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(endpoint,data={'documento_cresima':(io.BytesIO(b'%PDF-1.4\nfixture'),'cert.pdf')}).status_code,403)
        with self.app.test_request_context():
            self.assertEqual(db.session.get(Persona,self.child2_cf).visible_documents(),[])

    def test_all_group_ranges_validate_and_batch_is_atomic(self):
        self.login('admin@example.test')
        with self.app.app_context(): age=db.session.get(Persona,self.child_cf).eta
        for category,model,members in [('oratorio',GruppoOratorio,'ragazzi'),('catechismo',GruppoCatechismo,'ragazzi'),('doposcuola',GruppoDoposcuola,'studenti')]:
            with self.subTest(category=category):
                root='/api/'+category+'/gruppi'
                for limits in ({'eta_min':14,'eta_max':7},{'eta_min':-1},{'eta_max':True},{'eta_min':1.5}):
                    self.assertEqual(self.client.post(root,json=dict(nome='Invalid',**limits)).status_code,400)
                result=self.client.post(root,json={'nome':'Fascia Test','eta_min':age,'eta_max':age})
                self.assertEqual(result.status_code,201,result.json)
                ident=result.json['gruppo']['id'];url=root+'/'+str(ident)
                response=self.client.post(url+'/'+members+'/batch',json={'codici_fiscali':[self.child_cf, ' '.join(self.head_cf.lower())]})
                self.assertEqual(response.status_code,400,response.json)
                with self.app.app_context(): self.assertEqual(len(getattr(db.session.get(model,ident),members)),0)
                self.assertEqual(self.client.post(url+'/'+members,json={'codice_fiscale':self.child_cf}).status_code,200)
                self.assertEqual(self.client.put(url,json={'eta_min':age+1,'eta_max':age+2}).status_code,200)
                with self.app.app_context(): self.assertEqual(len(getattr(db.session.get(model,ident),members)),1)
                self.assertEqual(self.client.put(url,json={'eta_min':None,'eta_max':None}).status_code,200)
                self.assertEqual(self.client.post(url+'/'+members,json={'codice_fiscale':self.head_cf}).status_code,200)

    def test_enrollment_omits_clauses_and_does_not_invent_consent(self):
        activity=self.activity()
        result=self.client.post('/api/iscrizioni',json={'attivita_id':activity,'partecipanti':[self.child_cf]})
        self.assertEqual(result.status_code,201,result.json)
        with self.app.app_context():
            enrollment=Iscrizione.query.filter_by(attivita_id=activity).one()
            self.assertFalse(enrollment.consenso_privacy)
            self.assertFalse(enrollment.consenso_foto)
            self.assertFalse(enrollment.consenso_uscite)
            self.assertEqual(json.loads(enrollment.clausole_accettate),{})

    def test_group_age_applies_to_parent_and_activity_enrollment(self):
        self.login('admin@example.test')
        with self.app.app_context(): age=db.session.get(Persona,self.child_cf).eta
        result=self.client.post('/api/catechismo/gruppi',json={'nome':'Limiti Test','eta_min':age+1,'eta_max':age+3})
        ident=result.json['gruppo']['id']
        self.login()
        denied=self.client.put('/api/catechismo/gruppi/'+str(ident),json={'eta_min':None,'eta_max':None})
        self.assertEqual(denied.status_code,403)
        denied=self.client.post('/api/catechismo/iscrivi-figlio',json={'gruppo_id':ident,'codice_fiscale':self.child_cf})
        self.assertEqual(denied.status_code,400,denied.json)
        activity=self.activity()
        denied=self.client.post('/api/iscrizioni',json={'attivita_id':activity,'partecipanti':[self.child_cf],'gruppo_catechismo_id':ident})
        self.assertEqual(denied.status_code,400,denied.json)
        with self.app.app_context():
            self.assertEqual(Iscrizione.query.filter_by(attivita_id=activity).count(),0)
            self.assertEqual(len(db.session.get(GruppoCatechismo,ident).ragazzi),0)
