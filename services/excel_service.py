"""Import/export del portale: CF per le persone, codice stabile per i gruppi."""
import csv,json,re,zipfile
from datetime import date,datetime
from io import BytesIO,StringIO
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment
from werkzeug.exceptions import BadRequest,Conflict
from sqlalchemy.exc import IntegrityError
from models import db,Persona,NucleoFamiliare,Attivita,Iscrizione
from services.cf_validator import normalizza_cf,valida_cf,estrai_dati_cf

# Stesse colonne e stessi identificativi in importazione ed esportazione.
FIELDS=[
 ('codice_fiscale','Codice Fiscale*',['cf'],16),('cognome','Cognome*',[],100),('nome','Nome*',[],100),
 ('sesso','Sesso (M/F)',['sesso'],1),('data_nascita','Data Nascita',['data di nascita (aaaa-mm-gg)'],None),
 ('luogo_nascita','Luogo Nascita',['luogo di nascita'],100),('provincia_nascita','Provincia Nascita',[],10),
 ('foto_profilo_url','Foto profilo URL',[],500),('indirizzo_residenza','Indirizzo Residenza',['indirizzo','via/corso/piazza'],200),
 ('civico_residenza','Civico',[],30),('cap_residenza','CAP',[],10),('comune_residenza','Comune Residenza',['comune'],100),
 ('provincia_residenza','Provincia Residenza',[],10),('email','Email',['mail'],120),('telefono','Cellulare',['telefono','tel'],30),
 ('codice_famiglia','Codice Famiglia',[],3),('ruolo_famiglia','Ruolo Famiglia',[],50),('capofamiglia','Capofamiglia (Sì/No)',['capofamiglia'],None),
 ('allergie','Allergie',['allergie e note mediche'],20000),('intolleranze_alimentari','Intolleranze Alimentari',[],20000),
 ('terapie_medicinali','Terapie e medicinali',[],20000),('note_generali','Note',[],20000),
 ('identita','Carta identità (riferimento)',[],500),('numero_documento','Numero documento',[],100),('rilasciato_da','Rilasciato da',[],200),
 ('data_rilascio','Data rilascio',[],None),('data_scadenza','Data scadenza',[],None),
 ('battesimo','Certificato battesimo (riferimento)',[],500),('comunione','Certificato comunione (riferimento)',[],500),
 ('cresima','Certificato cresima (riferimento)',[],500),('matrimonio','Certificato matrimonio (riferimento)',[],500),
]
EXCEL_HEADERS=[f[1] for f in FIELDS]
HEALTH={'allergie','intolleranze_alimentari','terapie_medicinali','note_generali'}
DOCUMENTS={'identita','battesimo','comunione','cresima','matrimonio','numero_documento','rilasciato_da','data_rilascio','data_scadenza'}
DATES={'data_nascita','data_rilascio','data_scadenza'}
GROUP_HEADERS=['Codice Fiscale*','Codice Gruppo*','Cognome','Nome','Gruppo','Tipologia','Anno Pastorale']


def workbook_stream(headers,rows=(),title='Anagrafica'):
    wb=openpyxl.Workbook();ws=wb.active;ws.title=title
    ws.sheet_view.showGridLines=False
    ws.append(headers);ws.freeze_panes='C2';ws.auto_filter.ref=f'A1:{openpyxl.utils.get_column_letter(len(headers))}{max(2,ws.max_row)}'
    for cell in ws[1]:
        cell.fill=PatternFill('solid',fgColor='8B1E1E');cell.font=Font(name='Calibri',bold=True,color='FFFFFF',size=11)
        cell.alignment=Alignment(horizontal='center',wrap_text=True,vertical='center')
    ws.row_dimensions[1].height=44
    for row in rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            if isinstance(cell.value,str):cell.data_type='s';cell.number_format='@'
            elif isinstance(cell.value,(date,datetime)):cell.number_format='yyyy-mm-dd'
            cell.alignment=Alignment(vertical='top',wrap_text=True)
    for i,header in enumerate(headers,1):
        column=ws.column_dimensions[openpyxl.utils.get_column_letter(i)];column.width=min(36,max(20,len(header)+2));column.number_format='@'
    ws.auto_filter.ref=f'A1:{openpyxl.utils.get_column_letter(len(headers))}{max(2,ws.max_row)}'
    output=BytesIO();wb.save(output);output.seek(0);return output


