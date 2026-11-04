"""Calendari della comunità e appuntamenti locali; nessuna copia dei registri dei gruppi."""
import re
from datetime import datetime,timedelta
from urllib.parse import parse_qs,urlsplit
from werkzeug.exceptions import BadRequest
from models import db,CalendarioComunita,EventoCalendarioComunita
from services.group_calendar import calendar_url
from services.calendar_events import month_range,local_datetime


def apply_calendar_fields(calendar,data):
    if not isinstance(data,dict):raise BadRequest('Calendario non valido')
    for key,limit in [('titolo',150),('descrizione',20000),('icona',30),('categoria',50)]:
        if key in data:
            value=data[key]
            if not isinstance(value,str) or len(value)>limit:raise BadRequest('Valore non valido: '+key)
            setattr(calendar,key,value.strip())
    if not calendar.titolo:raise BadRequest('Indica il nome del calendario')
    if 'tipo' in data:
        if data['tipo'] not in ('google','manuale'):raise BadRequest('Scegli Google Calendar o eventi manuali')
        calendar.tipo=data['tipo']
    if not calendar.tipo:calendar.tipo='google'
    if 'google_calendar_url' in data:
        calendar.google_calendar_url=calendar_url(data['google_calendar_url']) if data['google_calendar_url'] else ''
    if calendar.tipo=='google' and not calendar.google_calendar_url:raise BadRequest('Inserisci il link del calendario Google pubblico')
    if 'colore' in data:
        if not isinstance(data['colore'],str) or not re.fullmatch(r'#[a-fA-F0-9]{6}',data['colore']):raise BadRequest('Colore non valido')
        calendar.colore=data['colore']
    if 'is_pubblico' in data:
        if type(data['is_pubblico']) is not bool:raise BadRequest('Visibilità non valida')
        calendar.is_pubblico=data['is_pubblico']
    if 'ordine' in data:
        if type(data['ordine']) is not int or not 0<=data['ordine']<=10000:raise BadRequest('Ordine non valido')
        calendar.ordine=data['ordine']


def apply_event_fields(event,data):
    if not isinstance(data,dict):raise BadRequest('Appuntamento non valido')
    for key,limit in [('titolo',300),('luogo',500)]:
        value=data.get(key,getattr(event,key) or '')
        if not isinstance(value,str) or len(value)>limit:raise BadRequest('Valore non valido: '+key)
        setattr(event,key,value.strip())
    if not event.titolo:raise BadRequest('Indica il titolo dell’appuntamento')
    all_day=data.get('tutto_il_giorno',bool(event.tutto_il_giorno))
    if type(all_day) is not bool:raise BadRequest('Durata non valida')
    event.tutto_il_giorno=all_day
    for key in ('inizio','fine'):
        if key in data:
            value=data[key]
            if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',value):raise BadRequest('Indica data e ora valide')
            try:parsed=datetime.strptime(value,'%Y-%m-%dT%H:%M')
            except ValueError:raise BadRequest('Data non valida')
            if not 1900<=parsed.year<=2100:raise BadRequest('Anno non valido')
            setattr(event,key,parsed.replace(hour=0,minute=0) if all_day else parsed)
    if not event.inizio or not event.fine or event.fine<=event.inizio:raise BadRequest('La fine deve essere successiva all’inizio')


def calendar_month(calendar,month):
    from services.calendar_events import cached_calendar,expand_events,CalendarUnavailable
    start,end=month_range(month)
    if calendar.tipo!='manuale':
        url=calendar_url(calendar.google_calendar_url)
        if not url:raise CalendarUnavailable('Calendario non configurato')
        source=parse_qs(urlsplit(url).query)['src'][0]
        parsed,stale=cached_calendar(source)
        return dict(eventi=expand_events(parsed,start,end),obsoleto=stale,mese=start.strftime('%Y-%m'),configurato=True)
    first=start-timedelta(days=start.weekday());last=first+timedelta(days=42)
    rows=EventoCalendarioComunita.query.filter(EventoCalendarioComunita.calendario_id==calendar.id,EventoCalendarioComunita.inizio<datetime.combine(last,datetime.min.time()),EventoCalendarioComunita.fine>datetime.combine(first,datetime.min.time())).order_by(EventoCalendarioComunita.inizio,EventoCalendarioComunita.id).all()
    events=[]
    for event in rows:
        days=[];current=max(first,event.inizio.date());final=(event.fine-timedelta(microseconds=1)).date()
        while current<=final and current<last:days.append(current.isoformat());current+=timedelta(days=1)
        events.append(dict(event.to_dict(),id=f'locale:{calendar.id}:{event.id}',inizio=local_datetime(event.inizio).isoformat(),fine=local_datetime(event.fine).isoformat(),giorno=event.inizio.date().isoformat(),giorni=days,ora='' if event.tutto_il_giorno else event.inizio.strftime('%H:%M')))
    return dict(eventi=events,obsoleto=False,mese=start.strftime('%Y-%m'),configurato=True)
