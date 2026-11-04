import unittest,json
from unittest.mock import patch
import test_alpha_family as fixture
from models import db,Utente,Persona,GruppoCatechismo,DefinizioneAccesso
from services.access_control import DEFAULTS,raw_roles


class AccessControlTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown
    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self)
        self.login('admin@example.test')

    def edit(self,key,permissions):
        return self.client.put('/api/accessi/'+key,json={'permessi':permissions})

    def user_profile(self,role='utente',extras=None):
        with self.app.app_context():
            user=Utente.query.filter_by(email='head@example.test').one();user.ruolo=role;user.privilegi_extra=json.dumps(extras or []);db.session.commit()
        self.login()

    def test_default_profiles_are_not_seeded_and_legacy_roles_are_interpreted_without_rewriting_accounts(self):
        with self.app.app_context():self.assertEqual(DefinizioneAccesso.query.count(),0)
        self.user_profile('catechista')
        data=self.client.get('/api/auth/me').json['user']
        self.assertEqual(data['ruolo_base'],'utente');self.assertIn('catechista',data['privilegi'])
        self.assertIn('catechismo.staff',data['permessi'])
        with self.app.app_context():self.assertEqual(Utente.query.filter_by(email='head@example.test').one().ruolo,'catechista')

    def test_admin_cannot_be_disabled_and_configuration_is_admin_only(self):
        self.assertEqual(self.client.get('/api/accessi').status_code,200)
        self.assertEqual(self.edit('admin',[]).status_code,400)
        self.assertEqual(self.client.put('/api/utenti/3/ruoli',json={'ruolo':'utente','privilegi':[]}).status_code,400)
        self.user_profile('segreteria')
        self.assertEqual(self.client.get('/api/accessi').status_code,403)
        self.assertEqual(self.client.put('/api/accessi/utente',json={'permessi':[]}).status_code,403)
        self.assertEqual(self.client.put('/api/utenti/1/ruoli',json={'ruolo':'admin','privilegi':[]}).status_code,403)

    def test_disabling_menu_denies_direct_api_and_new_role_allows_only_selected_functions(self):
        created=self.client.post('/api/accessi',json={'chiave':'referente_test','nome':'Referente test','tipo':'ruolo','permessi':['dashboard','attivita','attivita.catalogo']})
        self.assertEqual(created.status_code,201,created.json)
        self.user_profile('referente_test')
        grants=self.client.get('/api/auth/me').json['user']['permessi']
        self.assertIn('attivita.catalogo',grants);self.assertNotIn('segreteria',grants)
        for path in ('/api/persone','/api/utenti','/api/famiglie/mia','/api/excel/export-anagrafica'):
            self.assertEqual(self.client.get(path).status_code,403,path)
        self.assertEqual(self.client.post('/api/attivita',json={'titolo':'Non autorizzato'}).status_code,403)

    def test_role_and_privilege_union_can_disable_appelli_independently(self):
        grants=set(DEFAULTS['catechista'][2]);grants.remove('catechismo.appelli')
        self.assertEqual(self.edit('catechista',sorted(grants)).status_code,200)
        with self.app.app_context():
            user=Utente.query.filter_by(email='head@example.test').one();group=GruppoCatechismo(nome='Assegnato',catechista_utente_id=user.id);db.session.add(group);db.session.commit();group_id=group.id
        self.user_profile('utente',['catechista'])
        data=self.client.get('/api/auth/me').json['user'];self.assertIn('famiglia',data['permessi']);self.assertNotIn('catechismo.appelli',data['permessi'])
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{group_id}/allergie').status_code,200)
        self.assertEqual(self.client.get(f'/api/catechismo/gruppi/{group_id}/registro').status_code,403)
        self.assertEqual(self.client.post('/api/catechismo/presenze',json={'gruppo_id':group_id,'data':'2026-11-07','presenze':[]}).status_code,403)

    def test_health_disabled_hides_payload_and_cannot_overwrite_stored_health_fields(self):
        grants=set(DEFAULTS['utente'][2]);grants.remove('famiglia.salute')
        self.assertEqual(self.edit('utente',sorted(grants)).status_code,200)
        self.user_profile()
        response=self.client.get('/api/famiglie/mia')
        self.assertNotIn('allergie',response.json['nucleo']['componenti'][0])
        response=self.client.put('/api/persone/'+self.head_cf,json={'allergie':'Cambio non autorizzato'})
        self.assertEqual(response.status_code,200,response.json)
        with self.app.app_context():self.assertEqual(db.session.get(Persona,self.head_cf).allergie,'Nota sanitaria precedente')

    def test_invalid_profiles_and_permissions_never_persist(self):
        for data in [ {'chiave':'bad key','nome':'Nome','tipo':'ruolo','permessi':[]}, {'chiave':'valido','nome':'Nome','tipo':'ruolo','permessi':['inesistente']}, {'chiave':'valido','nome':'Nome','tipo':'ruolo','permessi':['oratorio.appelli']} ]:
            self.assertEqual(self.client.post('/api/accessi',json=data).status_code,400)
        with self.app.app_context():self.assertEqual(DefinizioneAccesso.query.count(),0)

    def test_custom_privilege_can_be_assigned_and_unassigned_and_user_remains_family_scoped(self):
        created=self.client.post('/api/accessi',json={'chiave':'accompagnatore','nome':'Accompagnatore','tipo':'privilegio','permessi':['calendari','calendari.comunita']})
        self.assertEqual(created.status_code,201)
        response=self.client.put('/api/utenti/1/ruoli',json={'ruolo':'utente','privilegi':['accompagnatore']})
        self.assertEqual(response.status_code,200,response.json)
        self.login();data=self.client.get('/api/auth/me').json['user'];self.assertIn('accompagnatore',data['privilegi'])
        self.assertEqual(self.client.get('/api/utenti').status_code,403)
        self.assertEqual(self.client.get('/api/accessi').status_code,403)

    def test_disabled_secretariat_submenu_is_rejected_even_for_secretariat_role(self):
        grants=set(DEFAULTS['segreteria'][2]);grants.remove('segreteria.homepage')
        self.assertEqual(self.edit('segreteria',sorted(grants)).status_code,200)
        self.user_profile('segreteria')
        self.assertEqual(self.client.put('/api/impostazioni/homepage',json={'titolo':'Non autorizzato'}).status_code,403)
        self.assertEqual(self.client.get('/api/utenti').status_code,200)

    def test_disabling_role_views_takes_effect_on_next_request_without_changing_existing_users(self):
        self.assertEqual(self.edit('utente',[]).status_code,200)
        self.user_profile()
        self.assertEqual(self.client.get('/api/auth/me').json['user']['permessi'],[])
        self.assertEqual(self.client.get('/api/famiglie/mia').status_code,403)
        self.assertEqual(self.client.post('/api/auth/logout').status_code,200)

    def test_exports_do_not_bypass_disabled_health_and_bulk_assignment_preserves_legacy_admin(self):
        import io,openpyxl
        grants=set(DEFAULTS['segreteria'][2]);grants.remove('anagrafica.salute')
        self.assertEqual(self.edit('segreteria',sorted(grants)).status_code,200)
        self.user_profile('segreteria')
        response=self.client.get('/api/excel/export-anagrafica')
        self.assertEqual(response.status_code,200)
        book=openpyxl.load_workbook(io.BytesIO(response.data))
        headers=[cell.value for cell in book.active[1]]
        health_columns=[headers.index(label) for label in ('Allergie','Intolleranze Alimentari','Terapie e medicinali','Note')]
        self.assertTrue(all(not row[column].value for row in list(book.active.rows)[1:] for column in health_columns))
        self.login('admin@example.test')
        with self.app.app_context():
            user=Utente.query.filter_by(email='head@example.test').one();user.ruolo='utente';user.privilegi_extra='["admin"]';db.session.commit()
        result=self.client.post('/api/utenti/bulk-privilegi',json={'ids':[1],'azione':'aggiungi','ruolo':'catechista'})
        self.assertEqual(result.status_code,200,result.json)
        with self.app.app_context():self.assertIn('admin',raw_roles(db.session.get(Utente,1)))

    def test_custom_catechism_manager_can_see_all_groups_and_management_controls(self):
        result=self.client.post('/api/accessi',json={'chiave':'coordinatore','nome':'Coordinatore','tipo':'privilegio','permessi':['catechismo','catechismo.staff','catechismo.gestione','catechismo.tutti','catechismo.genitori']})
        self.assertEqual(result.status_code,201)
        with self.app.app_context():
            db.session.add(GruppoCatechismo(nome='Gruppo senza assegnazione'));db.session.commit()
        self.user_profile('utente',['coordinatore'])
        result=self.client.get('/api/catechismo/gruppi')
        self.assertEqual(result.status_code,200,result.json)
        self.assertTrue(any(g['nome']=='Gruppo senza assegnazione' for g in result.json['gruppi']))
        self.assertFalse(result.json['is_catechista_only'])
