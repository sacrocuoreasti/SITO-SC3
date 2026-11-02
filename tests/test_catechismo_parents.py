import unittest
from datetime import date
from unittest.mock import patch
import test_alpha_family as fixture
from models import db,Persona,NucleoFamiliare,GruppoCatechismo,Presenza,Utente
from services import calendar_events
from services.catechismo_parents import members


def feed(source):
    day='07' if source.startswith('first') else '14'
    return f'''BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:{source}\r
DTSTART;TZID=Europe/Rome:202611{day}T150000\r
DTEND;TZID=Europe/Rome:202611{day}T160000\r
SUMMARY:Catechismo + Incontro Genitori\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:ordinary-{source}\r
DTSTART;TZID=Europe/Rome:20261121T150000\r
SUMMARY:Incontro ordinario\r
END:VEVENT\r
END:VCALENDAR\r
'''.encode()


class CatechismoParentsTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        calendar_events._cache.clear()
        self.login('admin@example.test')
        self.mother_cf=fixture.fiscal_code('BNCMRA82A41H501')
        self.other_parent_cf=fixture.fiscal_code('VRDLGU81A01H501')
        self.other_child_cf=fixture.fiscal_code('VRDLGI14A01H501')
        with self.app.app_context():
            head=db.session.get(Persona,self.head_cf);head.ruolo_famiglia='Padre';head.telefono='111111'
            mother=Persona(codice_fiscale=self.mother_cf,nome='Anna',cognome='Bianchi',ruolo_famiglia='Madre',data_nascita=date(1982,1,1),nucleo_id=self.family_id,telefono='222222')
            other_parent=Persona(codice_fiscale=self.other_parent_cf,nome='Luca',cognome='Verdi',ruolo_famiglia='Padre',data_nascita=date(1981,1,1))
            db.session.add_all([mother,other_parent]);db.session.flush()
            family=NucleoFamiliare(nome_famiglia='Altra famiglia',codice_fiscale_capofamiglia=self.other_parent_cf);db.session.add(family);db.session.flush();other_parent.nucleo_id=family.id
            child=Persona(codice_fiscale=self.other_child_cf,nome='Lia',cognome='Verdi',data_nascita=date(2014,1,1),ruolo_famiglia='Figlio/a',nucleo_id=family.id);db.session.add(child)
            first=GruppoCatechismo(nome='Primo',anno_pastorale='2026/2027',eta_min=8,eta_max=17,google_calendar_url='https://calendar.google.com/calendar/embed?src=first%40group.calendar.google.com')
            first.ragazzi=[db.session.get(Persona,self.child_cf),db.session.get(Persona,self.child2_cf)]
            second=GruppoCatechismo(nome='Secondo',anno_pastorale='2026/2027',eta_min=8,eta_max=17,google_calendar_url='https://calendar.google.com/calendar/embed?src=second%40group.calendar.google.com');second.ragazzi=[child,db.session.get(Persona,self.child2_cf)]
            old=GruppoCatechismo(nome='Vecchio',anno_pastorale='2025/2026',google_calendar_url='https://calendar.google.com/calendar/embed?src=old%40group.calendar.google.com');old.ragazzi=[child]
            parents=GruppoCatechismo(nome='Genitori',anno_pastorale='2026/2027',eta_min=26)
            db.session.add_all([first,second,old,parents]);db.session.commit()
            self.first_id=first.id;self.second_id=second.id;self.parents_id=parents.id

    def appello(self,cf,day='2026-11-07'):
        return self.client.post('/api/catechismo/presenze',json={'gruppo_id':self.parents_id,'data':day,'presenze':[{'codice_fiscale':cf,'presente':True}]})

    @patch('services.calendar_events.fetch_public_feed',side_effect=feed)
    def test_automatic_parents_and_dates_deduplicate_siblings_and_filter_year_and_marker(self,fetch):
        groups=self.client.get('/api/catechismo/gruppi').json['gruppi']
        parents=next(g for g in groups if g['id']==self.parents_id)
        self.assertTrue(parents['gruppo_genitori']);self.assertEqual(parents['totale_ragazzi'],3)
        self.assertEqual(len({p['codice_fiscale'] for p in parents['ragazzi']}),3)
        response=self.client.get(f'/api/calendari-gruppi/catechismo/{self.parents_id}?mese=2026-11')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual([e['giorno'] for e in response.json['eventi']],['2026-11-07','2026-11-14'])
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.parents_id}?mese=2027-11').json['eventi'],[])
        with self.app.app_context():
            self.assertEqual(len(db.session.get(GruppoCatechismo,self.parents_id).ragazzi),0)
            self.assertEqual(Presenza.query.count(),0)

    @patch('services.calendar_events.fetch_public_feed',side_effect=feed)
    def test_only_expected_parents_can_be_marked_and_same_parent_has_one_row(self,fetch):
        path=f'/api/catechismo/gruppi/{self.parents_id}/registro?mese=2026-11&giorno=2026-11-07'
        response=self.client.get(path)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual({p['codice_fiscale'] for p in response.json['studenti']},{self.head_cf,self.mother_cf})
        self.assertEqual(self.appello(self.other_parent_cf).status_code,403)
        self.assertEqual(self.appello(self.head_cf).status_code,200)
        self.assertEqual(self.appello(self.head_cf).status_code,200)
        self.assertEqual(self.appello(self.head_cf,'2026-11-21').status_code,403)
        with self.app.app_context():self.assertEqual(Presenza.query.count(),1)
        self.login()
        own=self.client.get('/api/famiglie/registri-gruppi/catechismo').json['gruppi']
        parent_group=next(g for g in own if g['id']==self.parents_id)
        self.assertEqual({p['codice_fiscale'] for p in parent_group['componenti']},{self.head_cf,self.mother_cf})
        self.assertNotIn(self.other_parent_cf,str(parent_group))
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.parents_id}/allergie').status_code,403)

    def test_roster_has_sorted_names_parent_contacts_and_separate_medical_fields_with_bound_access(self):
        with self.app.app_context():
            child=db.session.get(Persona,self.child_cf);child.allergie='Polline';child.intolleranze_alimentari='Lattosio';child.terapie_medicinali='Terapia test';child.note_generali='Nota test'
            user=Utente(email='catechista@example.test',ruolo='catechista');user.set_password('password-test-123');db.session.add(user);db.session.flush()
            db.session.get(GruppoCatechismo,self.first_id).catechisti=[user];db.session.commit()
        self.login('catechista@example.test')
        response=self.client.get(f'/api/catechismo/gruppi/{self.first_id}/allergie')
        self.assertEqual(response.status_code,200,response.json)
        person=next(p for p in response.json['ragazzi'] if p['codice_fiscale']==self.child_cf)
        self.assertEqual({p['telefono'] for p in person['genitori']},{'111111','222222'})
        self.assertEqual(person['terapie_medicinali'],'Terapia test')
        self.assertEqual(person['intolleranze_alimentari'],'Lattosio')
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.second_id}/allergie').status_code,403)
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.first_id}/assegnabili').status_code,403)

    def test_assignable_list_excludes_existing_out_of_age_and_automatic_parent_groups(self):
        response=self.client.get(f'/api/catechismo/gruppi/{self.first_id}/assegnabili')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual({p['codice_fiscale'] for p in response.json['persone']},{self.other_child_cf})
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.parents_id}/assegnabili').json['persone'],[])
        self.assertEqual(self.client.post(f'/api/catechismo/gruppi/{self.first_id}/ragazzi/batch',json={'codici_fiscali':[self.head_cf]}).status_code,400)
        self.assertEqual(self.client.post(f'/api/catechismo/gruppi/{self.parents_id}/ragazzi',json={'codice_fiscale':self.other_parent_cf}).status_code,400)

    @patch('services.calendar_events.fetch_public_feed',side_effect=feed)
    def test_source_membership_changes_update_parent_roster_without_overwriting_manual_or_history(self,fetch):
        self.assertEqual(self.appello(self.head_cf).status_code,200)
        with self.app.app_context():
            for group in GruppoCatechismo.query.filter_by(anno_pastorale='2026/2027').all():
                if group.id!=self.parents_id: group.ragazzi=[]
            db.session.commit()
            parents=members(db.session.get(GruppoCatechismo,self.parents_id))
            self.assertEqual([p.codice_fiscale for p in parents],[self.head_cf])
            self.assertEqual(Presenza.query.count(),1)

    @patch('services.calendar_events.fetch_public_feed')
    def test_same_parent_meeting_shared_by_two_groups_is_one_event_and_one_attendance_row(self,fetch):
        fetch.side_effect=lambda source: feed(source).replace(b'20261114',b'20261107')
        response=self.client.get(f'/api/calendari-gruppi/catechismo/{self.parents_id}?mese=2026-11')
        self.assertEqual(len(response.json['eventi']),1)
        register=self.client.get(f'/api/catechismo/gruppi/{self.parents_id}/registro?mese=2026-11&giorno=2026-11-07')
        self.assertEqual(len(register.json['studenti']),3)
        self.assertEqual(self.appello(self.head_cf).status_code,200)
        self.assertEqual(self.appello(self.head_cf).status_code,200)
        with self.app.app_context(): self.assertEqual(Presenza.query.count(),1)

    def test_hiding_old_form_fields_preserves_existing_class_and_linked_activity(self):
        from models import Attivita
        with self.app.app_context():
            activity=Attivita(titolo='Attività esistente',categoria='catechismo')
            db.session.add(activity);db.session.flush();activity_id=activity.id
            group=db.session.get(GruppoCatechismo,self.first_id)
            group.anno_catechismo='Classe precedente';group.attivita_id=activity_id
            db.session.commit()
        response=self.client.put(f'/api/catechismo/gruppi/{self.first_id}',json={'nome':'Nome aggiornato'})
        self.assertEqual(response.status_code,200,response.json)
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,self.first_id)
            self.assertEqual(group.anno_catechismo,'Classe precedente')
            self.assertEqual(group.attivita_id,activity_id)

    @patch('services.calendar_events.fetch_public_feed',side_effect=calendar_events.CalendarUnavailable('Offline'))
    def test_calendar_outage_never_records_unverified_parent_attendance(self,fetch):
        response=self.appello(self.head_cf)
        self.assertEqual(response.status_code,400,response.json)
        with self.app.app_context(): self.assertEqual(Presenza.query.count(),0)
