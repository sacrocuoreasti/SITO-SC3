"""Registro per gruppo/giornata: dati storici conservati, nuovi salvataggi idempotenti."""
from datetime import datetime
from flask_login import current_user
from sqlalchemy import or_,and_,text
from werkzeug.exceptions import Forbidden,BadRequest
from models import db,Presenza,Attivita
from services.enrollment_options import GROUP_MODELS
from services.family_service import staff_user
from services.cf_validator import normalizza_cf


def can_record(category,group):
    if not current_user.is_authenticated: return False
    if staff_user(): return True
    roles=set(current_user.get_all_roles())
    if category in ('oratorio','doposcuola') and 'oratorio' in roles: return True
    if category=='catechismo':
        return 'catechista' in roles and (current_user.id==group.catechista_utente_id or current_user.codice_fiscale==group.catechista_cf and bool(group.catechista_cf) or any(u.id==current_user.id for u in group.catechisti))
    if category=='oratorio':
        return bool(roles & {'oratorio','animatore'}) and (current_user.id==group.animatore_utente_id or current_user.codice_fiscale==group.animatore_cf and bool(group.animatore_cf) or any(u.id==current_user.id for u in group.animatori))
    return bool(roles & {'educatore','doposcuola','oratorio','catechista'}) and (current_user.id==group.educatore_utente_id or current_user.codice_fiscale==group.educatore_cf and bool(group.educatore_cf))


def group_records(category,group,people=None):
    _,collection=GROUP_MODELS[category]
    people=list(getattr(group,collection)) if people is None else people
    cfs=[p.codice_fiscale for p in people]
    if not cfs: return []
    legacy=and_(Presenza.gruppo_categoria.is_(None),Presenza.gruppo_id.is_(None))
    if group.attivita_id: legacy=and_(legacy,Presenza.attivita_id==group.attivita_id)
    else:
        ids=db.session.query(Attivita.id).filter(Attivita.categoria==category)
        legacy=and_(legacy,Presenza.attivita_id.in_(ids))
    query=Presenza.query.filter(Presenza.codice_fiscale_persona.in_(cfs),or_(and_(Presenza.gruppo_categoria==category,Presenza.gruppo_id==group.id),legacy))
    unique={}
    for record in query.order_by(Presenza.id.asc()).all():
        key=(record.codice_fiscale_persona,record.data)
        previous=unique.get(key)
        if not previous or record.gruppo_id is not None or previous.gruppo_id is None: unique[key]=record
    return sorted(unique.values(),key=lambda r:(r.data,r.id))


def save_group_records(category,group,data):
    if not can_record(category,group): raise Forbidden('Non puoi registrare presenze per questo gruppo')
    try: day=datetime.strptime(data.get('data',''),'%Y-%m-%d').date()
    except (ValueError,TypeError): raise BadRequest('Scegli una data valida per l’appello')
    rows=data.get('presenze')
    if not isinstance(rows,list) or not rows: raise BadRequest('Nessuna presenza da salvare')
    _,collection=GROUP_MODELS[category]
    allowed={p.codice_fiscale:p for p in getattr(group,collection)}
    normalized=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or type(row.get('presente')) is not bool: raise BadRequest('Indica presente o assente per ogni partecipante')
        cf=normalizza_cf(row.get('codice_fiscale',''))
        if cf not in allowed: raise Forbidden('Uno dei partecipanti non appartiene al gruppo')
        if cf in seen: raise BadRequest('Partecipante ripetuto nello stesso appello')
        seen.add(cf);normalized.append((cf,row))
    from services.calendar_events import calendar_dates
    meetings,_=calendar_dates(group,day.strftime('%Y-%m'))
    source=next((m for m in meetings if m['data']==day.isoformat()),None)
    title=(source['titolo_incontro'] if source else data.get('titolo_incontro',''))[:100]
    if db.engine.dialect.name=='sqlite': db.session.execute(text('BEGIN IMMEDIATE'))
    else: db.session.query(type(group)).filter_by(id=group.id).with_for_update().one()
    db.session.refresh(group)
    db.session.expire(group,[collection])
    if any(cf not in {p.codice_fiscale for p in getattr(group,collection)} for cf,_ in normalized): raise Forbidden('Il gruppo è cambiato: ricarica l’appello')
    history=group_records(category,group)
    activity_id=group.attivita_id
    if not activity_id:
        previous_ids={record.attivita_id for record in history}
        if history:
            activity_id=history[-1].attivita_id
            if len(previous_ids)==1: group.attivita_id=activity_id
        else:
            activity=Attivita(titolo=f'{category.capitalize()} - {group.nome}',categoria=category,is_attiva=True,is_pubblicato=False,anno_pastorale=getattr(group,'anno_pastorale',None) or getattr(group,'anno_scolastico',''))
            db.session.add(activity);db.session.flush();activity_id=activity.id;group.attivita_id=activity_id
    existing={r.codice_fiscale_persona:r for r in history if r.data==day}
    for cf,row in normalized:
        record=existing.get(cf)
        if not record:
            record=Presenza(attivita_id=activity_id,codice_fiscale_persona=cf,data=day)
            db.session.add(record)
        record.gruppo_categoria=category;record.gruppo_id=group.id
        record.presente=row['presente'];record.concorre_percentuale=data.get('concorre_percentuale',True) is not False
        if title: record.titolo_incontro=title
        if 'note' in row: record.note=str(row['note'])[:255]
    db.session.commit()


def registry_data(category,group,month=None,whole_year=False):
    from services.calendar_events import merge_calendar_dates,month_range,group_year_dates
    _,collection=GROUP_MODELS[category]
    records=group_records(category,group)
    by_date={}
    for record in records:
        day=record.data.isoformat()
        row=by_date.setdefault(day,{'data':day,'data_it':record.data.strftime('%d/%m/%Y'),'titolo_incontro':record.titolo_incontro or '',
            'concorre_percentuale':record.concorre_percentuale is not False,'presenti_count':0,'assenti_count':0})
        row['presenti_count' if record.presente else 'assenti_count']+=1
        if not row['titolo_incontro'] and record.titolo_incontro: row['titolo_incontro']=record.titolo_incontro
    dates,warning=(group_year_dates(group,list(by_date.values())) if whole_year else merge_calendar_dates(group,list(by_date.values()),month))
    students=[]
    for person in getattr(group,collection):
        own=[r for r in records if r.codice_fiscale_persona==person.codice_fiscale]
        valid=[r for r in own if r.concorre_percentuale is not False]
        present=sum(r.presente for r in own);valid_present=sum(r.presente for r in valid)
        students.append({'codice_fiscale':person.codice_fiscale,'nominativo':person.nominativo,'eta':person.eta,
            'presenze_map':{r.data.isoformat():r.presente for r in own},'totale_incontri':len(own),'presenti':present,'assenti':len(own)-present,
            'totale_incontri_validi':len(valid),'presenti_validi':valid_present,'percentuale':round(100*valid_present/len(valid)) if valid else 0})
    return {'gruppo':group.to_dict(**({'include_studenti':False} if category=='doposcuola' else {'include_ragazzi':False})),
        'date_incontri':dates,'studenti':students,'totale_date':len(dates),'incontri_registrati':len(by_date),
        'mese':month_range(month)[0].strftime('%Y-%m'),'data_odierna':datetime.now().date().isoformat(),'avviso_calendario':warning}