def genera_template_excel(tipo='anagrafica'):
    if tipo not in ('anagrafica','iscrizioni'):raise BadRequest('Tipo di importazione non valido')
    return workbook_stream(EXCEL_HEADERS if tipo=='anagrafica' else GROUP_HEADERS[:2],title=tipo.capitalize())


def esporta_anagrafica_excel(persone_list,include_health=True,include_documents=True):
    rows=[]
    for person in persone_list:
        imported=json.loads(person.documenti_importati or '{}') if include_documents else {}
        if include_documents:
            for doc in person.documenti:
                imported[doc.tipo]=doc.nome_originale
                if doc.tipo=='identita':
                    for key in ('numero_documento','rilasciato_da','data_rilascio','data_scadenza'):
                        value=getattr(doc,key)
                        if value:imported[key]=value
        row=[]
        for key,_,_,_ in FIELDS:
            if key in DOCUMENTS:value=imported.get(key,'') if include_documents else ''
            elif key in HEALTH and not include_health:value=''
            elif key=='codice_famiglia':value=person.nucleo.codice_invito if person.nucleo else ''
            elif key=='capofamiglia':value='Sì' if person.nucleo and person.nucleo.codice_fiscale_capofamiglia==person.codice_fiscale else 'No'
            else:value=getattr(person,key) or ''
            if key in DATES and value:value=parse_date(value)
            row.append(value)
        rows.append(row)
    return workbook_stream(EXCEL_HEADERS,rows)


def esporta_gruppi_excel():
    from services.enrollment_options import GROUP_MODELS
    from services.group_attendance import can_record
    from services.access_control import can
    from services.catechismo_parents import group_people
    groups=[];members=[]
    for category,(model,collection) in GROUP_MODELS.items():
        for group in model.query.order_by(model.id).all():
            if not can(category+'.assegnazioni') or not can_record(category,group):continue
            year=getattr(group,'anno_pastorale',None) or getattr(group,'anno_scolastico',None)
            groups.append([group.codice_gruppo,group.nome,category,year,group.stato])
            for person in group_people(group,collection):members.append([person.codice_fiscale,group.codice_gruppo,person.cognome,person.nome,group.nome,category,year])
    # Il primo foglio è reimportabile; il secondo permette di trovare il codice del gruppo.
    stream=workbook_stream(GROUP_HEADERS,members,'Iscrizioni');wb=openpyxl.load_workbook(stream)
    catalog=openpyxl.load_workbook(workbook_stream(['Codice Gruppo','Gruppo','Tipologia','Anno Pastorale','Stato'],groups,'Gruppi')).active
    target=wb.create_sheet('Gruppi')
    from copy import copy
    for row in catalog:
        for cell in row:
            new=target.cell(cell.row,cell.column,cell.value);new._style=copy(cell._style);new.data_type=cell.data_type
    for key,dimension in catalog.column_dimensions.items():target.column_dimensions[key].width=dimension.width
    target.freeze_panes='B2';target.auto_filter.ref=catalog.auto_filter.ref;target.row_dimensions[1].height=44
    output=BytesIO();wb.save(output);output.seek(0);return output


def parse_date(value):
    if isinstance(value,datetime):return value.date()
    if isinstance(value,date):return value
    if not value:return None
    for pattern in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%Y/%m/%d'):
        try:return datetime.strptime(str(value).strip(),pattern).date()
        except ValueError:pass
    return None


def key_name(value):return re.sub(r'\s+',' ',str(value or '').replace('*','').replace('_',' ').strip().lower())


class ExcelFormula(str):pass


