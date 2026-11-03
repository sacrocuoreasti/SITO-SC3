from flask import Blueprint,jsonify,request
from flask_login import current_user
from werkzeug.exceptions import Forbidden,NotFound
from models import db
from services.enrollment_options import GROUP_MODELS,manageable_people,group_candidates,age_eligible
from services.group_attendance import can_record,group_records
from services.calendar_events import group_events,CalendarUnavailable
from services.catechismo_parents import group_people

calendari_gruppi_bp=Blueprint('calendari_gruppi_bp',__name__,url_prefix='/api/calendari-gruppi')


@calendari_gruppi_bp.route('/<category>/<int:id>/sanita')
def health_summary(category,id):
    if category not in GROUP_MODELS:
        raise NotFound()
    model,collection=GROUP_MODELS[category]
    group=db.session.get(model,id)
    if not group:
        raise NotFound()
    if not can_record(category,group):
        raise Forbidden('Quadro sanitario disponibile solo per i gruppi assegnati')
    from services.catechismo_parents import parents_of
    people={p.codice_fiscale:p for p in group_people(group,collection)}
    rows=[]
    for person in sorted(people.values(),key=lambda p:(p.cognome.casefold(),p.nome.casefold())):
        parents=parents_of(person)
        head=person.nucleo.capofamiglia if person.nucleo else None
        contacts=parents or ([head] if head and head!=person else [])
        rows.append({'nominativo':person.nominativo,'allergie':person.allergie or '',
                     'intolleranze_alimentari':person.intolleranze_alimentari or '',
                     'terapie_medicinali':person.terapie_medicinali or '',
                     'note_mediche':person.note_generali or '',
                     'contatti':[{'nominativo':p.nominativo,'telefono':p.telefono or ''} for p in contacts]})
    return jsonify(gruppo=group.nome,categoria=category,persone=rows,
                   conteggi={'iscritti':len(rows),
                             'esigenze_alimentari':sum(bool(r['allergie'] or r['intolleranze_alimentari']) for r in rows),
                             'terapie':sum(bool(r['terapie_medicinali']) for r in rows)})


@calendari_gruppi_bp.route('/<category>/<int:id>')
def get_month(category,id):
    if category not in GROUP_MODELS: raise NotFound()
    model,collection=GROUP_MODELS[category]
    group=db.session.get(model,id)
    if not group: raise NotFound()
    manages=can_record(category,group)
    enrolled=[p for p in manageable_people() if p in group_people(group,collection)]
    eligible=group.stato=='pubblico' and any(age_eligible(p,group) for p in group_candidates())
    if not manages and not enrolled and not eligible: raise Forbidden('Calendario non disponibile per questo profilo')
    try: data=group_events(group,request.args.get('mese'))
    except CalendarUnavailable as error:
        return jsonify(error=str(error),eventi=[],configurato=True),502
    records=group_records(category,group,None if manages else enrolled)
    data.update(categoria=category,gruppo_id=group.id,nome_gruppo=group.nome,puo_registrare_presenze=bool(manages),iscritto=bool(enrolled))
    data['presenze']=[{'data':record.data.isoformat(),'nominativo':record.persona.nominativo,'presente':record.presente} for record in records if record.data.isoformat()[:7]==data['mese']]
    return jsonify(data)


@calendari_gruppi_bp.route('/<category>/<int:id>/registro',methods=['GET','POST','DELETE'])
def manage_register(category,id):
    from services.group_management import managed_group,day_value
    from services.group_attendance import registry_data,save_group_records
    group,collection=managed_group(category,id)
    if request.method=='GET':
        result=registry_data(category,group,request.args.get('mese'),whole_year=request.args.get('periodo')=='anno')
        from services.family_service import staff_user
        result['puo_cancellare']=bool(staff_user())
        return jsonify(result)
    data=request.get_json() or {}
    if request.method=='POST':
        save_group_records(category,group,data)
        return jsonify(success=True,message='Presenze salvate')
    from services.family_service import staff_user
    if not staff_user(): raise Forbidden('Cancellazione riservata alla segreteria')
    day=day_value(data.get('data'))
    for record in group_records(category,group):
        if record.data==day: db.session.delete(record)
    db.session.commit()
    return jsonify(success=True,message='Appello rimosso dal registro; appuntamento in calendario conservato')


@calendari_gruppi_bp.route('/<category>/<int:id>/elenco',methods=['GET','POST','DELETE'])
def manage_roster(category,id):
    from services.group_management import managed_group,roster_data,can_manage_members
    from services.cf_validator import normalizza_cf
    from services.group_age_service import validate_member_age
    from models import Persona
    from werkzeug.exceptions import BadRequest
    group,collection=managed_group(category,id)
    if request.method=='GET': return jsonify(roster_data(category,group,collection))
    if not can_manage_members(category): raise Forbidden('Assegnazione non autorizzata')
    data=request.get_json() or {}
    cf=data.get('codice_fiscale','')
    if not isinstance(cf,str): raise BadRequest('Codice fiscale non valido')
    person=db.session.get(Persona,normalizza_cf(cf))
    if not person: raise BadRequest('Partecipante non trovato')
    members=getattr(group,collection)
    if request.method=='POST' and person not in members:
        validate_member_age(group,person)
        members.append(person)
    if request.method=='DELETE' and person in members: members.remove(person)
    db.session.commit()
    return jsonify(success=True)


@calendari_gruppi_bp.route('/<category>/<int:id>/assegnabili')
def assignable_roster(category,id):
    from services.group_management import managed_group,can_manage_members
    from models import Persona
    group,collection=managed_group(category,id)
    if not can_manage_members(category): raise Forbidden('Assegnazione non autorizzata')
    existing={p.codice_fiscale for p in getattr(group,collection)}
    return jsonify(persone=[{'codice_fiscale':p.codice_fiscale,'nominativo':p.nominativo,'eta':p.eta}
        for p in Persona.query.order_by(Persona.cognome,Persona.nome).all() if p.codice_fiscale not in existing and age_eligible(p,group)])
