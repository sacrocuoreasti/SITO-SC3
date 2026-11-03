"""Assegnazioni multiple, compatibili con il precedente educatore singolo."""
from werkzeug.exceptions import BadRequest
from models import db, Utente
from services.access_control import can


def apply_educators(group,data):
    if 'educatori_ids' not in data:
        return
    ids=data['educatori_ids']
    if not isinstance(ids,list) or any(type(value) is not int for value in ids):
        raise BadRequest('Seleziona un elenco valido di educatori')
    ids=sorted(set(ids))
    users=Utente.query.filter(Utente.id.in_(ids)).order_by(Utente.id).all() if ids else []
    previous={u.id for u in group.educatori}|{group.educatore_utente_id}
    if len(users)!=len(ids) or any(u.id not in previous and (not u.is_attivo or not can('doposcuola.staff',u)) for u in users):
        raise BadRequest('Uno degli educatori non è disponibile o non ha il permesso Doposcuola staff')
    group.educatori=users
    primary=next((u for u in users if u.id==group.educatore_utente_id),users[0] if users else None)
    group.educatore_utente_id=primary.id if primary else None
    group.educatore_cf=primary.codice_fiscale if primary else None
    group.educatore_nome=', '.join(u.persona.nominativo if u.persona else u.email.split('@')[0] for u in users)[:120]
