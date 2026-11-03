"""Opportunità di iscrizione calcolate per la famiglia e i permessi correnti."""
from flask_login import current_user
from models import Attivita, Iscrizione, GruppoCatechismo, GruppoDoposcuola, GruppoOratorio
from services.family_service import can_manage_family

GROUP_MODELS = {'oratorio': (GruppoOratorio, 'ragazzi'), 'catechismo': (GruppoCatechismo, 'ragazzi'), 'doposcuola': (GruppoDoposcuola, 'studenti')}


def age_eligible(person, item):
    if item.eta_min is None and item.eta_max is None:
        return True
    age = person.eta
    return age is not None and (item.eta_min is None or age >= item.eta_min) and (item.eta_max is None or age <= item.eta_max)


def manageable_people():
    person = current_user.persona
    if not person or not person.nucleo:
        return []
    if person.nucleo and can_manage_family(person.nucleo):
        return list(person.nucleo.componenti)
    return [person]


def group_candidates():
    people = manageable_people()
    person = current_user.persona
    manages = bool(person and person.nucleo and can_manage_family(person.nucleo))
    return [p for p in people if (not manages or p.codice_fiscale != current_user.codice_fiscale) and
            (p.ruolo_famiglia in ('Figlio/a', 'Figlio', 'Figlia', 'Minore', 'Nipote') or (p.eta is not None and p.eta < 18))]


def available_groups(category):
    model, collection = GROUP_MODELS[category]
    people = group_candidates()
    results = []
    for group in model.query.filter_by(stato='pubblico').order_by(model.nome).all():
        candidates = [p for p in people if p not in getattr(group, collection) and age_eligible(p, group)]
        if not candidates:
            continue
        info = group.to_dict(**({'include_studenti': False} if category == 'doposcuola' else {'include_ragazzi': False}))
        info['partecipanti'] = [{'codice_fiscale':p.codice_fiscale, 'nominativo':p.nominativo, 'eta':p.eta} for p in candidates]
        results.append(info)
    return results


def enrollment_options():
    people = manageable_people()
    family_cfs = [p.codice_fiscale for p in (current_user.persona.nucleo.componenti if current_user.persona and current_user.persona.nucleo else people)]
    records = Iscrizione.query.filter(Iscrizione.codice_fiscale_partecipante.in_(family_cfs)).all() if family_cfs else []
    activities = {}
    from datetime import datetime
    from dateutil.tz import gettz
    today=datetime.now(gettz('Europe/Rome')).date()
    for activity in Attivita.query.filter_by(is_pubblicato=True).all():
        enrolled = {r.codice_fiscale_partecipante for r in records if r.attivita_id == activity.id and r.stato not in ('annullata','rifiutata')}
        free = activity.posti_disponibili
        ends=activity.data_fine or activity.data_inizio
        open_event=activity.is_attiva and (not ends or ends>=today)
        candidates = [p.codice_fiscale for p in people if p.codice_fiscale not in enrolled and age_eligible(p,activity)] if open_event and (free is None or free > 0) else []
        from routes.iscrizioni import can_withdraw
        withdrawals=[{'id':r.id,'nominativo':r.partecipante.nominativo,'puo_disiscriversi':can_withdraw(r)} for r in records if r.attivita_id==activity.id and r.stato != 'annullata']
        activities[activity.id] = {'partecipanti':candidates, 'gia_iscritto':bool(enrolled), 'ha_iscrizioni':any(r.attivita_id==activity.id for r in records), 'iscrizioni':withdrawals}
    return {'attivita':activities, 'gruppi':{category:available_groups(category) for category in GROUP_MODELS}, 'gruppi_iscritti':{category:assigned_groups(category) for category in GROUP_MODELS}}


def assigned_groups(category):
    groups={}
    for person in manageable_people():
        for group in person_groups(person,category):
            if group.id not in groups:
                info=group.to_dict(**({'include_studenti':False} if category=='doposcuola' else {'include_ragazzi':False}))
                info['componenti_iscritti']=[]
                groups[group.id]=info
            groups[group.id]['componenti_iscritti'].append({'codice_fiscale':person.codice_fiscale,'nominativo':person.nominativo,'eta':person.eta})
    return list(groups.values())


def person_groups(person,category):
    from services.catechismo_parents import members,is_parent_group
    groups=list(getattr(person,'gruppi_'+category))
    if category=='catechismo':
        for group in GruppoCatechismo.query.all():
            if is_parent_group(group) and group not in groups and person in members(group): groups.append(group)
    return groups
