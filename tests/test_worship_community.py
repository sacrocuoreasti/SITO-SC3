import unittest
from datetime import date
from unittest.mock import patch
import test_alpha_family as fixture
from models import db,Celebrazione,NotiziaEvento,CalendarioComunita,GruppoCatechismo,GruppoOratorio,GruppoDoposcuola,Persona,Utente
from services.community_calendars import current_pastoral_year,calendar_catalog


class WorshipCommunityTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        self.login('admin@example.test')

    def test_dated_occurrence_and_all_sections_are_available_in_dashboard_source(self):
        for section in ('messe','liturgia','avvenimenti'):
            data={'sezione':section,'titolo':'Prova '+section,'giorno':'Mercoledì','orario':'18:00'}
            if section=='avvenimenti':data['data_specifica']='2026-11-04'
            response=self.client.post('/api/celebrazioni',json=data)
            self.assertEqual(response.status_code,201,response.json)
            if section=='avvenimenti':
                self.assertEqual(response.json['celebrazione']['data_specifica'],'2026-11-04')
                self.assertEqual(response.json['celebrazione']['giorno'],'')
        self.login()
        source=self.client.get('/api/impostazioni/dati-pubblici').json['celebrazioni']
        self.assertTrue({'messe','liturgia','avvenimenti'}.issubset({c['sezione'] for c in source}))

    def test_invalid_occurrence_dates_are_rejected_without_creating_records(self):
        with self.app.app_context():before=Celebrazione.query.count()
        for value in (None,'','2026-02-30','04/11/2026',123):
            response=self.client.post('/api/celebrazioni',json={'titolo':'Data non valida','sezione':'avvenimenti','data_specifica':value})
            self.assertEqual(response.status_code,400,response.json)
        with self.app.app_context():self.assertEqual(Celebrazione.query.count(),before)

    def test_legacy_weekday_occurrence_is_not_rewritten_when_updating_description(self):
        with self.app.app_context():
            record=Celebrazione(titolo='Avvenimento precedente',sezione='avvenimenti',giorno='Domenica',orario='11:00');db.session.add(record);db.session.commit();ident=record.id
        response=self.client.put('/api/celebrazioni/'+str(ident),json={'descrizione':'Descrizione aggiornata'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['celebrazione']['giorno'],'Domenica')
        self.assertIsNone(response.json['celebrazione']['data_specifica'])

    def test_worship_operator_can_publish_notice_without_homepage_management_permission(self):
        response=self.client.post('/api/accessi',json={'chiave':'operatore_liturgia','nome':'Operatore liturgia','tipo':'ruolo','permessi':['segreteria','segreteria.celebrazioni']})
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.client.put('/api/utenti/1/ruoli',json={'ruolo':'operatore_liturgia','privilegi':[]}).status_code,200)
        self.login()
        data={'titolo':'Avviso della comunità','contenuto':'Incontro aperto a tutti','data_evento':'2026-11-04','is_pubblicato':True}
        self.assertEqual(self.client.post('/api/impostazioni/eventi',json=data).status_code,403)
        result=self.client.post('/api/celebrazioni/avvisi',json=data)
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(result.json['avviso']['data_evento_iso'],'2026-11-04')
        self.assertEqual(result.json['avviso']['data_evento'],'04/11/2026')
        source=self.client.get('/api/impostazioni/dati-pubblici').json['avvisi']
        self.assertIn('Avviso della comunità',[n['titolo'] for n in source])

    def test_draft_notice_is_hidden_and_ordinary_users_cannot_publish(self):
        self.assertEqual(self.client.post('/api/celebrazioni/avvisi',json={'titolo':'Bozza riservata','contenuto':'Contenuto','is_pubblicato':False}).status_code,201)
        self.assertEqual(self.client.post('/api/celebrazioni/avvisi',json={'titolo':'Data errata','contenuto':'Contenuto','data_evento':'2026-02-30'}).status_code,400)
        self.login()
        self.assertNotIn('Bozza riservata',[n['titolo'] for n in self.client.get('/api/impostazioni/dati-pubblici').json['avvisi']])
        self.assertNotIn('Bozza riservata',[n['titolo'] for n in self.client.get('/api/celebrazioni').json['avvisi']])
        self.assertEqual(self.client.post('/api/celebrazioni/avvisi',json={'titolo':'Non autorizzato','contenuto':'Testo'}).status_code,403)

    def calendar_groups(self):
        year=current_pastoral_year();first=int(year[:4]);past=f'{first-1}/{first}'
        with self.app.app_context():
            self.initial_calendar_count=CalendarioComunita.query.count()
            self.initial_public_calendar_count=len(calendar_catalog())
            cate=GruppoCatechismo(nome='Catechismo corrente',anno_pastorale=year,google_calendar_url='https://calendar.google.com/calendar/embed?src=cate%40example.test',stato='pubblico')
            oratorio=GruppoOratorio(nome='Oratorio corrente',anno_pastorale=year,google_calendar_url='https://calendar.google.com/calendar/embed?src=orat%40example.test',stato='pubblico')
            dop=GruppoDoposcuola(nome='Doposcuola corrente',anno_scolastico=year,google_calendar_url='https://calendar.google.com/calendar/embed?src=dopo%40example.test',stato='pubblico')
            old=GruppoCatechismo(nome='Gruppo passato',anno_pastorale=past,google_calendar_url='https://calendar.google.com/calendar/embed?src=past%40example.test',stato='pubblico')
            draft=GruppoCatechismo(nome='Gruppo in bozza',anno_pastorale=year,google_calendar_url='https://calendar.google.com/calendar/embed?src=draft%40example.test',stato='bozza')
            cate.ragazzi.append(db.session.get(Persona,self.child_cf))
            manual=CalendarioComunita(titolo='Calendario manuale esistente',google_calendar_url='https://calendar.google.com/calendar/embed?src=cate%40example.test',is_pubblico=True)
            db.session.add_all([cate,oratorio,dop,old,draft,manual]);db.session.commit()
            return cate.id,old.id,draft.id

    def test_current_year_group_calendars_are_automatic_deduplicated_and_do_not_create_rows(self):
        self.calendar_groups();self.login()
        response=self.client.get('/api/impostazioni/calendari?solo_pubblici=true')
        self.assertEqual(response.status_code,200)
        calendars=response.json['calendari']
        self.assertEqual(len(calendars),self.initial_public_calendar_count+3)
        self.assertTrue({'oratorio','doposcuola'}.issubset({c['categoria'] for c in calendars}))
        self.assertEqual(sum('cate%40' in c['google_calendar_url'] for c in calendars),1)
        self.assertNotIn('Gruppo passato',[c['titolo'] for c in calendars])
        self.assertNotIn('Gruppo in bozza',[c['titolo'] for c in calendars])
        with self.app.app_context():self.assertEqual(CalendarioComunita.query.count(),self.initial_calendar_count+1)
        self.assertEqual(len(self.client.get('/api/impostazioni/dati-pubblici').json['calendari']),self.initial_public_calendar_count+3)

    @patch('services.calendar_events.group_events')
    def test_public_month_contains_appointments_only_and_rejects_private_or_past_groups(self,events):
        events.return_value={'eventi':[{'data':'2026-11-04','titolo':'Appuntamento pubblico'}],'mese':'2026-11','configurato':True}
        cate,old,draft=self.calendar_groups()
        self.client.post('/api/auth/logout')
        result=self.client.get(f'/api/impostazioni/calendari-gruppi/catechismo/{cate}?mese=2026-11')
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['presenze'],[])
        self.assertFalse(result.json['puo_registrare_presenze'])
        self.assertNotIn(self.child_cf,result.get_data(as_text=True))
        for ident in (old,draft):self.assertEqual(self.client.get(f'/api/impostazioni/calendari-gruppi/catechismo/{ident}').status_code,404)

    def test_pastoral_year_changes_on_september_first(self):
        self.assertEqual(current_pastoral_year(date(2026,8,31)),'2025/2026')
        self.assertEqual(current_pastoral_year(date(2026,9,1)),'2026/2027')
        self.assertEqual(current_pastoral_year(date(2027,1,1)),'2026/2027')

    @patch('services.calendar_events.cached_calendar')
    @patch('services.calendar_events.expand_events')
    def test_manual_public_calendar_events_and_private_calendar_privacy(self,expand,cached):
        cached.return_value=(object(),True)
        expand.return_value=[{'id':'test','titolo':'Appuntamento', 'giorni':['2026-11-04']}]
        with self.app.app_context():
            public=CalendarioComunita(titolo='Pubblico',google_calendar_url='https://calendar.google.com/calendar/embed?src=public%40example.test',is_pubblico=True)
            private=CalendarioComunita(titolo='Privato',google_calendar_url='https://calendar.google.com/calendar/embed?src=private%40example.test',is_pubblico=False)
            db.session.add_all([public,private]);db.session.commit();public_id,private_id=public.id,private.id
        self.client.post('/api/auth/logout')
        response=self.client.get(f'/api/impostazioni/calendari/{public_id}/appuntamenti?mese=2026-11')
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(response.json['obsoleto'])
        self.assertEqual(response.json['eventi'][0]['titolo'],'Appuntamento')
        self.assertNotIn('presenze',response.json)
        cached.assert_called_once_with('public@example.test')
        self.assertEqual(self.client.get(f'/api/impostazioni/calendari/{private_id}/appuntamenti?mese=2026-11').status_code,404)
        self.assertEqual(self.client.get(f'/api/impostazioni/calendari/{public_id}/appuntamenti?mese=2026-99').status_code,400)
        self.assertEqual(cached.call_count,1)

    @patch('services.calendar_events.cached_calendar')
    def test_manual_calendar_feed_failure_is_recoverable(self,cached):
        from services.calendar_events import CalendarUnavailable
        cached.side_effect=CalendarUnavailable('Calendario non leggibile')
        with self.app.app_context():
            record=CalendarioComunita(titolo='Temporaneamente offline',google_calendar_url='https://calendar.google.com/calendar/embed?src=offline%40example.test',is_pubblico=True)
            db.session.add(record);db.session.commit();ident=record.id
        result=self.client.get(f'/api/impostazioni/calendari/{ident}/appuntamenti?mese=2026-11')
        self.assertEqual(result.status_code,502,result.json)
        self.assertEqual(result.json['error'],'Calendario non leggibile')
