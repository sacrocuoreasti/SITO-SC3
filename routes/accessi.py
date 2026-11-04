import json,re
from flask import Blueprint,jsonify,request,g
from werkzeug.exceptions import Forbidden,BadRequest
from models import db,DefinizioneAccesso
from services.access_control import definitions,catalog,is_admin,KEYS,ADMIN_ONLY,DEFAULTS

accessi_bp=Blueprint('accessi_bp',__name__,url_prefix='/api/accessi')

@accessi_bp.before_request
def require_admin():
    if not is_admin():raise Forbidden('Configurazione riservata agli amministratori')

@accessi_bp.route('',methods=['GET'])
def get_definitions():
    return jsonify(profili=list(definitions().values()),viste=catalog())


def fields(data,existing=None):
    name=data.get('nome',existing['nome'] if existing else '')
    kind=data.get('tipo',existing['tipo'] if existing else 'ruolo')
    grants=data.get('permessi',existing['permessi'] if existing else [])
    if not isinstance(name,str) or not name.strip() or len(name)>100:raise BadRequest('Indica un nome di massimo 100 caratteri')
    if kind not in ('ruolo','privilegio'):raise BadRequest('Tipo di profilo non valido')
    if not isinstance(grants,list) or any(not isinstance(key,str) or key not in KEYS for key in grants):raise BadRequest('Elenco delle viste non valido')
    grants=set(grants)-ADMIN_ONLY
    # Una funzione può essere attiva solo insieme al proprio menu laterale.
    if any(key.split('.')[0] not in grants for key in grants):raise BadRequest('Attiva il menu prima dei suoi sottomenu')
    return name.strip(),kind,sorted(grants)

@accessi_bp.route('',methods=['POST'])
def create_definition():
    data=request.get_json() or {};key=data.get('chiave','')
    if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9_]{1,29}',key):raise BadRequest('Usa un codice di 2–30 lettere minuscole, numeri o underscore')
    if key in definitions() or key in ('parroco','genitore','oratorio','doposcuola'):raise BadRequest('Codice già utilizzato o riservato')
    name,kind,grants=fields(data)
    db.session.add(DefinizioneAccesso(chiave=key,nome=name,tipo=kind,permessi=json.dumps(grants)))
    db.session.commit();g.pop('access_definitions',None)
    return jsonify(success=True,profilo=definitions()[key]),201

@accessi_bp.route('/<key>',methods=['PUT'])
def update_definition(key):
    if key=='admin':raise BadRequest('Admin mantiene sempre accesso completo')
    existing=definitions().get(key)
    if not existing:raise BadRequest('Profilo non trovato')
    name,kind,grants=fields(request.get_json() or {},existing)
    if kind!=existing['tipo']:raise BadRequest('Non puoi cambiare il tipo di un profilo già esistente')
    row=db.session.get(DefinizioneAccesso,key)
    if not row:row=DefinizioneAccesso(chiave=key);db.session.add(row)
    row.nome=name;row.tipo=kind;row.permessi=json.dumps(grants);row.versione_viste=1
    db.session.commit();g.pop('access_definitions',None)
    return jsonify(success=True,profilo=definitions()[key])


@accessi_bp.route('/<key>',methods=['DELETE'])
def delete_definition(key):
    from models import Utente
    from services.access_control import raw_roles
    if key in DEFAULTS:
        raise BadRequest('I profili di sistema non possono essere eliminati; puoi configurarne nome e viste.')
    row=db.session.get(DefinizioneAccesso,key)
    if not row:
        return jsonify(error='Profilo non trovato'),404
    count=sum(key in raw_roles(user) for user in Utente.query.all())
    if count:
        return jsonify(error=f'Profilo assegnato a {count} account: rimuovi prima le assegnazioni per eliminarlo.',assegnazioni=count),409
    db.session.delete(row)
    db.session.commit();g.pop('access_definitions',None)
    return jsonify(success=True)
