import json
import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
import test_alpha_family as fixture
from models import db,Persona,Utente,NucleoFamiliare,GruppoGiovani,GruppoCatechismo,AvvisoGruppo
from services.access_control import DEFAULTS
from services.community_calendars import current_pastoral_year


class YouthBoardsTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        self.login('admin@example.test')

    def create_youth(self,name='Gruppo giovani',year=None,client=None):
        return (client or self.client).post('/api/giovani/gruppi',json={'nome':name,'anno_pastorale':year or current_pastoral_year(),'catechisti_ids':[3]})

    def test_only_two_youth_groups_per_year_including_year_changes(self):
        self.assertEqual(self.create_youth('Anno non valido','2026/2028').status_code,400)
        first=self.create_youth('Primo');second=self.create_youth('Secondo')
        self.assertEqual(first.status_code,201,first.json);self.assertEqual(second.status_code,201,second.json)
        self.assertEqual(self.create_youth('Terzo').status_code,409)
        year=current_pastoral_year();start=int(year[:4]);future=f'{start+1}/{start+2}'
        following=self.create_youth('Altro anno',future)
        self.assertEqual(following.status_code,201)
        ident=following.json['gruppo']['id']
        self.assertEqual(self.client.put('/api/giovani/gruppi/'+str(ident),json={'anno_pastorale':year}).status_code,409)
        with self.app.app_context():self.assertEqual(db.session.get(GruppoGiovani,ident).anno_pastorale,future)

    def test_concurrent_creation_keeps_two_slots(self):
        self.assertEqual(self.create_youth('Esistente').status_code,201)
        clients=[self.app.test_client(),self.app.test_client()]
        for client in clients:self.login('admin@example.test',client=client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda args:self.create_youth(args[1],client=args[0]).status_code,zip(clients,['Nuovo A','Nuovo B'])))
        self.assertEqual(sorted(codes),[201,409])
        with self.app.app_context():self.assertEqual(GruppoGiovani.query.count(),2)

    def test_young_family_head_can_enroll_self_and_get_private_group_board(self):
        response=self.create_youth();ident=response.json['gruppo']['id']
        self.assertEqual(self.client.post(f'/api/bacheche/giovani/{ident}',json={'titolo':'Incontro giovani','contenuto':'Ci incontriamo sabato','argomento':'Incontri'}).status_code,201)
        with self.app.app_context():
            cf=fixture.fiscal_code('RSSMRA08A01H501')
            person=Persona(codice_fiscale=cf,nome='Giovane',cognome='Test',ruolo_famiglia='Figlio/a',data_nascita=date(2008,1,1));db.session.add(person);db.session.flush()
            family=NucleoFamiliare(nome_famiglia='Nucleo giovane',codice_fiscale_capofamiglia=cf);db.session.add(family);db.session.flush();person.nucleo_id=family.id
            user=Utente(email='young@example.test',codice_fiscale=cf,ruolo='utente');user.set_password('password-test-123');db.session.add(user);db.session.commit()
        self.login('young@example.test')
        self.assertEqual(self.client.get(f'/api/bacheche/giovani/{ident}').status_code,403)
        available=self.client.get('/api/famiglie/opportunita').json['gruppi']['giovani']
        self.assertIn(cf,[p['codice_fiscale'] for g in available for p in g['partecipanti']])
        enrolled=self.client.post('/api/famiglie/iscrizioni-gruppo',json={'categoria':'giovani','gruppo_id':ident,'partecipanti':[cf]})
        self.assertEqual(enrolled.status_code,200,enrolled.json)
        self.assertEqual(self.client.get(f'/api/bacheche/giovani/{ident}').status_code,200)
        self.assertEqual(self.client.post(f'/api/bacheche/giovani/{ident}',json={'titolo':'No','contenuto':'No'}).status_code,403)
        registers=self.client.get('/api/famiglie/registri-gruppi/giovani').json['gruppi']
        self.assertEqual([g['id'] for g in registers],[ident])
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/giovani/{ident}/registro').status_code,403)

    def test_youth_staff_can_only_read_and_record_assigned_groups(self):
        first=self.create_youth('Primo').json['gruppo']['id'];second=self.create_youth('Secondo').json['gruppo']['id']
        with self.app.app_context():
            user=db.session.get(Utente,1);user.privilegi_extra=json.dumps(['responsabile_giovani'])
            group=db.session.get(GruppoGiovani,first);group.catechisti.append(user);group.ragazzi.append(db.session.get(Persona,self.child_cf));db.session.commit()
        self.login()
        self.assertEqual([g['id'] for g in self.client.get('/api/giovani/gruppi').json['gruppi']],[first])
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/giovani/{second}/registro').status_code,403)
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/giovani/{first}/registro').status_code,200)
        saved=self.client.post(f'/api/calendari-gruppi/giovani/{first}/registro',json={'data':'2026-11-04','presenze':[{'codice_fiscale':self.child_cf,'presente':True}]})
        self.assertEqual(saved.status_code,200,saved.json)
        self.assertEqual(self.client.post('/api/giovani/gruppi',json={'nome':'Non autorizzato'}).status_code,403)

    def setup_boards(self):
        with self.app.app_context():
            head=db.session.get(Utente,1);head.privilegi_extra=json.dumps(['catechista'])
            own=GruppoCatechismo(nome='Gruppo del figlio');own.ragazzi.append(db.session.get(Persona,self.child_cf))
            staff=GruppoCatechismo(nome='Gruppo del catechista',catechista_utente_id=head.id)
            other=GruppoCatechismo(nome='Gruppo estraneo')
            db.session.add_all([own,staff,other]);db.session.commit();return own.id,staff.id,other.id

    def publish(self,ident,title,published=True):
        response=self.client.post(f'/api/bacheche/catechismo/{ident}',json={'titolo':title,'contenuto':'Messaggio del gruppo','argomento':'Organizzazione','is_pubblicato':published})
        self.assertEqual(response.status_code,201,response.json);return response.json['avviso']['id']

    def test_boards_and_overview_filter_membership_assignments_and_drafts(self):
        own,staff,other=self.setup_boards()
        self.publish(own,'Per la famiglia');self.publish(staff,'Per lo staff');self.publish(staff,'Bozza dello staff',False);self.publish(own,'Bozza non visibile',False);self.publish(other,'Avviso estraneo')
        self.login()
        response=self.client.get('/api/bacheche');self.assertEqual(response.status_code,200,response.json)
        self.assertEqual({n['titolo'] for n in response.json['avvisi']},{'Per la famiglia','Per lo staff','Bozza dello staff'})
        groups={g['id']:g for g in response.json['gruppi'] if g['categoria']=='catechismo'}
        self.assertEqual(groups[own]['ambiti'],['famiglia']);self.assertEqual(groups[staff]['ambiti'],['staff'])
        self.assertEqual(self.client.get(f'/api/bacheche/catechismo/{other}').status_code,403)
        self.assertEqual(self.client.post(f'/api/bacheche/catechismo/{own}',json={'titolo':'No','contenuto':'No'}).status_code,403)
        public=self.client.get('/api/impostazioni/dati-pubblici').json['avvisi']
        self.assertFalse(any(n['titolo'] in {'Per la famiglia','Per lo staff','Avviso estraneo'} for n in public))

    def test_staff_notice_edit_and_delete_cannot_cross_group_boundaries(self):
        own,staff,other=self.setup_boards();foreign=self.publish(other,'Estraneo');notice=self.publish(staff,'Gestibile')
        self.login()
        self.assertEqual(self.client.put(f'/api/bacheche/avvisi/{foreign}',json={'titolo':'Cambio'}).status_code,403)
        self.assertEqual(self.client.delete(f'/api/bacheche/avvisi/{foreign}').status_code,403)
        self.assertEqual(self.client.put(f'/api/bacheche/avvisi/{notice}',json={'titolo':'Aggiornato'}).status_code,200)
        self.assertEqual(self.client.delete(f'/api/bacheche/avvisi/{notice}').status_code,200)
        with self.app.app_context():self.assertEqual(db.session.get(AvvisoGruppo,foreign).titolo,'Estraneo')

    def test_same_group_in_both_scopes_is_not_duplicated_and_permission_revocation_applies(self):
        own,_,_=self.setup_boards();notice=self.publish(own,'Unico avviso')
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,own);group.catechisti.append(db.session.get(Utente,1));db.session.commit()
        self.login();rows=self.client.get('/api/bacheche').json['avvisi']
        self.assertEqual(sum(n['id']==notice for n in rows),1)
        self.assertEqual(next(n for n in rows if n['id']==notice)['ambiti'],['famiglia','staff'])
        self.login('admin@example.test')
        for profile in ('utente','catechista'):
            grants=sorted(set(DEFAULTS[profile][2])-{'catechismo.bacheca'})
            self.assertEqual(self.client.put('/api/accessi/'+profile,json={'permessi':grants}).status_code,200)
        self.login()
        self.assertEqual(self.client.get(f'/api/bacheche/catechismo/{own}').status_code,403)
        self.assertEqual(self.client.get('/api/bacheche').json['avvisi'],[])

    def test_anonymous_board_access_is_denied(self):
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/bacheche').status_code,401)
        self.assertEqual(self.client.get('/api/bacheche/catechismo/1').status_code,401)

    def test_overview_uses_bounded_previews_without_truncating_stored_notices(self):
        own,_,_=self.setup_boards()
        text='Messaggio lungo '*300
        response=self.client.post(f'/api/bacheche/catechismo/{own}',json={'titolo':'Avviso lungo','contenuto':text})
        self.assertEqual(response.status_code,201)
        ident=response.json['avviso']['id']
        self.login()
        row=next(n for n in self.client.get('/api/bacheche').json['avvisi'] if n['id']==ident)
        self.assertEqual(len(row['contenuto']),1000);self.assertTrue(row['anteprima'])
        full=self.client.get(f'/api/bacheche/catechismo/{own}').json['avvisi'][0]
        self.assertEqual(full['contenuto'],text.strip());self.assertFalse(full['anteprima'])
