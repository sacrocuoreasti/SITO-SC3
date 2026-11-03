import unittest
from datetime import date
from unittest.mock import patch
import test_alpha_family as fixture
from test_group_calendar_register import FEED
from models import db,Persona,Utente,Attivita,Iscrizione,Presenza,GruppoDoposcuola,GruppoOratorio
from services import calendar_events


class PortalUpdateTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown
    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        calendar_events._cache.clear()
        self.login('admin@example.test')
        self.groups={}
        with self.app.app_context():
            head=db.session.get(Persona,self.head_cf);head.ruolo_famiglia='Padre';head.telefono='111111'
            child=db.session.get(Persona,self.child_cf);child.terapie_medicinali='Terapia di prova'
            for category,model,collection in [('oratorio',GruppoOratorio,'ragazzi'),('doposcuola',GruppoDoposcuola,'studenti')]:
                kwargs={'nome':'Gruppo '+category,'eta_min':8,'eta_max':14,'google_calendar_url':'https://calendar.google.com/calendar/embed?src=test%40group.calendar.google.com'}
                if category=='doposcuola':kwargs['anno_scolastico']='2026/2027'
                else:kwargs['anno_pastorale']='2026/2027'
                group=model(**kwargs);getattr(group,collection).append(child);db.session.add(group);db.session.flush();self.groups[category]=group.id
            db.session.commit()

    def path(self,category,part):return f'/api/calendari-gruppi/{category}/{self.groups[category]}/{part}'

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_group_dates_roster_and_daily_attendance_use_the_same_flow_for_both_categories(self,fetch):
        for category in self.groups:
            registry=self.client.get(self.path(category,'registro')+'?periodo=anno')
            self.assertEqual(registry.status_code,200,registry.json)
            self.assertEqual(len(registry.json['date_incontri']),3)
            roster=self.client.get(self.path(category,'elenco'))
            self.assertEqual(roster.status_code,200,roster.json)
            self.assertEqual(roster.json['persone'][0]['genitori'][0]['telefono'],'111111')
            self.assertEqual(roster.json['persone'][0]['terapie_medicinali'],'Terapia di prova')
            payload={'data':'2026-11-07','presenze':[{'codice_fiscale':self.child_cf,'presente':False}]}
            for _ in range(2):self.assertEqual(self.client.post(self.path(category,'registro'),json=payload).status_code,200)
            registry=self.client.get(self.path(category,'registro')+'?periodo=anno').json
            self.assertEqual(registry['incontri_registrati'],1)
            self.assertEqual(registry['studenti'][0]['assenti'],1)
            self.assertEqual(registry['studenti'][0]['totale_incontri'],1)
        with self.app.app_context():self.assertEqual(Presenza.query.count(),2)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_meeting_deletion_keeps_google_schedule_and_other_group_records(self,fetch):
        for category in self.groups:
            self.client.post(self.path(category,'registro'),json={'data':'2026-11-07','presenze':[{'codice_fiscale':self.child_cf,'presente':True}]})
        response=self.client.delete(self.path('doposcuola','registro'),json={'data':'2026-11-07'})
        self.assertEqual(response.status_code,200,response.json)
        registry=self.client.get(self.path('doposcuola','registro')+'?mese=2026-11').json
        self.assertFalse(registry['date_incontri'][0]['registrato'])
        with self.app.app_context():self.assertEqual(Presenza.query.one().gruppo_categoria,'oratorio')

    def test_roster_candidates_respect_ages_and_existing_members_and_do_not_create_accounts(self):
        for category in self.groups:
            response=self.client.get(self.path(category,'assegnabili'))
            self.assertEqual(response.status_code,200,response.json)
            self.assertEqual({p['codice_fiscale'] for p in response.json['persone']},{self.child2_cf})
            self.assertEqual(self.client.post(self.path(category,'elenco'),json={'codice_fiscale':self.head_cf}).status_code,400)
            for _ in range(2):self.assertEqual(self.client.post(self.path(category,'elenco'),json={'codice_fiscale':self.child2_cf}).status_code,200)
            self.assertEqual(len(self.client.get(self.path(category,'elenco')).json['persone']),2)
        with self.app.app_context():self.assertEqual(Utente.query.count(),3)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_family_cannot_access_management_and_assigned_educator_cannot_see_another_register(self,fetch):
        self.login()
        for category in self.groups:
            for part in ('registro','elenco','assegnabili'):
                self.assertEqual(self.client.get(self.path(category,part)).status_code,403)
        with self.app.app_context():
            user=Utente(email='educator@example.test',ruolo='educatore');user.set_password('password-test-123');db.session.add(user);db.session.flush()
            db.session.get(GruppoDoposcuola,self.groups['doposcuola']).educatore_utente_id=user.id
            other=GruppoDoposcuola(nome='Altro gruppo');db.session.add(other);db.session.commit();other_id=other.id
        self.login('educator@example.test')
        self.assertEqual(self.client.get(self.path('doposcuola','elenco')).status_code,200)
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/doposcuola/{other_id}/elenco').status_code,403)
        self.assertEqual(self.client.get(self.path('doposcuola','assegnabili')).status_code,403)
        self.assertEqual(self.client.delete(self.path('doposcuola','registro'),json={'data':'2026-11-07'}).status_code,403)

    def test_past_or_inactive_activities_keep_enrollment_history_without_new_candidates(self):
        with self.app.app_context():
            event=Attivita(titolo='Evento passato',categoria='evento',data_inizio=date(2000,1,1),data_fine=date(2000,1,2),is_attiva=False,is_pubblicato=True)
            db.session.add(event);db.session.flush();event_id=event.id
            db.session.add(Iscrizione(attivita_id=event.id,codice_fiscale_partecipante=self.child_cf,stato='confermata'))
            db.session.commit()
        self.login()
        events=self.client.get('/api/attivita?solo_attive=false').json['attivita']
        self.assertIn(event_id,[event['id'] for event in events])
        options=self.client.get('/api/famiglie/opportunita').json['attivita'][str(event_id)]
        self.assertEqual(options['partecipanti'],[])
        self.assertTrue(options['ha_iscrizioni']);self.assertTrue(options['gia_iscritto'])
