"""Appuntamenti Google in sola lettura: feed pubblico, cache limitata e ricorrenze."""
import calendar as month_calendar
import hashlib
import re
import threading
import time
from collections import OrderedDict
from datetime import date,datetime,timedelta
from urllib.parse import parse_qs,urlsplit,quote
from urllib.request import Request,build_opener,HTTPRedirectHandler
from dateutil.tz import gettz
from icalendar import Calendar
import recurring_ical_events
from werkzeug.exceptions import BadRequest
from services.group_calendar import calendar_info

ROME=gettz('Europe/Rome')
_cache=OrderedDict()
_lock=threading.Lock()
_locks={}

class CalendarUnavailable(Exception): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def month_range(value=None):
    try:
        start=datetime.strptime(value or datetime.now(ROME).strftime('%Y-%m'),'%Y-%m').date()
        if start.strftime('%Y-%m') != (value or start.strftime('%Y-%m')) or not 1900 <= start.year <= 2100: raise ValueError()
    except (ValueError,TypeError): raise BadRequest('Mese non valido: usa AAAA-MM')
    end=start+timedelta(days=month_calendar.monthrange(start.year,start.month)[1])
    return start,end


def fetch_public_feed(source):
    # Host e percorso costruiti dal server; nessun redirect o URL arbitrario.
    url='https://calendar.google.com/calendar/ical/'+quote(source,safe='')+'/public/basic.ics'
    try:
        with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'CuoreInRete/Calendar','Accept':'text/calendar'}),timeout=8) as response:
            body=response.read(2*1024*1024+1)
        if len(body)>2*1024*1024 or b'BEGIN:VCALENDAR' not in body[:2048]: raise ValueError()
        return body
    except Exception:
        raise CalendarUnavailable('Calendario non leggibile. Controlla che sia pubblico o riprova più tardi.') from None


def cached_calendar(source):
    now=time.monotonic()
    with _lock:
        entry=_cache.get(source)
        if entry and entry['expires']>now:
            _cache.move_to_end(source)
            if entry.get('error'): raise CalendarUnavailable(entry['error'])
            return entry['calendar'],entry.get('stale',False)
        if source not in _locks and len(_locks)>=64: raise CalendarUnavailable('Calendario occupato. Riprova tra poco.')
        source_lock=_locks.setdefault(source,threading.Lock())
    if not source_lock.acquire(timeout=1):
        raise CalendarUnavailable('Aggiornamento calendario in corso. Riprova tra poco.')
    try:
        with _lock:
            entry=_cache.get(source)
            if entry and entry['expires']>time.monotonic():
                if entry.get('error'): raise CalendarUnavailable(entry['error'])
                return entry['calendar'],entry.get('stale',False)
        try:
            parsed=Calendar.from_ical(fetch_public_feed(source))
            components=parsed.walk('VEVENT')
            if len(components)>2500: raise CalendarUnavailable('Calendario troppo grande per la visualizzazione.')
            for event in components:
                rule=event.get('RRULE')
                if rule and str(rule.get('FREQ',[''])[0]).upper() in ('SECONDLY','MINUTELY','HOURLY'):
                    raise CalendarUnavailable('Il calendario contiene ricorrenze troppo frequenti per il registro.')
            entry={'calendar':parsed,'expires':time.monotonic()+300,'created':time.monotonic(),'stale':False}
        except Exception as error:
            message=str(error) if isinstance(error,CalendarUnavailable) else 'Calendario Google non disponibile o non valido.'
            if entry and entry.get('calendar') and now-entry.get('created',0)<86400:
                entry={**entry,'expires':time.monotonic()+30,'stale':True}
                with _lock: _cache[source]=entry
                return entry['calendar'],True
            entry={'error':message,'expires':time.monotonic()+30}
        with _lock:
            _cache[source]=entry;_cache.move_to_end(source)
            while len(_cache)>32: _cache.popitem(last=False)
        if entry.get('error'): raise CalendarUnavailable(entry['error'])
        return entry['calendar'],entry.get('stale',False)
    finally:
        source_lock.release()
        with _lock:
            if not source_lock.locked(): _locks.pop(source,None)


def local_datetime(value):
    if isinstance(value,datetime):
        return value.replace(tzinfo=ROME) if value.tzinfo is None else value.astimezone(ROME)
    return datetime.combine(value,datetime.min.time()).replace(tzinfo=ROME)


