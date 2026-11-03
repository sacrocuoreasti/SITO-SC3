"""Elenco e appelli condivisi di oratorio e doposcuola."""
from datetime import date
from flask_login import current_user
from werkzeug.exceptions import Forbidden,NotFound,BadRequest
from models import db,Persona
from services.enrollment_options import GROUP_MODELS,age_eligible
from services.group_attendance import can_record,registry_data,group_records,save_group_records
from services.catechismo_parents import group_people,parents_of
from services.family_service import staff_user
from services.group_age_service import validate_member_age
from services.cf_validator import normalizza_cf


def managed_group(category,id):
    if category not in ('oratorio','doposcuola','giovani'): raise NotFound()
    model,collection=GROUP_MODELS[category]
    group=db.session.get(model,id)
    if not group: raise NotFound()
    if not can_record(category,group): raise Forbidden('Gestione non disponibile per questo profilo')
    return group,collection


def can_manage_members(category):
    from services.access_control import can,is_admin
    return is_admin() or can(category+'.assegnazioni')


def day_value(value):
    try:
        day=date.fromisoformat(value)
        if day.isoformat()!=value: raise ValueError()
        return day
    except (ValueError,TypeError): raise BadRequest('Data non valida')


def roster_data(category,group,collection):
    people=[]
    for person in sorted(group_people(group,collection),key=lambda p:(p.cognome.casefold(),p.nome.casefold())):
        parents=parents_of(person)
        head=person.nucleo.capofamiglia if person.nucleo else None
        people.append({'codice_fiscale':person.codice_fiscale,'nome':person.nome,'cognome':person.cognome,'nominativo':person.nominativo,
            'genitori':[{'nominativo':p.nominativo,'telefono':p.telefono or '','ruolo':p.ruolo_famiglia} for p in parents],
            'referente':{'nominativo':head.nominativo,'telefono':head.telefono or ''} if not parents and head and head!=person else None,
            'allergie':person.allergie or '','intolleranze_alimentari':person.intolleranze_alimentari or '',
            'terapie_medicinali':person.terapie_medicinali or '','note_mediche':person.note_generali or ''})
    return {'gruppo':group.to_dict(**({'include_studenti':False} if category=='doposcuola' else {'include_ragazzi':False})),
        'persone':people,'puo_modificare':bool(can_manage_members(category))}
