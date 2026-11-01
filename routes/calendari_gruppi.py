from flask import Blueprint,jsonify,request
from flask_login import current_user
from werkzeug.exceptions import Forbidden,NotFound
from models import db
from services.enrollment_options import GROUP_MODELS,manageable_people,group_candidates,age_eligible
from services.group_attendance import can_record,group_records
from services.calendar_events import group_events,CalendarUnavailable

calendari_gruppi_bp=Blueprint('calendari_gruppi_bp',__name__,url_prefix='/api/calendari-gruppi')


@calendari_gruppi_bp.route('/<category>/<int:id>')
def get_month(category,id):
    if category not in GROUP_MODELS: raise NotFound()
    model,collection=GROUP_MODELS[category]
    group=db.session.get(model,id)
    if not group: raise NotFound()
    manages=can_record(category,group)
    enrolled=[p for p in manageable_people() if p in getattr(group,collection)]
    eligible=group.stato=='pubblico' and any(age_eligible(p,group) for p in group_candidates())
    if not manages and not enrolled and not eligible: raise Forbidden('Calendario non disponibile per questo profilo')
    try: data=group_events(group,request.args.get('mese'))
    except CalendarUnavailable as error:
        return jsonify(error=str(error),eventi=[],configurato=True),502
    records=group_records(category,group,None if manages else enrolled)
    data.update(categoria=category,gruppo_id=group.id,nome_gruppo=group.nome,puo_registrare_presenze=bool(manages),iscritto=bool(enrolled))
    data['presenze']=[{'data':record.data.isoformat(),'nominativo':record.persona.nominativo,'presente':record.presente} for record in records if record.data.isoformat()[:7]==data['mese']]
    return jsonify(data)
