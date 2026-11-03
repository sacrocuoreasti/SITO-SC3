"""Catalogo virtuale: calendari manuali e calendari dei gruppi dell’anno corrente."""
from datetime import datetime
from dateutil.tz import gettz
from werkzeug.exceptions import BadRequest
from models import CalendarioComunita
from services.enrollment_options import GROUP_MODELS
from services.group_calendar import calendar_info, calendar_url
from services.group_attendance import can_record
from services.catechismo_membership import year_key
from services.catechismo_parents import is_parent_group, source_groups


def current_pastoral_year(today=None):
    today=today or datetime.now(gettz('Europe/Rome')).date()
    first=today.year if today.month>=9 else today.year-1
    return f'{first}/{first+1}'


def public_group(group):
    return group.stato in ('pubblico','chiuso','attivo')


def has_calendar(group):
    return bool(calendar_info(group) or (is_parent_group(group) and any(calendar_info(g) for g in source_groups(group))))


def calendar_catalog(include_private=False):
    year=current_pastoral_year()
    query=CalendarioComunita.query
    if not include_private:query=query.filter_by(is_pubblico=True)
    result=[dict(c.to_dict(),automatico=False) for c in query.order_by(CalendarioComunita.ordine,CalendarioComunita.id).all()]
    colors={'catechismo':'#8B1E1E','oratorio':'#2563eb','doposcuola':'#d97706'}
    icons={'catechismo':'📖','oratorio':'🏓','doposcuola':'📚'}
    for category,(model,_) in GROUP_MODELS.items():
        for group in model.query.order_by(model.nome,model.id).all():
            group_year=getattr(group,'anno_pastorale',None) or getattr(group,'anno_scolastico',None)
            visible=public_group(group)
            if year_key(group_year)!=year or not has_calendar(group) or (not visible and not (include_private and can_record(category,group))):continue
            origin={'categoria':category,'id':group.id,'nome':group.nome}
            result.append({'id':f'auto:{category}:{group.id}','titolo':group.nome,'descrizione':f'{category.capitalize()} · {year}',
                           'google_calendar_url':calendar_info(group),'calendar_embed_url':calendar_info(group),
                           'calendar_api_url':f'/api/impostazioni/calendari-gruppi/{category}/{group.id}',
                           'categoria':category,'colore':colors[category],'icona':icons[category],
                           'is_pubblico':visible,'automatico':True,'anno_pastorale':year,'gruppi_origine':[origin]})
    merged={}
    for entry in result:
        try:url=calendar_url(entry['google_calendar_url'])
        except BadRequest:url=entry['google_calendar_url']
        key=(url or str(entry['id']),entry['is_pubblico'])
        if key not in merged:merged[key]=entry
        else:
            previous=merged[key]
            previous.setdefault('gruppi_origine',[]).extend(entry.get('gruppi_origine',[]))
            if entry.get('calendar_api_url') and not previous.get('calendar_api_url'):
                previous['calendar_api_url']=entry['calendar_api_url']
    return list(merged.values())
