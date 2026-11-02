"""Fasce di età facoltative per i nuovi inserimenti nei gruppi."""
from flask import request
from werkzeug.exceptions import BadRequest, Forbidden
from models import db, Persona
from services.cf_validator import normalizza_cf


def apply_age_range(group, data):
    from services.family_service import staff_user
    if any(key in data for key in ('eta_min', 'eta_max')) and not staff_user():
        raise Forbidden('Solo l’amministrazione può modificare le fasce di età')
    values = {}
    for key in ('eta_min', 'eta_max'):
        value = data.get(key, getattr(group,key))
        if value == '': value = None
        if value is not None and (type(value) is not int or not 0 <= value <= 120):
            raise BadRequest('Le età devono essere numeri interi tra 0 e 120 anni')
        values[key] = value
    if all(v is not None for v in values.values()) and values['eta_min'] > values['eta_max']:
        raise BadRequest('L’età minima non può superare l’età massima')
    for key,value in values.items(): setattr(group,key,value)


def validate_member_age(group, person):
    if group.eta_min is None and group.eta_max is None: return
    age = person.eta
    if age is None:
        raise BadRequest('Indica la data di nascita di ' + person.nominativo + ' prima di iscriverlo al gruppo')
    if (group.eta_min is not None and age < group.eta_min) or (group.eta_max is not None and age > group.eta_max):
        raise BadRequest(person.nominativo + ' non rientra nella fascia di età del gruppo ' + group.nome)


def register_age_guard(blueprint, model, collection):
    @blueprint.before_request
    def validate_group_members():
        if request.method != 'POST': return
        path = request.path
        if not (path.endswith('/iscrivi-figlio') or path.endswith('/'+collection) or path.endswith('/'+collection+'/batch')): return
        data = request.get_json() or {}
        group_id = (request.view_args or {}).get('id') or data.get('gruppo_id')
        try: group = db.session.get(model,int(group_id))
        except (TypeError,ValueError): return
        if not group: return
        from services.catechismo_parents import is_parent_group
        if model.__name__=='GruppoCatechismo' and not path.endswith('/iscrivi-figlio'):
            from services.family_service import staff_user
            if not staff_user(): raise Forbidden('Assegnazione riservata alla segreteria')
        if is_parent_group(group): raise BadRequest('I genitori sono iscritti automaticamente tramite i figli: non servono assegnazioni manuali.')
        members = data.get('codici_fiscali', [data.get('codice_fiscale','')])
        if not isinstance(members,list): raise BadRequest('Elenco dei partecipanti non valido')
        for cf in members:
            if not isinstance(cf,str): raise BadRequest('Codice fiscale non valido')
            person = db.session.get(Persona,normalizza_cf(cf))
            if person and person not in getattr(group,collection): validate_member_age(group,person)