def expand_events(parsed,start,end):
    grid_start=start-timedelta(days=start.weekday())
    grid_end=grid_start+timedelta(days=42)
    try:
        instances=recurring_ical_events.of(parsed).between(local_datetime(grid_start),local_datetime(grid_end))
        if len(instances)>5000: raise ValueError()
        events={}
        for event in instances:
            if str(event.get('STATUS','')).upper()=='CANCELLED': continue
            first=event.decoded('DTSTART');last=event.decoded('DTEND',first)
            begins=local_datetime(first);ends=local_datetime(last)
            all_day=not isinstance(first,datetime)
            if ends<=begins: ends=begins+timedelta(days=1) if all_day else begins
            identity=event.get('RECURRENCE-ID')
            identity=str(identity.dt) if identity else begins.isoformat()
            key=hashlib.sha256((str(event.get('UID',''))+'|'+identity).encode()).hexdigest()[:24]
            last_day=(ends-timedelta(microseconds=1)).date() if ends>begins else begins.date()
            days=[];current=max(begins.date(),grid_start)
            while current<=last_day and current<grid_end:
                days.append(current.isoformat());current+=timedelta(days=1)
            if not days: continue
            events[key]={'id':key,'titolo':str(event.get('SUMMARY','Incontro'))[:300],
                         'luogo':str(event.get('LOCATION',''))[:500], 'inizio':begins.isoformat(),
                         'fine':ends.isoformat(),'giorno':begins.date().isoformat(),'giorni':days,
                         'tutto_il_giorno':all_day,'ora':'' if all_day else begins.strftime('%H:%M')}
        return sorted(events.values(),key=lambda e:(e['inizio'],e['id']))
    except Exception:
        raise CalendarUnavailable('Impossibile interpretare gli appuntamenti del calendario.') from None


def group_events(group,month=None):
    start,end=month_range(month)
    url=calendar_info(group)
    if not url: return {'eventi':[],'configurato':False,'mese':start.strftime('%Y-%m'),'obsoleto':False}
    source=parse_qs(urlsplit(url).query)['src'][0]
    parsed,stale=cached_calendar(source)
    return {'eventi':expand_events(parsed,start,end),'configurato':True,'mese':start.strftime('%Y-%m'),'obsoleto':stale}


def calendar_dates(group,month=None):
    try:
        data=group_events(group,month)
    except CalendarUnavailable as error:
        return [],str(error)
    result={}
    for event in data['eventi']:
        for day in event['giorni']:
            if day[:7]!=data['mese']: continue
            item=result.setdefault(day,{'data':day,'data_it':datetime.strptime(day,'%Y-%m-%d').strftime('%d/%m/%Y'),
                'titolo_incontro':'','concorre_percentuale':True,'presenti_count':0,'assenti_count':0,'da_google':True,'registrato':False})
            titles=item['titolo_incontro'].split(' · ') if item['titolo_incontro'] else []
            if event['titolo'] not in titles: titles.append(event['titolo'])
            item['titolo_incontro']=' · '.join(titles)
    return list(result.values()),'Google non raggiungibile: mostrata l’ultima copia disponibile.' if data['obsoleto'] else ''


def merge_calendar_dates(group,dates,month=None):
    scheduled,warning=calendar_dates(group,month)
    merged={row['data']:dict(row) for row in scheduled}
    for row in dates:
        previous=merged.get(row['data'],{})
        merged[row['data']]={**previous,**row,'registrato':True,
            'titolo_incontro':row.get('titolo_incontro') or previous.get('titolo_incontro','')}
    return sorted(merged.values(),key=lambda row:row['data']),warning


def group_year_dates(group,dates):
    """Tutti gli incontri dell'anno pastorale, oltre all'intero storico salvato."""
    match=re.match(r'^(\d{4})[/-](\d{4})$',getattr(group,'anno_pastorale','') or '')
    today=datetime.now(ROME)
    year=int(match[1]) if match else today.year-(today.month<9)
    if not 1900<=year<2100: raise BadRequest('Anno pastorale non valido')
    scheduled=[];warnings=[]
    for offset in range(12):
        month=(8+offset)%12+1
        current_year=year+(8+offset)//12
        rows,warning=calendar_dates(group,f'{current_year:04d}-{month:02d}')
        scheduled.extend(rows)
        if warning and warning not in warnings: warnings.append(warning)
    merged={row['data']:dict(row) for row in scheduled}
    for row in dates:
        previous=merged.get(row['data'],{})
        merged[row['data']]={**previous,**row,'registrato':True,
            'titolo_incontro':row.get('titolo_incontro') or previous.get('titolo_incontro','')}
    return sorted(merged.values(),key=lambda row:row['data']),' '.join(warnings)
