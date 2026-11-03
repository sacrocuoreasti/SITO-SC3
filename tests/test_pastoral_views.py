import json
import unittest
import test_alpha_family as fixture
from models import db, Utente, Persona, GruppoCatechismo, GruppoOratorio, GruppoDoposcuola
from services.access_control import DEFAULTS


class PastoralViewsTests(unittest.TestCase):
    login = fixture.AlphaFamilyTests.login
    tearDown = fixture.AlphaFamilyTests.tearDown

    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        with self.app.app_context():
            user=db.session.get(Utente,1)
            user.privilegi_extra=json.dumps(['catechista'])
            user.persona.ruolo_famiglia='Madre'
            self.foreign_cf=fixture.fiscal_code('BNCLCU14A01H501')
            foreign=Persona(codice_fiscale=self.foreign_cf,nome='Altro',cognome='Iscritto',allergie='Polline',intolleranze_alimentari='Lattosio',terapie_medicinali='Terapia dichiarata')
            db.session.add(foreign)
            own=GruppoCatechismo(nome='Gruppo di mio figlio',stato='pubblico')
            own.ragazzi.append(db.session.get(Persona,self.child_cf))
            staff=GruppoCatechismo(nome='Il gruppo che seguo',catechista_utente_id=user.id,stato='pubblico')
            staff.ragazzi.append(foreign)
            db.session.add_all([own,staff]);db.session.commit()
            self.own_id,self.staff_id=own.id,staff.id

    def test_parent_and_catechist_keep_both_scopes_distinct(self):
        me=self.client.get('/api/auth/me').json['user']
        self.assertEqual(me['ruolo_base'],'utente')
        self.assertIn('catechista',me['privilegi'])
        own=self.client.get('/api/famiglie/registri-gruppi/catechismo').json['gruppi']
        self.assertEqual([g['id'] for g in own],[self.own_id])
        staff=self.client.get('/api/catechismo/gruppi').json['gruppi']
        self.assertEqual([g['id'] for g in staff],[self.staff_id])
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.staff_id}/registro').status_code,200)
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{self.own_id}/registro').status_code,403)

    def test_health_report_is_group_scoped_and_requires_both_permissions(self):
        report=self.client.get(f'/api/calendari-gruppi/catechismo/{self.staff_id}/sanita')
        self.assertEqual(report.status_code,200,report.json)
        self.assertEqual(report.json['conteggi'],{'iscritti':1,'esigenze_alimentari':1,'terapie':1})
        self.assertEqual(report.json['persone'][0]['intolleranze_alimentari'],'Lattosio')
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.own_id}/sanita').status_code,403)
        self.login('admin@example.test')
        grants=set(DEFAULTS['catechista'][2])-{'catechismo.cucina'}
        self.assertEqual(self.client.put('/api/accessi/catechista',json={'permessi':sorted(grants)}).status_code,200)
        self.login()
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.staff_id}/sanita').status_code,403)

    def test_family_membership_does_not_grant_staff_health_access(self):
        with self.app.app_context():
            db.session.get(Utente,1).privilegi_extra='[]';db.session.commit()
        self.assertEqual(self.client.get(f'/api/calendari-gruppi/catechismo/{self.own_id}/sanita').status_code,403)

    def test_report_is_available_for_all_three_categories(self):
        self.login('admin@example.test')
        with self.app.app_context():
            foreign=db.session.get(Persona,self.foreign_cf)
            oratorio=GruppoOratorio(nome='Oratorio test');oratorio.ragazzi.append(foreign)
            dop=GruppoDoposcuola(nome='Doposcuola test');dop.studenti.append(foreign)
            db.session.add_all([oratorio,dop]);db.session.commit()
            ids={'oratorio':oratorio.id,'doposcuola':dop.id,'catechismo':self.staff_id}
        for category,ident in ids.items():
            report=self.client.get(f'/api/calendari-gruppi/{category}/{ident}/sanita')
            self.assertEqual(report.status_code,200,report.json)
            self.assertEqual(report.json['conteggi']['iscritti'],1)

    def test_custom_profile_can_be_renamed_and_deleted_only_when_unassigned(self):
        self.login('admin@example.test')
        for kind in ('ruolo','privilegio'):
            key='profilo_'+kind
            self.assertEqual(self.client.post('/api/accessi',json={'chiave':key,'nome':'Vecchio nome','tipo':kind,'permessi':['dashboard','dashboard.settimana']}).status_code,201)
            renamed=self.client.put('/api/accessi/'+key,json={'nome':'Nome aggiornato'})
            self.assertEqual(renamed.status_code,200)
            self.assertEqual(renamed.json['profilo']['nome'],'Nome aggiornato')
            self.assertEqual(renamed.json['profilo']['permessi'],['dashboard','dashboard.settimana'])
            with self.app.app_context():
                user=db.session.get(Utente,1)
                if kind=='ruolo':user.ruolo=key
                else:user.privilegi_extra=json.dumps([key])
                db.session.commit()
            self.assertEqual(self.client.delete('/api/accessi/'+key).status_code,409)
            with self.app.app_context():
                user=db.session.get(Utente,1);user.ruolo='utente';user.privilegi_extra='[]';db.session.commit()
            self.assertEqual(self.client.delete('/api/accessi/'+key).status_code,200)
            self.assertNotIn(key,[p['chiave'] for p in self.client.get('/api/accessi').json['profili']])
        self.assertEqual(self.client.delete('/api/accessi/admin').status_code,400)
        self.login()
        self.assertEqual(self.client.delete('/api/accessi/catechista').status_code,403)

    def test_existing_staff_account_with_family_keeps_family_capabilities(self):
        with self.app.app_context():
            user=db.session.get(Utente,1);user.ruolo='oratorio';user.privilegi_extra='[]';db.session.commit()
        profile=self.client.get('/api/auth/me').json['user']
        self.assertFalse(profile['is_gestione_pura'])
        self.assertEqual(profile['ruolo_base'],'utente')
        self.assertIn('responsabile_oratorio',profile['privilegi'])
        self.assertEqual(self.client.get('/api/famiglie/mia').json['nucleo']['id'],self.family_id)
