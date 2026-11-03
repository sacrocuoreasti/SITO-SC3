from flask import Blueprint,jsonify,request
from werkzeug.exceptions import BadRequest,Forbidden,NotFound,Conflict
from sqlalchemy import text
import re
from models import db,GruppoGiovani,Utente,Presenza,AvvisoGruppo
from services.access_control import can,is_admin
from services.group_attendance import can_record
from services.group_age_service import apply_age_range
from services.group_calendar import apply_calendar
from services.community_calendars import current_pastoral_year
from services.catechismo_membership import year_key

giovani_bp=Blueprint('giovani_bp',__name__,url_prefix='/api/giovani')


def fields(group,data):
    for key,limit in [('nome',120),('anno_pastorale',20),('orario_incontri',100),('aula',50),('note',20000)]:
        if key in data:
            value=data[key]
            if not isinstance(value,str) or len(value)>limit:raise BadRequest('Valore non valido: '+key)
            setattr(group,key,value.strip())
    if not group.nome or not group.anno_pastorale:raise BadRequest('Indica nome e anno pastorale')
    year=year_key(group.anno_pastorale)
    if not re.fullmatch(r'\d{4}/\d{4}',year) or int(year[5:])!=int(year[:4])+1:raise BadRequest('Indica un anno pastorale valido, per esempio 2026/2027')
    group.anno_pastorale=year
    if 'stato' in data:
        if data['stato'] not in ('pubblico','bozza','chiuso'):raise BadRequest('Stato non valido')
        group.stato=data['stato']
    if 'catechisti_ids' in data:
        ids=data['catechisti_ids']
        if not isinstance(ids,list) or any(type(i) is not int for i in ids):raise BadRequest('Responsabili non validi')
        users=Utente.query.filter(Utente.id.in_(set(ids))).order_by(Utente.id).all() if ids else []
        previous={u.id for u in group.catechisti}
        if len(users)!=len(set(ids)) or any(u.id not in previous and (not u.is_attivo or not can('giovani.staff',u)) for u in users):raise BadRequest('Seleziona responsabili con il permesso Gruppi giovani staff')
        group.catechisti=users
        group.catechista_utente_id=users[0].id if users else None
        group.catechista_nome=', '.join(u.persona.nominativo if u.persona else u.email.split('@')[0] for u in users)[:120]
    apply_age_range(group,data);apply_calendar(group,data)


def lock_groups():
    if db.engine.dialect.name=='sqlite':db.session.execute(text('BEGIN IMMEDIATE'))
    else:db.session.query(GruppoGiovani).with_for_update().all()


def check_slots(group):
    with db.session.no_autoflush:
        others=GruppoGiovani.query.filter(GruppoGiovani.id!=group.id).all() if group.id else GruppoGiovani.query.all()
    if sum(year_key(other.anno_pastorale)==year_key(group.anno_pastorale) for other in others)>=2:raise Conflict('Sono consentiti al massimo due gruppi giovani per anno pastorale')


@giovani_bp.route('/gruppi',methods=['GET','POST'])
def groups():
    if request.method=='GET':
        rows=[g for g in GruppoGiovani.query.order_by(GruppoGiovani.anno_pastorale.desc(),GruppoGiovani.nome).all() if can_record('giovani',g)]
        return jsonify(gruppi=[g.to_dict(include_ragazzi=False) for g in rows],anno_pastorale_corrente=current_pastoral_year())
    lock_groups()
    group=GruppoGiovani(anno_pastorale=current_pastoral_year(),stato='pubblico')
    fields(group,request.get_json() or {});check_slots(group)
    db.session.add(group);db.session.commit()
    return jsonify(success=True,gruppo=group.to_dict(include_ragazzi=False)),201


@giovani_bp.route('/gruppi/<int:id>',methods=['PUT','DELETE'])
def update_group(id):
    lock_groups()
    group=db.session.get(GruppoGiovani,id)
    if not group:raise NotFound()
    if not can_record('giovani',group):raise Forbidden('Gruppo non assegnato')
    if request.method=='DELETE':
        if group.ragazzi or Presenza.query.filter_by(gruppo_categoria='giovani',gruppo_id=id).first() or AvvisoGruppo.query.filter_by(categoria='giovani',gruppo_id=id).first():raise BadRequest('Il gruppo contiene iscritti, appelli o avvisi: puoi chiuderlo per conservarne lo storico')
        db.session.delete(group)
    else:
        fields(group,request.get_json() or {});check_slots(group)
    db.session.commit();return jsonify(success=True)


@giovani_bp.route('/responsabili')
def staff():
    if not can('giovani.gestione'):raise Forbidden()
    return jsonify(responsabili=[{'id':u.id,'nominativo':u.persona.nominativo if u.persona else u.email,'email':u.email} for u in Utente.query.filter_by(is_attivo=True).all() if can('giovani.staff',u)])
