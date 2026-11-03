from flask import Blueprint,request,jsonify
from flask_login import current_user
from werkzeug.exceptions import BadRequest,Forbidden,NotFound
from models import db,AvvisoGruppo
from services.group_boards import visible_groups,notice_data

bacheche_bp=Blueprint('bacheche_bp',__name__,url_prefix='/api/bacheche')


def accessible(category,id,write=False):
    info=visible_groups().get((category,id))
    if not info or (write and not info[1]):raise Forbidden('Bacheca non disponibile per questo profilo')
    return info[0],info[1]


def fields(notice,data):
    for key,limit in [('titolo',150),('contenuto',20000),('argomento',80)]:
        value=data.get(key,getattr(notice,key,None) or ('Comunicazioni' if key=='argomento' else ''))
        if not isinstance(value,str) or not value.strip() or len(value)>limit:raise BadRequest('Indica un valore valido per '+key)
        setattr(notice,key,value.strip())
    if 'is_pubblicato' in data:
        if type(data['is_pubblicato']) is not bool:raise BadRequest('Stato di pubblicazione non valido')
        notice.is_pubblicato=data['is_pubblicato']


@bacheche_bp.route('')
def overview():
    visible=visible_groups()
    from sqlalchemy import and_,or_
    conditions=[and_(AvvisoGruppo.categoria==category,AvvisoGruppo.gruppo_id==ident,True if info[1] else AvvisoGruppo.is_pubblicato.is_(True)) for (category,ident),info in visible.items()]
    rows=[]
    notices=AvvisoGruppo.query.filter(or_(*conditions)).order_by(AvvisoGruppo.created_at.desc(),AvvisoGruppo.id.desc()).limit(200).all() if conditions else []
    for notice in notices:
        info=visible.get((notice.categoria,notice.gruppo_id))
        if info and (notice.is_pubblicato or info[1]):rows.append(dict(notice_data(notice,info[0],preview=True),ambiti=(['famiglia'] if info[2] else [])+(['staff'] if info[3] else [])))
    return jsonify(avvisi=rows,gruppi=[{'categoria':category,'id':ident,'nome':info[0].nome,'puo_gestire':info[1],'ambiti':(['famiglia'] if info[2] else [])+(['staff'] if info[3] else [])} for (category,ident),info in visible.items()])


@bacheche_bp.route('/<category>/<int:id>',methods=['GET','POST'])
def group_board(category,id):
    group,write=accessible(category,id,request.method=='POST')
    if request.method=='POST':
        notice=AvvisoGruppo(categoria=category,gruppo_id=id,autore_id=current_user.id,is_pubblicato=True)
        fields(notice,request.get_json() or {});db.session.add(notice);db.session.commit()
        return jsonify(success=True,avviso=notice_data(notice,group)),201
    rows=AvvisoGruppo.query.filter_by(categoria=category,gruppo_id=id).order_by(AvvisoGruppo.created_at.desc(),AvvisoGruppo.id.desc()).all()
    return jsonify(gruppo=group.nome,puo_gestire=write,avvisi=[notice_data(n,group) for n in rows if n.is_pubblicato or write])


@bacheche_bp.route('/avvisi/<int:id>',methods=['PUT','DELETE'])
def update_notice(id):
    notice=db.session.get(AvvisoGruppo,id)
    if not notice:raise NotFound()
    group,_=accessible(notice.categoria,notice.gruppo_id,True)
    if request.method=='DELETE':db.session.delete(notice)
    else:fields(notice,request.get_json() or {})
    db.session.commit();return jsonify(success=True)
