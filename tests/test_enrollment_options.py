import unittest
from datetime import date
import test_alpha_family as family_fixture
from models import db, Persona, Attivita, Iscrizione, GruppoOratorio, GruppoCatechismo, GruppoDoposcuola


class EnrollmentOptionsTests(unittest.TestCase):
    def setUp(self):
        family_fixture.AlphaFamilyTests.setUp(self)
        with self.app.app_context():
            for model in (GruppoOratorio,GruppoCatechismo,GruppoDoposcuola):
                model.query.update({'stato':'chiuso'})
            db.session.commit()
    tearDown=family_fixture.AlphaFamilyTests.tearDown
    login=family_fixture.AlphaFamilyTests.login

    def activity(self, **values):
        self.login('admin@example.test')
        result=self.client.post('/api/attivita',json=dict(titolo='Attività di prova',categoria='evento',is_pubblicato=True,**values))
        self.assertEqual(result.status_code,201,result.json)
        self.login()
        return result.json['attivita']

    def options(self):
        result=self.client.get('/api/famiglie/opportunita')
        self.assertEqual(result.status_code,200,result.json)
        return result.json

    def test_blank_activity_ages_persist_as_unlimited_and_keep_existing_limits(self):
        item=self.activity(eta_min=None,eta_max=None)
        self.assertIsNone(item['eta_min']); self.assertIsNone(item['eta_max'])
        with self.app.app_context():
            model=db.session.get(Attivita,item['id'])
            self.assertIsNone(model.eta_min);self.assertIsNone(model.eta_max)
        self.assertEqual(set(self.options()['attivita'][str(item['id'])]['partecipanti']),{self.head_cf,self.child_cf,self.child2_cf})
        self.login('admin@example.test')
        url='/api/attivita/'+str(item['id'])
        self.assertEqual(self.client.put(url,json={'eta_min':6,'eta_max':16}).status_code,200)
        unchanged=self.client.put(url,json={'descrizione':'Descrizione aggiornata'}).json['attivita']
        self.assertEqual((unchanged['eta_min'],unchanged['eta_max']),(6,16))
        cleared=self.client.put(url,json={'eta_min':'','eta_max':''}).json['attivita']
        self.assertEqual((cleared['eta_min'],cleared['eta_max']),(None,None))
        for invalid in ({'eta_min':15,'eta_max':8},{'eta_min':-1},{'eta_max':True},{'eta_min':2.4}):
            self.assertEqual(self.client.put(url,json=invalid).status_code,400)

    def test_no_limits_accepts_missing_birth_date_but_zero_max_is_enforced(self):
        item=self.activity()
        with self.app.app_context():
            db.session.get(Persona,self.child_cf).data_nascita=None
            db.session.commit()
        self.assertIn(self.child_cf,self.options()['attivita'][str(item['id'])]['partecipanti'])
        self.assertEqual(self.client.post('/api/iscrizioni',json={'attivita_id':item['id'],'partecipanti':[self.child_cf]}).status_code,201)
        baby=self.activity(eta_min=None,eta_max=0)
        self.assertFalse(self.options()['attivita'][str(baby['id'])]['partecipanti'])
        for cf in (self.child_cf,self.child2_cf):
            self.assertEqual(self.client.post('/api/iscrizioni',json={'attivita_id':baby['id'],'partecipanti':[cf]}).status_code,400)
        with self.app.app_context():
            db.session.get(Persona,self.child2_cf).data_nascita=date.today()
            db.session.commit()
        self.assertEqual(self.client.post('/api/iscrizioni',json={'attivita_id':baby['id'],'partecipanti':[self.child2_cf]}).status_code,201)

    def test_activity_opportunities_exclude_enrolled_and_full_activities(self):
        item=self.activity(eta_min=0,eta_max=17)
        ident=str(item['id'])
        self.assertEqual(set(self.options()['attivita'][ident]['partecipanti']),{self.child_cf,self.child2_cf})
        for cf in (self.child_cf,self.child2_cf):
            self.assertEqual(self.client.post('/api/iscrizioni',json={'attivita_id':item['id'],'partecipanti':[cf]}).status_code,201)
            state=self.options()['attivita'][ident]
            self.assertTrue(state['gia_iscritto']); self.assertNotIn(cf,state['partecipanti'])
        self.assertFalse(state['partecipanti'])
        full=self.activity(posti_massimi=1)
        self.assertEqual(self.client.post('/api/iscrizioni',json={'attivita_id':full['id'],'partecipanti':[self.child_cf]}).status_code,201)
        self.assertFalse(self.options()['attivita'][str(full['id'])]['partecipanti'])

    def test_available_groups_and_enrollment_respect_age_and_existing_members(self):
        self.login('admin@example.test')
        with self.app.app_context(): age=db.session.get(Persona,self.child_cf).eta
        for category in ('oratorio','catechismo','doposcuola'):
            root='/api/'+category+'/gruppi'
            result=self.client.post(root,json={'nome':'Gruppo disponibile','eta_min':age,'eta_max':age})
            ident=result.json['gruppo']['id']
            for state in ('bozza','chiuso'):
                self.client.post(root,json={'nome':'Non aperto','stato':state})
            self.client.post(root,json={'nome':'Non idoneo','eta_min':100})
            self.login()
            groups=self.options()['gruppi'][category]
            self.assertEqual([g['id'] for g in groups],[ident])
            self.assertEqual([p['codice_fiscale'] for p in groups[0]['partecipanti']],[self.child_cf])
            payload={'categoria':category,'gruppo_id':ident,'partecipanti':[self.child_cf]}
            self.assertEqual(self.client.post('/api/famiglie/iscrizioni-gruppo',json=payload).status_code,200)
            self.assertFalse(self.options()['gruppi'][category])
            # Retrying is idempotent; it never creates another membership.
            self.assertEqual(self.client.post('/api/famiglie/iscrizioni-gruppo',json=payload).status_code,200)
            self.login('admin@example.test')

    def test_family_group_batch_revalidates_all_members_before_writing(self):
        self.login('admin@example.test')
        group=self.client.post('/api/catechismo/gruppi',json={'nome':'Gruppo test'}).json['gruppo']['id']
        self.login('child@example.test')
        groups=self.options()['gruppi']['catechismo']
        self.assertEqual([p['codice_fiscale'] for p in groups[0]['partecipanti']],[self.child_cf])
        response=self.client.post('/api/famiglie/iscrizioni-gruppo',json={'categoria':'catechismo','gruppo_id':group,'partecipanti':[self.child_cf,self.child2_cf]})
        self.assertEqual(response.status_code,403)
        with self.app.app_context(): self.assertFalse(db.session.get(GruppoCatechismo,group).ragazzi)
        self.login('admin@example.test')
        self.client.put('/api/catechismo/gruppi/'+str(group),json={'stato':'chiuso'})
        self.login()
        response=self.client.post('/api/famiglie/iscrizioni-gruppo',json={'categoria':'catechismo','gruppo_id':group,'partecipanti':[self.child_cf]})
        self.assertEqual(response.status_code,400)
        self.assertFalse(self.options()['gruppi']['catechismo'])

    def test_options_are_private_and_person_without_family_has_no_opportunities(self):
        self.assertEqual(self.app.test_client().get('/api/famiglie/opportunita').status_code,401)
        self.login('admin@example.test')
        self.assertTrue(all(not values for values in self.options()['gruppi'].values()))
