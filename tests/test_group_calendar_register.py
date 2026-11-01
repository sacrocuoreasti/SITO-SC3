import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_alpha_family as fixture
from models import db,Persona,Utente,Attivita,Presenza,GruppoCatechismo,GruppoDoposcuola,GruppoOratorio
from services import calendar_events
from services.group_attendance import group_records

FEED=b'''BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//CuoreInRete tests//IT\r
BEGIN:VEVENT\r
UID:weekly@test\r
DTSTART;TZID=Europe/Rome:20261107T150000\r
DTEND;TZID=Europe/Rome:20261107T160000\r
RRULE:FREQ=WEEKLY;COUNT=3\r
SUMMARY:Incontro settimanale\r
LOCATION:Aula parrocchiale\r
END:VEVENT\r
END:VCALENDAR\r
'''


class GroupCalendarRegisterTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        calendar_events._cache.clear()
        self.login('admin@example.test')
        with self.app.app_context():
            group=GruppoCatechismo(nome='Gruppo prova',eta_min=0,eta_max=17,stato='pubblico',google_calendar_url='https://calendar.google.com/calendar/embed?src=test%40group.calendar.google.com')
            group.ragazzi=[db.session.get(Persona,self.child_cf),db.session.get(Persona,self.child2_cf)]
            db.session.add(group);db.session.commit();self.group_id=group.id

    def attendance(self,cf=None,present=True,day='2026-11-07'):
        return self.client.post('/api/catechismo/presenze',json={'gruppo_id':self.group_id,'data':day,'presenze':[{'codice_fiscale':cf or self.child_cf,'presente':present}]})

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_monthly_calendar_and_registry_read_never_create_attendance(self,fetch):
        root=f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11'
        first=self.client.get(root);second=self.client.get(root)
        self.assertEqual(first.status_code,200,first.json)
        self.assertEqual(len(first.json['eventi']),3)
        self.assertEqual(first.json['eventi'],second.json['eventi'])
        self.assertEqual(fetch.call_count,1)
        registry=self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?mese=2026-11')
        self.assertEqual(registry.status_code,200,registry.json)
        self.assertEqual(len(registry.json['date_incontri']),3)
        self.assertTrue(all(not day['registrato'] for day in registry.json['date_incontri']))
        self.assertTrue(all(person['totale_incontri']==0 for person in registry.json['studenti']))
        with self.app.app_context():
            self.assertEqual(Presenza.query.count(),0)
            self.assertIsNone(db.session.get(GruppoCatechismo,self.group_id).attivita_id)

    @patch('services.calendar_events.fetch_public_feed')
    def test_group_date_list_includes_entire_pastoral_year_and_older_saved_attendance(self,fetch):
        fetch.return_value=FEED.replace(b'20261107',b'20260907').replace(b'FREQ=WEEKLY;COUNT=3',b'FREQ=MONTHLY;COUNT=12')
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,self.group_id)
            group.anno_pastorale='2026/2027'
            db.session.commit()
        self.assertEqual(self.attendance(day='2024-12-01').status_code,200)
        response=self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?periodo=anno')
        self.assertEqual(response.status_code,200,response.json)
        dates=response.json['date_incontri']
        self.assertEqual(len(dates),13)
        self.assertEqual(dates[0]['data'],'2024-12-01')
        self.assertTrue(dates[0]['registrato'])
        self.assertEqual(dates[1]['data'],'2026-09-07')
        self.assertEqual(dates[-1]['data'],'2027-08-07')
        self.assertTrue(all(not row['registrato'] for row in dates[1:]))
        self.assertEqual(fetch.call_count,1)
        with self.app.app_context(): self.assertEqual(Presenza.query.count(),1)
        self.login()
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?periodo=anno').status_code,403)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_daily_save_is_idempotent_and_google_dates_do_not_affect_percentage(self,fetch):
        self.assertEqual(self.attendance().status_code,200)
        self.assertEqual(self.attendance(present=False).status_code,200)
        with self.app.app_context():
            record=Presenza.query.one()
            self.assertEqual((record.gruppo_categoria,record.gruppo_id,record.presente),('catechismo',self.group_id,False))
            self.assertEqual(record.titolo_incontro,'Incontro settimanale')
        registry=self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?mese=2026-11').json
        self.assertEqual(registry['incontri_registrati'],1)
        self.assertEqual(len(registry['date_incontri']),3)
        person=next(p for p in registry['studenti'] if p['codice_fiscale']==self.child_cf)
        self.assertEqual((person['totale_incontri'],person['assenti'],person['percentuale']),(1,1,0))
        self.login()
        own=self.client.get('/api/famiglie/registri-gruppi/catechismo').json['gruppi']
        group=next(g for g in own if g['id']==self.group_id)
        person=next(p for p in group['componenti'] if p['codice_fiscale']==self.child_cf)
        self.assertEqual((person['totale'],person['assenti'],person['percentuale']),(1,1,0))

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_same_calendar_day_merges_with_existing_register_without_duplicates(self,fetch):
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,self.group_id)
            activity=Attivita(titolo='Vecchia attività',categoria='catechismo');db.session.add(activity);db.session.flush()
            group.attivita_id=activity.id
            db.session.add(Presenza(attivita_id=activity.id,codice_fiscale_persona=self.child_cf,data=date(2026,11,7),presente=True,titolo_incontro='Titolo conservato'))
            db.session.commit()
        result=self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?mese=2026-11').json
        dates=[d for d in result['date_incontri'] if d['data']=='2026-11-07']
        self.assertEqual(len(dates),1)
        self.assertTrue(dates[0]['registrato']);self.assertEqual(dates[0]['titolo_incontro'],'Titolo conservato')
        self.assertEqual(self.attendance().status_code,200)
        with self.app.app_context(): self.assertEqual(Presenza.query.count(),1)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_membership_keeps_section_even_after_last_enrollment(self,fetch):
        self.login()
        options=self.client.get('/api/famiglie/opportunita').json
        self.assertFalse(any(g['id']==self.group_id for g in options['gruppi']['catechismo']))
        self.assertTrue(any(g['id']==self.group_id for g in options['gruppi_iscritti']['catechismo']))
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,self.group_id);group.stato='chiuso';db.session.commit()
        options=self.client.get('/api/famiglie/opportunita').json
        self.assertTrue(any(g['id']==self.group_id for g in options['gruppi_iscritti']['catechismo']))
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11').status_code,200)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_parent_cannot_record_and_cannot_read_other_families_attendance(self,fetch):
        self.assertEqual(self.attendance().status_code,200)
        self.assertEqual(self.attendance(cf=self.child2_cf,present=False).status_code,200)
        self.login('child@example.test')
        self.assertEqual(self.attendance().status_code,403)
        data=self.client.get(f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11').json
        self.assertFalse(data['puo_registrare_presenze'])
        self.assertEqual(len(data['presenze']),1)
        own=self.client.get('/api/famiglie/registri-gruppi/catechismo').json['gruppi']
        group=next(g for g in own if g['id']==self.group_id)
        self.assertEqual([p['codice_fiscale'] for p in group['componenti']],[self.child_cf])
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro').status_code,403)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_catechist_only_records_assigned_groups(self,fetch):
        with self.app.app_context():
            teacher=Utente(email='teacher@example.test',ruolo='catechista');teacher.set_password('password-test-123');db.session.add(teacher)
            assigned=db.session.get(GruppoCatechismo,self.group_id)
            assigned.catechisti.append(teacher)
            other=GruppoCatechismo(nome='Altro gruppo',stato='chiuso');db.session.add(other);db.session.commit();other_id=other.id
        self.login('teacher@example.test')
        self.assertEqual(self.attendance().status_code,200)
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{other_id}/registro').status_code,403)
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{other_id}').status_code,403)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_groups_sharing_activity_do_not_overwrite_each_others_presence(self,fetch):
        self.assertEqual(self.attendance().status_code,200)
        with self.app.app_context():
            original=db.session.get(GruppoCatechismo,self.group_id)
            other=GruppoCatechismo(nome='Secondo gruppo',attivita_id=original.attivita_id,stato='pubblico');other.ragazzi=[db.session.get(Persona,self.child_cf)]
            db.session.add(other);db.session.commit();other_id=other.id
        result=self.client.post('/api/catechismo/presenze',json={'gruppo_id':other_id,'data':'2026-11-07','presenze':[{'codice_fiscale':self.child_cf,'presente':False}]})
        self.assertEqual(result.status_code,200,result.json)
        with self.app.app_context():
            first=group_records('catechismo',db.session.get(GruppoCatechismo,self.group_id));second=group_records('catechismo',db.session.get(GruppoCatechismo,other_id))
            self.assertTrue(first[0].presente);self.assertFalse(second[0].presente);self.assertEqual(Presenza.query.count(),2)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_oratory_and_after_school_registers_are_group_scoped(self,fetch):
        for category,model,collection in [('oratorio',GruppoOratorio,'ragazzi'),('doposcuola',GruppoDoposcuola,'studenti')]:
            with self.app.app_context():
                group=model(nome='Gruppo '+category,stato='pubblico');getattr(group,collection).append(db.session.get(Persona,self.child_cf));db.session.add(group);db.session.commit();ident=group.id
            endpoint=f'/api/oratorio/gruppi/{ident}/presenze' if category=='oratorio' else '/api/doposcuola/presenze'
            body={'gruppo_id':ident,'data':'2026-11-07','presenze':[{'codice_fiscale':self.child_cf,'presente':True}]}
            self.assertEqual(self.client.post(endpoint,json=body).status_code,200)
            self.assertEqual(self.client.post(endpoint,json=body).status_code,200)
            self.login()
            result=self.client.get('/api/famiglie/registri-gruppi/'+category)
            person=next(g for g in result.json['gruppi'] if g['id']==ident)['componenti'][0]
            self.assertEqual((person['totale'],person['presenti']),(1,1))
            self.login('admin@example.test')

    def test_recurrences_dst_exceptions_and_all_day_end_are_respected(self):
        source=b'''BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:dst@test\r
DTSTART;TZID=Europe/Rome:20261018T100000\r
DTEND;TZID=Europe/Rome:20261018T110000\r
RRULE:FREQ=WEEKLY;COUNT=3\r
EXDATE;TZID=Europe/Rome:20261025T100000\r
SUMMARY:Ricorrente\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:day@test\r
DTSTART;VALUE=DATE:20261020\r
DTEND;VALUE=DATE:20261022\r
SUMMARY:Due giorni\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:cancel@test\r
DTSTART:20261020T100000Z\r
STATUS:CANCELLED\r
SUMMARY:Cancellato\r
END:VEVENT\r
END:VCALENDAR\r
'''
        parsed=calendar_events.Calendar.from_ical(source)
        events=calendar_events.expand_events(parsed,date(2026,10,1),date(2026,11,1))
        recurring=[event for event in events if event['titolo']=='Ricorrente']
        self.assertEqual([e['ora'] for e in recurring],['10:00','10:00'])
        self.assertTrue(recurring[0]['inizio'].endswith('+02:00'));self.assertTrue(recurring[1]['inizio'].endswith('+01:00'))
        all_day=next(event for event in events if event['titolo']=='Due giorni')
        self.assertEqual(all_day['giorni'],['2026-10-20','2026-10-21'])
        self.assertFalse(any(event['titolo']=='Cancellato' for event in events))

    @patch('services.calendar_events.fetch_public_feed',side_effect=calendar_events.CalendarUnavailable('Google non disponibile'))
    def test_google_failure_keeps_saved_attendance_and_offers_clear_calendar_error(self,fetch):
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,self.group_id)
            activity=Attivita(titolo='Storico',categoria='catechismo');db.session.add(activity);db.session.flush();group.attivita_id=activity.id
            db.session.add(Presenza(attivita_id=activity.id,codice_fiscale_persona=self.child_cf,data=date(2026,11,7),presente=True));db.session.commit()
        response=self.client.get(f'/api/catechismo/gruppi/{self.group_id}/registro?mese=2026-11')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['incontri_registrati'],1);self.assertTrue(response.json['avviso_calendario'])
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11').status_code,502)
        self.assertEqual(fetch.call_count,1)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_concurrent_saves_do_not_duplicate_daily_attendance(self,fetch):
        self.client.get(f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11')
        clients=[self.app.test_client(),self.app.test_client()]
        for client in clients:self.login('admin@example.test',client=client)
        def save(client):
            return client.post('/api/catechismo/presenze',json={'gruppo_id':self.group_id,'data':'2026-11-07','presenze':[{'codice_fiscale':self.child_cf,'presente':True}]}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(save,clients))
        self.assertEqual(statuses,[200,200])
        with self.app.app_context():self.assertEqual(Presenza.query.count(),1)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_unlinked_legacy_attendance_remains_visible_after_new_daily_save(self,fetch):
        with self.app.app_context():
            activity=Attivita(titolo='Registro precedente',categoria='catechismo');db.session.add(activity);db.session.flush()
            db.session.add(Presenza(attivita_id=activity.id,codice_fiscale_persona=self.child_cf,data=date(2026,10,31),presente=False))
            db.session.commit()
        self.assertEqual(self.attendance().status_code,200)
        with self.app.app_context():
            records=group_records('catechismo',db.session.get(GruppoCatechismo,self.group_id))
            self.assertEqual(len(records),2)
            self.assertEqual(records[0].data,date(2026,10,31));self.assertFalse(records[0].presente)

    def test_moved_and_cancelled_occurrences_do_not_duplicate_the_weekly_meeting(self):
        source=FEED.replace(b'END:VCALENDAR',b'''BEGIN:VEVENT\r
UID:weekly@test\r
RECURRENCE-ID;TZID=Europe/Rome:20261114T150000\r
DTSTART;TZID=Europe/Rome:20261115T160000\r
DTEND;TZID=Europe/Rome:20261115T170000\r
SEQUENCE:2\r
SUMMARY:Incontro spostato\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:weekly@test\r
RECURRENCE-ID;TZID=Europe/Rome:20261121T150000\r
DTSTART;TZID=Europe/Rome:20261121T150000\r
DTEND;TZID=Europe/Rome:20261121T160000\r
STATUS:CANCELLED\r
SEQUENCE:2\r
END:VEVENT\r
END:VCALENDAR''')
        events=calendar_events.expand_events(calendar_events.Calendar.from_ical(source),date(2026,11,1),date(2026,12,1))
        self.assertEqual([event['giorno'] for event in events],['2026-11-07','2026-11-15'])
        self.assertEqual(events[1]['titolo'],'Incontro spostato')

    @patch('services.calendar_events.fetch_public_feed',side_effect=[FEED,calendar_events.CalendarUnavailable('Offline')])
    def test_temporary_google_failure_uses_last_valid_feed_with_stale_notice(self,fetch):
        endpoint=f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-11'
        first=self.client.get(endpoint).json
        next(iter(calendar_events._cache.values()))['expires']=0
        second=self.client.get(endpoint).json
        third=self.client.get(endpoint).json
        self.assertTrue(second['obsoleto']);self.assertTrue(third['obsoleto'])
        self.assertEqual(first['eventi'],second['eventi']);self.assertEqual(fetch.call_count,2)

    @patch('services.calendar_events.fetch_public_feed',return_value=FEED)
    def test_invalid_dates_and_duplicate_or_unmarked_people_never_write_attendance(self,fetch):
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.group_id}?mese=2026-13').status_code,400)
        for rows,day in [([{'codice_fiscale':self.child_cf,'presente':True}],'not-a-date'),([{'codice_fiscale':self.child_cf,'presente':'false'}],'2026-11-07'),([{'codice_fiscale':self.child_cf,'presente':True}]*2,'2026-11-07')]:
            result=self.client.post('/api/catechismo/presenze',json={'gruppo_id':self.group_id,'data':day,'presenze':rows})
            self.assertEqual(result.status_code,400,result.json)
        with self.app.app_context():self.assertEqual(Presenza.query.count(),0)