def read_rows(stream,filename='file.xlsx'):
    if filename.lower().endswith('.csv'):
        try:body=stream.read().decode('utf-8-sig')
        except UnicodeDecodeError:raise BadRequest('Il CSV deve essere salvato come UTF-8')
        try:dialect=csv.Sniffer().sniff(body[:4096],delimiters=',;\t')
        except csv.Error:dialect=csv.excel
        rows=list(csv.reader(StringIO(body),dialect))
    else:
        try:
            # Limiti anche sulla dimensione decompressa, prima di leggere le celle.
            with zipfile.ZipFile(stream) as archive:
                if sum(info.file_size for info in archive.infolist())>32*1024*1024:raise BadRequest('File Excel troppo grande')
            stream.seek(0);wb=openpyxl.load_workbook(stream,read_only=True,data_only=False);ws=wb.active
            if ws.max_row>5001 or ws.max_column>128:raise BadRequest('Massimo 5000 righe e 128 colonne per file')
            rows=[[ExcelFormula(cell.value) if cell.data_type=='f' else cell.value for cell in row] for row in ws.iter_rows()];wb.close()
        except (zipfile.BadZipFile,ValueError,KeyError):raise BadRequest('File Excel non valido: usa un file .xlsx oppure .csv')
    if not rows or len(rows)>5001 or max(map(len,rows))>128:raise BadRequest('File vuoto o troppo grande: massimo 5000 righe e 128 colonne')
    return rows


def importa_da_excel(stream,tipo='anagrafica',filename='file.xlsx',include_health=True,include_documents=True):
    if tipo not in ('anagrafica','iscrizioni'):raise BadRequest('Scegli Anagrafica oppure Iscrizioni')
    rows=read_rows(stream,filename)
    aliases={key_name(label):key for key,label,_,_ in FIELDS}
    for key,_,names,_ in FIELDS:
        aliases[key_name(key)]=key
        for name in names:aliases[key_name(name)]=key
    aliases.update({'codice gruppo':'codice_gruppo','cf capofamiglia':'cf_capofamiglia'})
    mapping={}
    for index,header in enumerate(rows[0]):
        key=aliases.get(key_name(header))
        if key and (tipo=='anagrafica' or key in ('codice_fiscale','codice_gruppo')):
            if key in mapping:raise BadRequest('Colonna duplicata: '+str(header))
            mapping[key]=index
    if 'codice_fiscale' not in mapping or (tipo=='iscrizioni' and 'codice_gruppo' not in mapping):raise BadRequest('Mancano le colonne Codice Fiscale'+(' e Codice Gruppo' if tipo=='iscrizioni' else ''))
    from services.catechismo_membership import lock_enrollment
    lock_enrollment([])
    report=dict(success=True,totale_righe=0,persone_create=0,persone_aggiornate=0,nuclei_creati=0,iscrizioni_create=0,iscrizioni_esistenti=0,errori=[])
    for number,row in enumerate(rows[1:],2):
        if not any(value is not None and str(value).strip() for value in row):continue
        report['totale_righe']+=1
        values={key:row[index] if index<len(row) else None for key,index in mapping.items()}
        try:
            if any(isinstance(value,ExcelFormula) for value in values.values()):raise ValueError('Usa valori, non formule, nelle colonne importate')
            with db.session.begin_nested():
                if tipo=='iscrizioni':counts=import_membership(values)
                else:counts=import_person(values,include_health,include_documents)
                db.session.flush()
            for key,count in counts.items():report[key]+=count
        except (ValueError,BadRequest,Conflict,IntegrityError) as error:
            message=error.description if isinstance(error,(BadRequest,Conflict)) else 'Dati duplicati o non validi' if isinstance(error,IntegrityError) else str(error)
            report['errori'].append(f'Riga {number}: {message}')
    db.session.commit();return report


def text_value(value):
    if value is None:return ''
    if isinstance(value,float) and value.is_integer():return str(int(value))
    return str(value).strip()


