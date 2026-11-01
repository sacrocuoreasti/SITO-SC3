"""Collegamenti Google Calendar normalizzati, senza richieste a URL esterni."""
import base64
from urllib.parse import urlsplit, parse_qs, urlencode
from werkzeug.exceptions import BadRequest


def calendar_url(value):
    if not isinstance(value,str):
        raise BadRequest('Link Google Calendar non valido')
    value=value.strip()
    if not value: return ''
    try:
        parts=urlsplit(value)
        if parts.scheme != 'https' or parts.hostname not in ('calendar.google.com','www.google.com') or not parts.path.startswith('/calendar/') or parts.username or parts.port:
            raise ValueError()
        query=parse_qs(parts.query)
        source=(query.get('src') or query.get('cid') or [''])[0]
        if '@' not in source:
            source=base64.urlsafe_b64decode(source + '='*((-len(source))%4)).decode('utf-8')
        if '@' not in source or len(source)>350 or any(c.isspace() or c in '<>"' for c in source):
            raise ValueError()
    except (ValueError, UnicodeError, TypeError):
        raise BadRequest('Inserisci il link del calendario Google con src o cid, disponibile in Impostazioni > Integra calendario')
    return 'https://calendar.google.com/calendar/embed?' + urlencode({'src':source,'ctz':'Europe/Rome','mode':'AGENDA'})


def apply_calendar(group,data):
    if 'google_calendar_url' in data and data['google_calendar_url'] != group.google_calendar_url:
        group.google_calendar_url=calendar_url(data['google_calendar_url'])


def calendar_info(group):
    try: return calendar_url(group.google_calendar_url or '')
    except BadRequest: return ''
