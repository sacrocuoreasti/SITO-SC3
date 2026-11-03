"""Una nuova iscrizione al catechismo per persona e anno pastorale."""
import re
from sqlalchemy import text
from werkzeug.exceptions import Conflict
from flask import g
from models import db, Persona
from services.catechismo_parents import is_parent_group


def year_key(value):
    return re.sub(r'\s+', '', value or '').replace('-', '/') or '2026/2027'


def conflicting_group(person, group):
    if is_parent_group(group):
        return None
    return next((other for other in person.gruppi_catechismo
                 if other.id != group.id and not is_parent_group(other)
                 and year_key(other.anno_pastorale) == year_key(group.anno_pastorale)), None)


def ensure_unique(group, people, preserve_existing=True):
    for person in people:
        if preserve_existing and person in group.ragazzi:
            continue
        if conflicting_group(person, group):
            raise Conflict(f'{person.nominativo} è già iscritto a un gruppo di catechismo per l’anno {group.anno_pastorale}.')


def lock_enrollment(cfs):
    if g.get('catechismo_enrollment_locked'):
        return
    from services.cf_validator import normalizza_cf
    cfs=[normalizza_cf(cf) for cf in cfs if isinstance(cf,str)]
    if db.engine.dialect.name == 'sqlite':
        db.session.execute(text('BEGIN IMMEDIATE'))
    else:
        db.session.query(Persona).filter(Persona.codice_fiscale.in_(cfs)).order_by(Persona.codice_fiscale).with_for_update().all()
    db.session.expire_all()
    g.catechismo_enrollment_locked = True
