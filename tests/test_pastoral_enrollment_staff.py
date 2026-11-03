import json
import unittest
from concurrent.futures import ThreadPoolExecutor
import test_alpha_family as fixture
from models import db, Persona, Utente, GruppoCatechismo, GruppoDoposcuola


class PastoralEnrollmentStaffTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        with self.app.app_context():
            groups=[GruppoCatechismo(nome=name,anno_pastorale=year,stato='pubblico') for name,year in [('Primo','2026/2027'),('Secondo','2026/2027'),('Anno successivo','2027/2028')]]
            db.session.add_all(groups);db.session.commit();self.group_ids=[g.id for g in groups]

    def enroll(self,group,cfs=None,client=None):
        return (client or self.client).post('/api/famiglie/iscrizioni-gruppo',json={'categoria':'catechismo','gruppo_id':group,'partecipanti':cfs or [self.child_cf]})

    def test_one_group_per_year_and_options_remain_for_other_children_and_years(self):
        first,second,next_year=self.group_ids
        self.assertEqual(self.enroll(first).status_code,200)
        groups=self.client.get('/api/famiglie/opportunita').json['gruppi']['catechismo']
        other=next(g for g in groups if g['id']==second)
        self.assertNotIn(self.child_cf,[p['codice_fiscale'] for p in other['partecipanti']])
        self.assertIn(self.child2_cf,[p['codice_fiscale'] for p in other['partecipanti']])
        self.assertEqual(self.enroll(second).status_code,409)
        self.assertEqual(self.enroll(first).status_code,200)
        self.assertEqual(self.enroll(first,[self.child2_cf]).status_code,200)
        groups=self.client.get('/api/famiglie/opportunita').json['gruppi']['catechismo']
        self.assertEqual([g['id'] for g in groups],[next_year])
        self.assertEqual(self.enroll(next_year).status_code,200)

    def test_legacy_admin_and_batch_paths_cannot_bypass_limit_or_partially_enroll(self):
        first,second,_=self.group_ids
        self.assertEqual(self.enroll(first).status_code,200)
        legacy=self.client.post('/api/catechismo/iscrivi-figlio',json={'gruppo_id':second,'codice_fiscale':self.child_cf})
        self.assertEqual(legacy.status_code,409)
        self.login('admin@example.test')
        self.assertEqual(self.client.post(f'/api/catechismo/gruppi/{second}/ragazzi',json={'codice_fiscale':self.child_cf}).status_code,409)
        response=self.client.post(f'/api/catechismo/gruppi/{second}/ragazzi/batch',json={'codici_fiscali':[self.child2_cf,self.child_cf]})
        self.assertEqual(response.status_code,409,response.json)
        with self.app.app_context():self.assertEqual(db.session.get(GruppoCatechismo,second).ragazzi,[])
        available=self.client.get(f'/api/catechismo/gruppi/{second}/assegnabili').json['persone']
        self.assertNotIn(self.child_cf,[p['codice_fiscale'] for p in available])

    def test_concurrent_enrollments_cannot_create_two_memberships(self):
        clients=[self.app.test_client(),self.app.test_client()]
        for client in clients:self.login(client=client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda pair:self.enroll(pair[1],client=pair[0]).status_code,zip(clients,self.group_ids[:2])))
        self.assertEqual(sorted(results),[200,409])
        with self.app.app_context():self.assertEqual(len(db.session.get(Persona,self.child_cf).gruppi_catechismo),1)

    def test_changing_year_cannot_introduce_conflicts_and_existing_data_is_not_removed(self):
        first,second,next_year=self.group_ids
        self.assertEqual(self.enroll(first).status_code,200)
        self.assertEqual(self.enroll(next_year).status_code,200)
        self.login('admin@example.test')
        response=self.client.put(f'/api/catechismo/gruppi/{next_year}',json={'anno_pastorale':'2026/2027'})
        self.assertEqual(response.status_code,409,response.json)
        with self.app.app_context():
            self.assertEqual(db.session.get(GruppoCatechismo,next_year).anno_pastorale,'2027/2028')
            # Simula una doppia iscrizione preesistente: il deploy non la cancella.
            previous=db.session.get(GruppoCatechismo,second)
            previous.ragazzi.append(db.session.get(Persona,self.child_cf));db.session.commit()
        self.assertEqual(self.client.put(f'/api/catechismo/gruppi/{second}',json={'note':'Nota aggiornata'}).status_code,200)
        with self.app.app_context():self.assertEqual(len(db.session.get(Persona,self.child_cf).gruppi_catechismo),3)

    def educators(self):
        with self.app.app_context():
            users=[]
            for i in range(2):
                user=Utente(email=f'educator{i}@example.test',ruolo='utente',privilegi_extra=json.dumps(['educatore']))
                user.set_password('password-test-123');db.session.add(user);users.append(user)
            db.session.commit();return [u.id for u in users]

    def test_multiple_educators_can_record_and_removed_educator_loses_access(self):
        ids=self.educators();self.login('admin@example.test')
        response=self.client.post('/api/doposcuola/gruppi',json={'nome':'Gruppo condiviso','educatori_ids':ids})
        self.assertEqual(response.status_code,201,response.json)
        group_id=response.json['gruppo']['id']
        self.assertEqual(set(response.json['gruppo']['educatori_ids']),set(ids))
        for i in range(2):
            self.login(f'educator{i}@example.test')
            self.assertIn(group_id,[g['id'] for g in self.client.get('/api/doposcuola/gruppi').json['gruppi']])
            self.assertEqual(self.client.get(f'/api/calendari-gruppi/doposcuola/{group_id}/registro').status_code,200)
        self.login('admin@example.test')
        self.assertEqual(self.client.put(f'/api/doposcuola/gruppi/{group_id}',json={'educatori_ids':[ids[1]]}).status_code,200)
        self.login('educator0@example.test')
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/doposcuola/{group_id}/registro').status_code,403)

    def test_existing_educator_is_preserved_when_assignment_is_omitted(self):
        ids=self.educators();self.login('admin@example.test')
        with self.app.app_context():
            group=GruppoDoposcuola(nome='Gruppo precedente',educatore_utente_id=ids[0],educatore_nome='Nome precedente')
            db.session.add(group);db.session.commit();ident=group.id
        result=self.client.put(f'/api/doposcuola/gruppi/{ident}',json={'nome':'Nome aggiornato'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['gruppo']['educatori_ids'],[ids[0]])
        with self.app.app_context():self.assertEqual(db.session.get(GruppoDoposcuola,ident).educatore_nome,'Nome precedente')
        invalid=self.client.put(f'/api/doposcuola/gruppi/{ident}',json={'educatori_ids':[1,9999]})
        self.assertEqual(invalid.status_code,400)
        with self.app.app_context():self.assertEqual(db.session.get(GruppoDoposcuola,ident).educatore_utente_id,ids[0])

    def test_six_menu_entries_use_separate_staff_and_family_panels(self):
        from html.parser import HTMLParser
        from pathlib import Path
        class Panels(HTMLParser):
            def __init__(self):
                super().__init__();self.sections=[];self.locations={};self.links=[]
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='section':self.sections.append(attrs.get('id'))
                if attrs.get('id'):self.locations[attrs['id']]=list(self.sections)
                if tag=='a' and attrs.get('data-view'):self.links.append(attrs['data-view'])
            def handle_endtag(self,tag):
                if tag=='section':self.sections.pop()
        parsed=Panels();parsed.feed((Path(__file__).resolve().parents[1]/'templates/index.html').read_text())
        for category,cap in [('oratorio','Oratorio'),('catechismo','Catechismo'),('doposcuola','Doposcuola')]:
            self.assertEqual(parsed.links.count(category),1)
            self.assertEqual(parsed.links.count(category+'_staff'),1)
            self.assertIn('view'+cap,parsed.locations[category+'ParentSection'])
            self.assertNotIn('view'+cap,parsed.locations[category+'StaffSection'])
            self.assertIn('view'+cap+'Staff',parsed.locations[category+'StaffSection'])
