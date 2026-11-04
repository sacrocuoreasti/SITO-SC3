import unittest
from unittest.mock import patch
from sqlalchemy import text,inspect
import test_alpha_family as fixture
from models import db,CalendarioComunita,EventoCalendarioComunita,GruppoCatechismo,DefinizioneAccesso,Utente,init_default_configurazioni
from services.community_calendars import current_pastoral_year


class CalendarEditorTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown
    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self);self.login('admin@example.test')

    def calendar(self,**values):
        data={'titolo':'Calendario locale','tipo':'manuale','google_calendar_url':'','colore':'#2563eb','is_pubblico':True}
        data.update(values)
        result=self.client.post('/api/impostazioni/calendari',json=data)
        self.assertEqual(result.status_code,201,result.json)
        return result.json['calendario']['id']

    def event(self,calendar,**values):
        data={'titolo':'Incontro locale','inizio':'2026-11-04T18:00','fine':'2026-11-04T19:30','luogo':'Salone','tutto_il_giorno':False}
        data.update(values)
        return self.client.post(f'/api/impostazioni/calendari/{calendar}/eventi',json=data)

    def test_manual_event_lifecycle_and_calendar_visibility(self):
        ident=self.calendar()
        event=self.event(ident);self.assertEqual(event.status_code,201,event.json);event_id=event.json['evento']['id']
        source=self.client.get(f'/api/impostazioni/calendari/{ident}/appuntamenti?mese=2026-11').json
        self.assertEqual(source['eventi'][0]['ora'],'18:00')
        self.assertEqual(source['eventi'][0]['giorni'],['2026-11-04'])
        self.assertEqual(self.client.put(f'/api/impostazioni/calendari/{ident}/eventi/{event_id}',json={'titolo':'Titolo modificato'}).status_code,200)
        self.assertEqual(self.client.put(f'/api/impostazioni/calendari/{ident}',json={'is_pubblico':False}).status_code,200)
        self.client.post('/api/auth/logout')
        self.assertNotIn(ident,[c['id'] for c in self.client.get('/api/impostazioni/calendari').json['calendari']])
        self.assertEqual(self.client.get(f'/api/impostazioni/calendari/{ident}/appuntamenti').status_code,404)
        self.login('admin@example.test')
        events=self.client.get(f'/api/impostazioni/calendari/{ident}/eventi').json['eventi']
        self.assertEqual(events[0]['titolo'],'Titolo modificato')
        self.assertEqual(self.client.delete(f'/api/impostazioni/calendari/{ident}/eventi/{event_id}').status_code,200)
        with self.app.app_context():self.assertEqual(EventoCalendarioComunita.query.count(),0)

    def test_invalid_dates_sources_and_colors_do_not_create_records(self):
        ident=self.calendar()
        for data in ({'fine':'2026-11-04T17:00'},{'inizio':'2026-02-30T12:00'},{'inizio':'2026-11-04T18:00Z'},{'tutto_il_giorno':'true'}):
            self.assertEqual(self.event(ident,**data).status_code,400)
        self.assertEqual(self.client.post('/api/impostazioni/calendari',json={'titolo':'Errato','tipo':'google','google_calendar_url':'https://example.com/secret'}).status_code,400)
        self.assertEqual(self.client.put(f'/api/impostazioni/calendari/{ident}',json={'colore':'red;display:none'}).status_code,400)
        with self.app.app_context():self.assertEqual(EventoCalendarioComunita.query.count(),0)

    def test_all_day_spanning_month_boundaries_and_other_calendars_are_isolated(self):
        first=self.calendar();second=self.calendar(titolo='Secondo')
        event=self.event(first,inizio='2026-10-31T00:00',fine='2026-11-03T00:00',tutto_il_giorno=True)
        self.assertEqual(event.status_code,201,event.json)
        events=self.client.get(f'/api/impostazioni/calendari/{first}/appuntamenti?mese=2026-11').json['eventi']
        self.assertEqual(events[0]['giorni'],['2026-10-31','2026-11-01','2026-11-02'])
        self.assertEqual(events[0]['ora'],'')
        self.assertEqual(self.client.delete(f'/api/impostazioni/calendari/{second}/eventi/{event.json["evento"]["id"]}').status_code,404)
        self.login()
        self.assertEqual(self.client.get(f'/api/impostazioni/calendari/{first}/eventi').status_code,403)
        self.assertEqual(self.event(first).status_code,403)
        self.assertEqual(self.client.get(f'/api/impostazioni/calendari/{first}/appuntamenti?mese=2026-11').status_code,200)

    def test_group_calendar_customization_can_be_hidden_without_changing_group_or_register(self):
        year=current_pastoral_year()
        with self.app.app_context():
            group=GruppoCatechismo(nome='Nome originale',anno_pastorale=year,stato='pubblico',google_calendar_url='https://calendar.google.com/calendar/embed?src=group%40example.test')
            db.session.add(group);db.session.commit();group_id=group.id
        origin=f'auto:catechismo:{group_id}'
        ident=self.calendar(titolo='Nome personalizzato',origine_gruppo=origin,is_pubblico=False)
        catalog=self.client.get('/api/impostazioni/calendari').json['calendari']
        entry=next(c for c in catalog if c['id']==ident)
        self.assertEqual(entry['colore'],'#2563eb');self.assertEqual(entry['gruppi_origine'][0]['id'],group_id)
        public=self.client.get('/api/impostazioni/calendari?solo_pubblici=true').json['calendari']
        self.assertNotIn(origin,[c['id'] for c in public]);self.assertNotIn(ident,[c['id'] for c in public])
        self.assertEqual(self.client.post('/api/impostazioni/calendari',json={'titolo':'Duplicato','tipo':'manuale','origine_gruppo':origin}).status_code,400)
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,group_id)
            self.assertEqual(group.nome,'Nome originale');self.assertIn('group%40',group.google_calendar_url)

    def test_google_switch_preserves_existing_manual_events(self):
        ident=self.calendar();self.assertEqual(self.event(ident).status_code,201)
        response=self.client.put(f'/api/impostazioni/calendari/{ident}',json={'tipo':'google','google_calendar_url':'https://calendar.google.com/calendar/embed?src=source%40example.test'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.event(ident).status_code,400)
        self.assertEqual(len(self.client.get(f'/api/impostazioni/calendari/{ident}/eventi').json['eventi']),1)
        self.client.put(f'/api/impostazioni/calendari/{ident}',json={'tipo':'manuale'})
        self.assertEqual(len(self.client.get(f'/api/impostazioni/calendari/{ident}/appuntamenti?mese=2026-11').json['eventi']),1)

    def test_legacy_calendar_schema_is_backed_up_and_extended_without_losing_data(self):
        with self.app.app_context():
            db.session.execute(text('DROP TABLE evento_calendario_comunita'))
            db.session.execute(text('DROP TABLE calendario_comunita'))
            db.session.execute(text('CREATE TABLE calendario_comunita (id INTEGER PRIMARY KEY,titolo VARCHAR(150) NOT NULL,descrizione TEXT,google_calendar_url VARCHAR(500) NOT NULL,colore VARCHAR(30),icona VARCHAR(30),categoria VARCHAR(50),is_pubblico BOOLEAN,ordine INTEGER,created_at DATETIME)'))
            db.session.execute(text("INSERT INTO calendario_comunita(id,titolo,google_calendar_url,colore,is_pubblico) VALUES(41,'Da conservare','https://calendar.google.com/calendar/embed?src=original%40example.test','#123456',1)"));db.session.commit()
            with patch('services.migrations.backup_sqlite',wraps=__import__('services.migrations',fromlist=['backup_sqlite']).backup_sqlite) as backup:
                init_default_configurazioni()
                self.assertIsNotNone(backup.call_args)
            self.assertIn('tipo',{c['name'] for c in inspect(db.engine).get_columns('calendario_comunita')})
            row=db.session.get(CalendarioComunita,41)
            self.assertEqual((row.titolo,row.colore,row.tipo),('Da conservare','#123456','google'))
            self.assertEqual(EventoCalendarioComunita.query.count(),0)

    def test_unused_system_profile_deletion_persists_and_can_be_recreated(self):
        result=self.client.delete('/api/accessi/animatore');self.assertEqual(result.status_code,200,result.json)
        for _ in range(2):self.assertNotIn('animatore',[p['chiave'] for p in self.client.get('/api/accessi').json['profili']])
        with self.app.app_context():self.assertTrue(db.session.get(DefinizioneAccesso,'animatore').eliminato)
        restored=self.client.post('/api/accessi',json={'chiave':'animatore','nome':'Animatore nuovo','tipo':'privilegio','permessi':[]})
        self.assertEqual(restored.status_code,201,restored.json)
        self.assertEqual(restored.json['profilo']['permessi'],[])

    def test_assigned_system_profiles_and_admin_remain_protected(self):
        self.assertEqual(self.client.delete('/api/accessi/admin').status_code,400)
        self.assertEqual(self.client.delete('/api/accessi/utente').status_code,409)
        with self.app.app_context():
            user=db.session.get(Utente,1);user.ruolo='oratorio';db.session.commit()
        self.assertEqual(self.client.delete('/api/accessi/responsabile_oratorio').status_code,409)
        self.login();self.assertEqual(self.client.delete('/api/accessi/animatore').status_code,403)

    def test_page_contains_calendar_management_and_original_logo_is_served(self):
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn('id="modalCalendarEvents"',html)
        self.assertIn('id="inputCalTipo"',html)
        self.assertIn('images/logo-sacro-cuore.png',html)
        logo=self.client.get('/static/images/logo-sacro-cuore.png')
        self.assertEqual(logo.status_code,200)
        self.assertEqual(logo.mimetype,'image/png')
        self.assertTrue(logo.data.startswith(b'\x89PNG'))