def import_person(values,include_health,include_documents):
    cf=normalizza_cf(values.get('codice_fiscale'))
    if not valida_cf(cf):raise ValueError('Codice fiscale mancante o non valido')
    person=db.session.get(Persona,cf);created=person is None
    if created:
        if not text_value(values.get('nome')) or not text_value(values.get('cognome')):raise ValueError('Nome e cognome obbligatori per una nuova persona')
        person=Persona(codice_fiscale=cf);db.session.add(person)
    counts={'persone_create':int(created),'persone_aggiornate':int(not created),'nuclei_creati':0}
    docs=json.loads(person.documenti_importati or '{}')
    for key,_,_,limit in FIELDS:
        value=values.get(key)
        if value is None or not text_value(value) or key in ('codice_fiscale','codice_famiglia','capofamiglia'):continue
        if key in HEALTH and not include_health or key in DOCUMENTS and not include_documents:continue
        if key in DATES:
            parsed=parse_date(value)
            if not parsed:raise ValueError('Data non valida: '+key)
            value=parsed
        else:value=text_value(value)
        if limit and len(value)>limit:raise ValueError('Valore troppo lungo: '+key)
        if key=='sesso':
            value=value.upper()
            if value not in ('M','F'):raise ValueError('Sesso non valido: usa M o F')
        if key=='cap_residenza' and value.isdigit():value=value.zfill(5)
        if key=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Email non valida')
        if key=='foto_profilo_url' and not value.startswith(('https://','/uploads/')):raise ValueError('La foto deve avere un URL HTTPS o un riferimento /uploads/')
        if key in DOCUMENTS:docs[key]=value.isoformat() if isinstance(value,date) else value
        else:setattr(person,key,value)
    if created:
        extracted=estrai_dati_cf(cf)
        if not person.data_nascita:person.data_nascita=extracted.get('data_nascita')
        if not person.sesso:person.sesso=extracted.get('sesso')
    if include_documents:person.documenti_importati=json.dumps(docs)
    code=text_value(values.get('codice_famiglia')).upper()
    if code and not re.fullmatch(r'[A-Z0-9]{3}',code):raise ValueError('Il codice famiglia deve avere tre lettere o numeri')
    head=text_value(values.get('capofamiglia')).lower()
    if head and head not in ('sì','si','s','true','1','no','n','false','0'):raise ValueError('Capofamiglia: indica Sì o No')
    db.session.flush()
    if include_documents:
        identity=next((doc for doc in person.documenti if doc.tipo=='identita'),None)
        if identity:
            for key in ('numero_documento','rilasciato_da','data_rilascio','data_scadenza'):
                if text_value(values.get(key)):
                    setattr(identity,key,parse_date(values[key]) if key in DATES else text_value(values[key]))
    family=NucleoFamiliare.query.filter_by(codice_invito=code).first() if code else person.nucleo
    legacy_head=normalizza_cf(values.get('cf_capofamiglia'))
    if not code and legacy_head:
        if not valida_cf(legacy_head) or not db.session.get(Persona,legacy_head):raise ValueError('Importa prima l’anagrafica del capofamiglia indicato')
        family=NucleoFamiliare.query.filter_by(codice_fiscale_capofamiglia=legacy_head).first()
    if not family:
        family=NucleoFamiliare(nome_famiglia='Famiglia '+person.cognome,codice_invito=code or None,indirizzo=person.indirizzo_residenza,telefono_principale=person.telefono,citta=person.comune_residenza)
        db.session.add(family);db.session.flush();counts['nuclei_creati']=1
        if legacy_head and not code:family.codice_fiscale_capofamiglia=legacy_head
        elif head not in ('no','n','false','0'):family.codice_fiscale_capofamiglia=cf
    if person.nucleo_id and person.nucleo_id!=family.id and person.nucleo.codice_fiscale_capofamiglia==cf:raise ValueError('La persona è capofamiglia di un altro nucleo: modifica prima il nucleo dal profilo')
    person.nucleo=family
    if head in ('sì','si','s','true','1'):family.codice_fiscale_capofamiglia=cf
    return counts


