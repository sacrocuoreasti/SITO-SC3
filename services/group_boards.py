from flask_login import current_user
from services.enrollment_options import GROUP_MODELS,manageable_people
from services.group_attendance import can_record
from services.catechismo_parents import group_people
from services.access_control import can


def visible_groups():
    own={p.codice_fiscale for p in manageable_people()}
    result={}
    for category,(model,collection) in GROUP_MODELS.items():
        if not can(category+'.bacheca'):continue
        for group in model.query.all():
            staff=can_record(category,group)
            member=any(p.codice_fiscale in own for p in group_people(group,collection))
            if staff or member:result[(category,group.id)]=(group,staff and can(category+'.avvisi'),member,staff)
    return result


def notice_data(notice,group,preview=False):
    return {'id':notice.id,'categoria':notice.categoria,'gruppo_id':notice.gruppo_id,'gruppo':group.nome,
            'argomento':notice.argomento,'titolo':notice.titolo,'contenuto':notice.contenuto[:1000] if preview else notice.contenuto,'anteprima':bool(preview and len(notice.contenuto)>1000),
            'is_pubblicato':notice.is_pubblicato,'created_at':notice.created_at.isoformat()+'Z'}
