"""Iscrizioni genitori derivate dalle famiglie, senza duplicare dati o iscrizioni."""
import re
from models import GruppoCatechismo

PARENT_MEETING=re.compile(r'\+\s*incontro\s+genitori\b',re.I)


def within_year(group,day):
    from datetime import datetime
    from services.calendar_events import ROME
    match=re.match(r'^(\d{4})[/-](\d{4})$',group.anno_pastorale or '')
    today=datetime.now(ROME)
    year=int(match[1]) if match else today.year-(today.month<9)
    return f'{year:04d}-09-01'<=day<f'{year+1:04d}-09-01'


def is_parent_group(group):
    return isinstance(group,GruppoCatechismo) and group.eta_min is not None and group.eta_min>25


def parents_of(child):
    if not child.nucleo: return []
    if (child.ruolo_famiglia or '').strip().casefold() in ('padre','madre'): return []
    return sorted([p for p in child.nucleo.componenti if p.codice_fiscale!=child.codice_fiscale and (p.ruolo_famiglia or '').strip().casefold() in ('padre','madre')],key=lambda p:(p.cognome.casefold(),p.nome.casefold(),p.codice_fiscale))


def source_groups(group):
    return [g for g in GruppoCatechismo.query.filter_by(anno_pastorale=group.anno_pastorale).all() if g.id!=group.id and not is_parent_group(g)]


def members(group):
    people={p.codice_fiscale:p for p in group.ragazzi}
    if is_parent_group(group):
        from models import Presenza
        if group.id:
            for record in Presenza.query.filter_by(gruppo_categoria='catechismo',gruppo_id=group.id).all():
                if record.persona: people[record.codice_fiscale_persona]=record.persona
        from services.enrollment_options import age_eligible
        for source in source_groups(group):
            for child in source.ragazzi:
                for parent in parents_of(child):
                    if age_eligible(parent,group): people[parent.codice_fiscale]=parent
    return sorted(people.values(),key=lambda p:(p.cognome.casefold(),p.nome.casefold(),p.codice_fiscale))


def parent_events(group,month):
    from services.calendar_events import group_events,month_range
    import hashlib
    result={};stale=False
    if not within_year(group,month_range(month)[0].isoformat()):
        return {'eventi':[],'configurato':True,'mese':month_range(month)[0].strftime('%Y-%m'),'obsoleto':False}
    for source in source_groups(group):
        data=group_events(source,month)
        stale=stale or data['obsoleto']
        for event in data['eventi']:
            if not PARENT_MEETING.search(event['titolo']): continue
            days=[day for day in event['giorni'] if within_year(group,day)]
            if not days: continue
            # Lo stesso appuntamento condiviso fra più classi resta un solo evento.
            key=hashlib.sha256((event['inizio']+'|'+event['fine']+'|'+event['titolo'].casefold()).encode()).hexdigest()[:24]
            result[key]={**event,'id':key,'giorni':days}
    return {'eventi':sorted(result.values(),key=lambda e:(e['inizio'],e['id'])),'configurato':True,'mese':month_range(month)[0].strftime('%Y-%m'),'obsoleto':stale}


def expected_members(group,day):
    if not is_parent_group(group): return members(group)
    from services.calendar_events import group_events,CalendarUnavailable
    from services.enrollment_options import age_eligible
    from werkzeug.exceptions import BadRequest
    people={p.codice_fiscale:p for p in group.ragazzi}
    if not within_year(group,day): return list(people.values())
    try:
        for source in source_groups(group):
            data=group_events(source,day[:7])
            if data['obsoleto']: raise CalendarUnavailable('Calendario non aggiornato')
            if not any(day in e['giorni'] and PARENT_MEETING.search(e['titolo']) for e in data['eventi']): continue
            for child in source.ragazzi:
                for parent in parents_of(child):
                    if age_eligible(parent,group): people[parent.codice_fiscale]=parent
    except CalendarUnavailable:
        raise BadRequest('Impossibile verificare i genitori convocati: riprova quando i calendari sono disponibili.') from None
    return sorted(people.values(),key=lambda p:(p.cognome.casefold(),p.nome.casefold(),p.codice_fiscale))


def group_people(group,collection='ragazzi'):
    return members(group) if isinstance(group,GruppoCatechismo) else list(getattr(group,collection))