def import_membership(values):
    from services.enrollment_options import GROUP_MODELS,age_eligible
    from services.group_codes import PREFIXES
    from services.access_control import can
    from services.group_attendance import can_record
    from services.catechismo_membership import ensure_unique
    cf=normalizza_cf(values.get('codice_fiscale'));code=text_value(values.get('codice_gruppo')).upper()
    if not valida_cf(cf):raise ValueError('Codice fiscale mancante o non valido')
    if not re.fullmatch(r'[DCOG][0-9]{3}',code) or code[1:]=='000':raise ValueError('Codice gruppo non valido: usa D001, C001, O001 o G001')
    category=next(category for category,prefix in PREFIXES.items() if prefix==code[0]);model,collection=GROUP_MODELS[category]
    group=model.query.filter_by(codice_gruppo=code).first()
    if not group:raise ValueError('Gruppo non trovato: '+code)
    if not can(category+'.assegnazioni') or not can_record(category,group):raise ValueError('Non hai il permesso di assegnare persone a questo gruppo')
    person=db.session.get(Persona,cf)
    if not person:raise ValueError('Persona non trovata: importa prima l’anagrafica')
    members=getattr(group,collection)
    if person in members:return {'iscrizioni_esistenti':1}
    if not age_eligible(person,group):raise ValueError('La persona non rientra nella fascia di età del gruppo')
    if category=='catechismo':ensure_unique(group,[person])
    members.append(person);return {'iscrizioni_create':1}


def esporta_iscritti_attivita_excel(attivita, include_health=True) -> BytesIO:
    """
    Esporta gli iscritti di un'attività con colonne per quote e note sanitarie/allergie.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Iscritti - {attivita.titolo[:25]}"

    header_fill = PatternFill(start_color="8B1E1E", end_color="8B1E1E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    headers = [
        "Codice Fiscale", "Cognome", "Nome", "Età", "Data Nascita",
        "Famiglia", "Telefono Genitore/Contatto", "Email",
        "Squadra", "Stato Iscrizione", "Stato Pagamento", "Quota Dovuta (€)", "Quota Pagata (€)",
        "Note / Deleghe", "Intolleranze Alimentari", "Allergie e Note Mediche"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, isc in enumerate(attivita.iscrizioni, start=2):
        p = isc.partecipante
        telefono = p.telefono
        if not telefono and p.nucleo and p.nucleo.capofamiglia:
            telefono = p.nucleo.capofamiglia.telefono

        ws.cell(row=row_idx, column=1, value=p.codice_fiscale)
        ws.cell(row=row_idx, column=2, value=p.cognome)
        ws.cell(row=row_idx, column=3, value=p.nome)
        ws.cell(row=row_idx, column=4, value=p.eta if p.eta is not None else "")
        ws.cell(row=row_idx, column=5, value=p.data_nascita.strftime('%d/%m/%Y') if p.data_nascita else "")
        ws.cell(row=row_idx, column=6, value=p.nucleo.nome_famiglia if p.nucleo else "")
        ws.cell(row=row_idx, column=7, value=telefono or "")
        ws.cell(row=row_idx, column=8, value=p.email or "")
        ws.cell(row=row_idx, column=9, value=isc.squadra or "")
        ws.cell(row=row_idx, column=10, value=isc.stato.capitalize())
        ws.cell(row=row_idx, column=11, value=isc.stato_pagamento.capitalize())
        ws.cell(row=row_idx, column=12, value=isc.importo_dovuto)
        ws.cell(row=row_idx, column=13, value=isc.importo_pagato)
        ws.cell(row=row_idx, column=14, value=isc.note_iscrizione or "")
        ws.cell(row=row_idx, column=15, value=(p.intolleranze_alimentari or "") if include_health else "")
        ws.cell(row=row_idx, column=16, value=(p.allergie or "") if include_health else "")

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
