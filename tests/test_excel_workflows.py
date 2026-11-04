import csv,io,json,re,unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from sqlalchemy import text
import openpyxl
import test_alpha_family as fixture
from models import db,Persona,NucleoFamiliare,GruppoCatechismo,GruppoDoposcuola,GruppoOratorio,GruppoGiovani,ProgressivoGruppo,init_default_configurazioni
from services.excel_service import workbook_stream,EXCEL_HEADERS


class ExcelWorkflowTests(unittest.TestCase):
    login=fixture.AlphaFamilyTests.login
    tearDown=fixture.AlphaFamilyTests.tearDown
    def setUp(self):
        fixture.AlphaFamilyTests.setUp(self);self.login('admin@example.test')

    def upload(self,headers,rows,tipo='anagrafica',csv_file=False):
        if csv_file:
            output=io.StringIO();writer=csv.writer(output,delimiter=';');writer.writerow(headers);writer.writerows(rows)
            stream=io.BytesIO(output.getvalue().encode('utf-8-sig'));name='import.csv'
        else:stream=workbook_stream(headers,rows);name='import.xlsx'
        return self.client.post('/api/excel/import',data={'tipo':tipo,'file':(stream,name)},content_type='multipart/form-data')

    def group(self,model=GruppoCatechismo,**values):
        with self.app.app_context():
            group=model(nome='Gruppo test',**values);db.session.add(group);db.session.commit()
            return group.id,group.codice_gruppo

    def test_full_anagraphic_roundtrip_with_family_and_declared_documents(self):
        cf=fixture.fiscal_code('VRDLGI10A01H501')
        headers=['Codice Fiscale','Nome','Cognome','Data Nascita','Sesso','Luogo Nascita','Provincia Nascita','Indirizzo Residenza','Civico','CAP','Comune Residenza','Provincia Residenza','Email','Cellulare','Codice Famiglia','Capofamiglia','Ruolo Famiglia','Allergie','Intolleranze Alimentari','Terapie e medicinali','Note','Numero documento','Rilasciato da','Data rilascio','Data scadenza','Certificato battesimo (riferimento)','Foto profilo URL']
        values=[cf,'Giulia','Verdi',date(2010,1,1),'F','Asti','AT','Via Test','12/A','00100','Roma','RM','giulia@example.test','0123456789','X1Z','Sì','Figlia','Polline','Lattosio','Terapia','Note','AZ001','Comune',date(2026,1,1),date(2030,1,1),'battesimo.pdf','https://example.test/foto.png']
        result=self.upload(headers,[values]);self.assertEqual(result.status_code,200,result.json);self.assertEqual(result.json['dettagli']['errori'],[])
        exported=self.client.get('/api/excel/export-anagrafica?cfs='+cf)
        wb=openpyxl.load_workbook(io.BytesIO(exported.data));rows=list(wb.active.values);row=dict(zip([str(h).replace('*','') for h in rows[0]],rows[1]))
        self.assertEqual(row['Codice Famiglia'],'X1Z');self.assertEqual(row['Civico'],'12/A');self.assertEqual(row['CAP'],'00100');self.assertEqual(row['Terapie e medicinali'],'Terapia');self.assertEqual(row['Numero documento'],'AZ001')
        with self.app.app_context():
            person=db.session.get(Persona,cf);self.assertEqual(person.nucleo.codice_fiscale_capofamiglia,cf);self.assertEqual(person.ruolo_famiglia,'Figlia')
            self.assertEqual(json.loads(person.documenti_importati)['battesimo'],'battesimo.pdf')
        again=self.client.post('/api/excel/import',data={'tipo':'anagrafica','file':(io.BytesIO(exported.data),'roundtrip.xlsx')},content_type='multipart/form-data')
        self.assertEqual(again.json['dettagli']['errori'],[]);self.assertEqual(again.json['dettagli']['persone_aggiornate'],1)

    def test_blank_family_code_generates_only_for_new_people_and_empty_cells_preserve_existing_data(self):
        cf=fixture.fiscal_code('VRDLGI10A01H501')
        response=self.upload(['CF','Nome','Cognome','Codice Famiglia'],[[cf,'Giulia','Verdi',''],[self.head_cf,'','','']])
        self.assertEqual(response.json['dettagli']['errori'],[])
        with self.app.app_context():
            person=db.session.get(Persona,cf);self.assertRegex(person.nucleo.codice_invito,r'^[A-Z0-9]{3}$');self.assertNotEqual(person.nucleo_id,self.family_id)
            head=db.session.get(Persona,self.head_cf);self.assertEqual(head.nucleo_id,self.family_id);self.assertEqual(head.comune_residenza,'Comune Test')

    def test_existing_family_code_connects_people_and_bad_row_is_rolled_back(self):
        good=fixture.fiscal_code('VRDLGI10A01H501');bad=fixture.fiscal_code('BNCLGI12A01H501')
        response=self.upload(['CF','Nome','Cognome','Codice Famiglia'],[[bad,'Errato','Test','INVALIDO'],[good,'Giulia','Verdi',self.code]])
        self.assertEqual(response.json['dettagli']['persone_create'],1);self.assertEqual(len(response.json['dettagli']['errori']),1)
        with self.app.app_context():self.assertIsNone(db.session.get(Persona,bad));self.assertEqual(db.session.get(Persona,good).nucleo_id,self.family_id)

    def test_group_codes_cover_all_types_are_stable_and_not_reused_after_deletion(self):
        for model,prefix in [(GruppoCatechismo,'C'),(GruppoDoposcuola,'D'),(GruppoOratorio,'O'),(GruppoGiovani,'G')]:
            ident,code=self.group(model);self.assertRegex(code,'^'+prefix+r'\d{3}$')
            with self.app.app_context():
                group=db.session.get(model,ident);group.nome='Nome modificato';db.session.commit();self.assertEqual(group.codice_gruppo,code)
                db.session.delete(group);db.session.commit()
            _,next_code=self.group(model);self.assertGreater(int(next_code[1:]),int(code[1:]))

    def test_membership_import_uses_only_cf_and_group_code_and_is_idempotent(self):
        _,code=self.group(eta_min=8,eta_max=20)
        rows=[[self.child_cf,code.lower(),'=BAD_FORMULA','NOME DA IGNORARE'],[self.child_cf,code,'','']]
        result=self.upload(['CF','Codice Gruppo','Extra','Nome'],rows,tipo='iscrizioni')
        self.assertEqual(result.status_code,200,result.json);report=result.json['dettagli'];self.assertEqual(report['errori'],[]);self.assertEqual(report['iscrizioni_create'],1);self.assertEqual(report['iscrizioni_esistenti'],1)
        with self.app.app_context():self.assertEqual(db.session.get(Persona,self.child_cf).nome,'Child')
        result=self.upload(['Codice Gruppo','Codice Fiscale'],[[code,self.child_cf]],tipo='iscrizioni',csv_file=True)
        self.assertEqual(result.json['dettagli']['iscrizioni_esistenti'],1)

    def test_age_unique_catechism_unknown_codes_and_missing_people_are_reported(self):
        _,first=self.group(anno_pastorale='2026/2027',eta_min=8,eta_max=20)
        _,second=self.group(anno_pastorale='2026/2027')
        missing=fixture.fiscal_code('VRDLGI10A01H501')
        rows=[[self.child_cf,first],[self.child_cf,second],[self.head_cf,first],[missing,first],[self.child_cf,'C999'],['INVALID',first]]
        result=self.upload(['CF','Codice Gruppo'],rows,tipo='iscrizioni')
        self.assertEqual(result.json['dettagli']['iscrizioni_create'],1);self.assertEqual(len(result.json['dettagli']['errori']),5)
        with self.app.app_context():self.assertEqual(len(db.session.get(Persona,self.child_cf).gruppi_catechismo),1)

    def test_membership_export_has_reimportable_rows_and_group_catalog(self):
        ident,code=self.group()
        self.upload(['CF','Codice Gruppo'],[[self.child_cf,code]],tipo='iscrizioni')
        response=self.client.get('/api/excel/export-iscrizioni');self.assertEqual(response.status_code,200)
        wb=openpyxl.load_workbook(io.BytesIO(response.data));self.assertEqual(wb.sheetnames,['Iscrizioni','Gruppi'])
        self.assertEqual(wb['Iscrizioni']['A2'].value,self.child_cf);self.assertEqual(wb['Iscrizioni']['B2'].value,code);self.assertIn(code,[row[0] for row in list(wb['Gruppi'].values)[1:]])
        result=self.client.post('/api/excel/import',data={'tipo':'iscrizioni','file':(io.BytesIO(response.data),'iscrizioni.xlsx')},content_type='multipart/form-data')
        self.assertEqual(result.json['dettagli']['iscrizioni_esistenti'],1)

    def test_templates_are_empty_bad_headers_are_rejected_and_registration_has_no_documents(self):
        for kind in ('anagrafica','iscrizioni'):
            response=self.client.get('/api/excel/template?tipo='+kind);self.assertEqual(response.status_code,200)
            wb=openpyxl.load_workbook(io.BytesIO(response.data));self.assertEqual(wb.active.max_row,1)
            self.assertEqual(self.client.post('/api/excel/import',data={'tipo':kind,'file':(io.BytesIO(response.data),'empty.xlsx')},content_type='multipart/form-data').json['dettagli']['totale_righe'],0)
        self.assertEqual(self.upload(['Nome'],[['Test']]).status_code,400)
        self.assertEqual(self.upload(['CF','Codice Fiscale'],[[self.child_cf,self.child_cf]]).status_code,400)
        self.assertEqual(self.client.get('/api/excel/template?tipo=errato').status_code,400)
        html=self.client.get('/').get_data(as_text=True);self.assertNotIn('id="regDocumenti"',html);self.assertIn('id="profiloDocumenti"',html)

    def test_formula_like_strings_export_as_text_and_invalid_row_does_not_update_existing_person(self):
        with self.app.app_context():
            person=db.session.get(Persona,self.child_cf);person.note_generali='=HYPERLINK("https://example.test")';db.session.commit()
        wb=openpyxl.load_workbook(io.BytesIO(self.client.get('/api/excel/export-anagrafica?cfs='+self.child_cf).data))
        column=EXCEL_HEADERS.index('Note')+1;self.assertEqual(wb.active.cell(2,column).data_type,'s')
        result=self.upload(['CF','Nome','Data Nascita'],[[self.child_cf,'Da non salvare','30/02/2026']])
        self.assertEqual(len(result.json['dettagli']['errori']),1)
        with self.app.app_context():self.assertEqual(db.session.get(Persona,self.child_cf).nome,'Child')

    def test_ordinary_user_cannot_import_or_export_and_scope_is_enforced(self):
        _,code=self.group();self.login()
        self.assertEqual(self.upload(['CF','Codice Gruppo'],[[self.child_cf,code]],tipo='iscrizioni').status_code,403)
        self.assertEqual(self.client.get('/api/excel/export-iscrizioni').status_code,403)

    def test_migration_assigns_codes_to_existing_groups_without_changing_membership(self):
        ident,code=self.group()
        with self.app.app_context():
            group=db.session.get(GruppoCatechismo,ident);group.ragazzi.append(db.session.get(Persona,self.child_cf));db.session.commit()
            # Simula la colonna assente della versione precedente con una tabella ricostruita.
            ddl=db.session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='gruppo_catechismo'")).scalar_one()
            old=re.sub(r'\s*codice_gruppo VARCHAR\(4\),?', '',ddl)
            old=re.sub(r',?\s*UNIQUE \(codice_gruppo\)', '',old)
            data=db.session.execute(text('SELECT * FROM gruppo_catechismo')).mappings().all()
            db.session.execute(text('DROP TABLE gruppo_catechismo'));db.session.execute(text(old))
            for row in data:
                values=dict(row);values.pop('codice_gruppo');names=list(values)
                db.session.execute(text('INSERT INTO gruppo_catechismo ('+','.join(names)+') VALUES ('+','.join(':'+name for name in names)+')'),values)
            db.session.commit();db.session.expire_all()
            init_default_configurazioni()
            self.assertIsNotNone(db.session.get(GruppoCatechismo,ident).codice_gruppo)
            self.assertEqual([p.codice_fiscale for p in db.session.get(GruppoCatechismo,ident).ragazzi],[self.child_cf])

    def test_actual_formula_in_used_column_is_rejected_but_extra_columns_are_ignored(self):
        _,code=self.group()
        stream=workbook_stream(['CF','Codice Gruppo','Extra'],[[self.child_cf,code,'']]);wb=openpyxl.load_workbook(stream);wb.active['C2']='=1+1'
        data=io.BytesIO();wb.save(data);data.seek(0)
        response=self.client.post('/api/excel/import',data={'tipo':'iscrizioni','file':(data,'formula.xlsx')},content_type='multipart/form-data')
        self.assertEqual(response.json['dettagli']['iscrizioni_create'],1)
        wb.active['A2']='=A1';data=io.BytesIO();wb.save(data);data.seek(0)
        response=self.client.post('/api/excel/import',data={'tipo':'iscrizioni','file':(data,'formula.xlsx')},content_type='multipart/form-data')
        self.assertEqual(len(response.json['dettagli']['errori']),1)

    def test_concurrent_group_creation_assigns_distinct_codes(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.group(GruppoGiovani),range(2)))
        self.assertEqual(len({code for _,code in results}),2)

    def test_disabled_health_and_documents_are_not_changed_by_import(self):
        from services.access_control import DEFAULTS
        grants=set(DEFAULTS['segreteria'][2])-{'anagrafica.salute','anagrafica.documenti'}
        self.assertEqual(self.client.put('/api/accessi/segreteria',json={'permessi':sorted(grants)}).status_code,200)
        self.assertEqual(self.client.put('/api/utenti/1/ruoli',json={'ruolo':'segreteria','privilegi':[]}).status_code,200)
        self.login()
        result=self.upload(['CF','Allergie','Numero documento'],[[self.head_cf,'Da ignorare','AB123']])
        self.assertEqual(result.json['dettagli']['errori'],[])
        with self.app.app_context():
            person=db.session.get(Persona,self.head_cf)
            self.assertEqual(person.allergie,'Nota sanitaria precedente')
            self.assertEqual(json.loads(person.documenti_importati or '{}'),{})
