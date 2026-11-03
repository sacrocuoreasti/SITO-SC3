"""Catalogo dei menu e permessi applicati sia all'interfaccia sia alle API."""
import json
from flask import g,has_request_context,request
from flask_login import current_user

SECTIONS={
 'dashboard':('Panoramica',{'attivita':'Attività del nucleo','settimana':'Avvisi e settimana','cassa':'Statistiche e cassa (staff)'}),
 'famiglia':('La mia famiglia',{'membri':'Anagrafica e residenza','contatti':'Contatti','documenti':'Documenti e certificati','salute':'Fascicolo sanitario','accessi':'Accessi dei membri','inviti':'Inviti e richieste','iscrizioni':'Iscrizioni del nucleo','offerte':'Offerte e sostegno'}),
 'attivita':('Attività e iscrizioni',{'catalogo':'Catalogo','passati':'Eventi passati','iscrizioni':'Iscrizione e disiscrizione','gestione':'Creazione, modifica e pubblicazione (staff)'}),
 'calendari':('Calendari e appuntamenti',{'comunita':'Calendari della comunità','gruppi':'Calendari dei propri gruppi'}),
 'oratorio':('Oratorio',{'estivo':'Oratorio estivo','invernale':'Oratorio invernale','staff':'Gestione pastorale (staff)','elenco':'Elenco iscritti','salute':'Fascicoli sanitari','appelli':'Incontri e appelli','calendario':'Calendario del gruppo','storico':'Storico e statistiche','gestione':'Crea e modifica gruppi','assegnazioni':'Assegna e rimuovi iscritti','tutti':'Accesso a tutti i gruppi','cucina':'Quadro sanitario e cucina'}),
 'catechismo':('Catechismo',{'staff':'Gestione pastorale (staff)','elenco':'Elenco iscritti','salute':'Fascicoli sanitari','appelli':'Incontri e appelli','calendario':'Calendario del gruppo','storico':'Storico e statistiche','gestione':'Crea e modifica gruppi','assegnazioni':'Assegna e rimuovi iscritti','tutti':'Accesso a tutti i gruppi','genitori':'Gruppi genitori'}),
 'doposcuola':('Doposcuola',{'staff':'Gestione pastorale (staff)','elenco':'Elenco iscritti','salute':'Fascicoli sanitari','appelli':'Incontri e appelli','calendario':'Calendario del gruppo','storico':'Storico e statistiche','gestione':'Crea e modifica gruppi','assegnazioni':'Assegna e rimuovi iscritti','tutti':'Accesso a tutti i gruppi'}),
 'segreteria':('Segreteria',{'iscrizioni':'Iscrizioni e cassa quote','pagamenti':'Pagamenti e ricevute','liste':'Liste parrocchiali','celebrazioni':'Messe e liturgia','homepage':'Homepage pubblica','calendari':'Calendari comunitari','avvisi':'Avvisi ed eventi','configurazioni':'Configurazioni e clausole','campi_account':'Campi personalizzati account'}),
 'anagrafica':('Anagrafica parrocchiale',{'elenco':'Consultazione','gestione':'Inserimento, modifica e cancellazione','contatti':'Contatti','nuclei':'Nuclei familiari','documenti':'Documenti e certificati','salute':'Fascicoli sanitari','liste':'Badge e liste'}),
 'excel':('Importa ed esporta Excel',{'template':'Scarica modello','import':'Importazione','export':'Esportazione'}),
 'utenti':('Utenti e privilegi',{'elenco':'Consultazione account','gestione':'Gestione account (solo admin)','permessi':'Ruoli, privilegi e permessi (solo admin)'})}
KEYS={key for section,(_,children) in SECTIONS.items() for key in [section,*[section+'.'+child for child in children]]}
ADMIN_ONLY={'utenti.gestione','utenti.permessi'}

def subtree(section): return {key for key in KEYS if key==section or key.startswith(section+'.')}
USER=set().union(*(subtree(s) for s in ('dashboard','famiglia','attivita','calendari','oratorio','catechismo','doposcuola')))-{'dashboard.cassa','attivita.gestione'}
for section in ('oratorio','catechismo','doposcuola'):
    USER-={section+'.'+child for child in ('staff','gestione','assegnazioni','tutti','cucina','appelli','elenco','salute')}
STAFF=KEYS-ADMIN_ONLY
DEFAULTS={
 'admin':('Admin','ruolo',KEYS),
 'segreteria':('Segreteria','ruolo',STAFF),
 'utente':('Utente','ruolo',USER),
 'animatore':('Animatore','privilegio',{'dashboard','dashboard.attivita','dashboard.settimana'}|subtree('oratorio')-{'oratorio.gestione','oratorio.assegnazioni','oratorio.cucina'}),
 'responsabile_oratorio':('Responsabile oratorio','privilegio',{'dashboard','dashboard.attivita','dashboard.settimana'}|subtree('oratorio')),
 'catechista':('Catechista','privilegio',{'dashboard','dashboard.attivita','dashboard.settimana'}|subtree('catechismo')-{'catechismo.gestione','catechismo.assegnazioni','catechismo.tutti'}),
 'educatore':('Educatore (incarico precedente)','privilegio',{'dashboard','dashboard.attivita','dashboard.settimana'}|subtree('doposcuola')-{'doposcuola.gestione','doposcuola.assegnazioni','doposcuola.tutti'})}
ALIASES={'genitore':'utente','parroco':'segreteria','oratorio':'responsabile_oratorio','doposcuola':'educatore'}

def raw_roles(user):
    roles={user.ruolo}
    try:
        extra=json.loads(user.privilegi_extra or '[]')
        if isinstance(extra,list):roles.update(value for value in extra if isinstance(value,str))
    except (ValueError,TypeError): pass
    return roles

def is_admin(user=None):
    user=user or current_user
    return bool(user.is_authenticated and 'admin' in raw_roles(user))

def definitions():
    if has_request_context() and hasattr(g,'access_definitions'):return g.access_definitions
    from models import DefinizioneAccesso
    result={key:{'chiave':key,'nome':value[0],'tipo':value[1],'permessi':sorted(value[2]),'predefinito':True} for key,value in DEFAULTS.items()}
    for row in DefinizioneAccesso.query.all():
        result[row.chiave]={'chiave':row.chiave,'nome':row.nome,'tipo':row.tipo,'permessi':json.loads(row.permessi),'predefinito':row.chiave in DEFAULTS}
    if has_request_context():g.access_definitions=result
    return result

def assigned(user):
    config=definitions();raw=raw_roles(user)
    primary=ALIASES.get(user.ruolo,user.ruolo)
    base='admin' if is_admin(user) else primary if primary in config and config[primary]['tipo']=='ruolo' else 'utente'
    profiles={base}|{ALIASES.get(role,role) for role in raw if ALIASES.get(role,role) in config}
    return base,profiles

def permissions(user=None):
    user=user or current_user
    if not user.is_authenticated:return set()
    if is_admin(user):return set(KEYS)
    _,profiles=assigned(user);config=definitions();grants=set()
    for key in profiles:grants.update(config[key]['permessi'])
    # Ogni voce richiede anche il menu genitore; gli incarichi si sommano.
    return {key for key in grants-ADMIN_ONLY if key.split('.')[0] in grants}

def can(key,user=None):return key in permissions(user)

def technical_roles(user):
    base,profiles=assigned(user);roles=set(profiles)|{base}
    if is_admin(user):return ['admin']
    grants=permissions(user)
    if base=='segreteria' or any(key in grants for key in ('anagrafica','excel','segreteria','attivita.gestione','utenti.elenco')):roles.add('segreteria')
    if 'catechismo.staff' in grants:roles.add('catechista')
    if 'oratorio.staff' in grants:roles.add('oratorio' if 'oratorio.tutti' in grants else 'animatore')
    if 'doposcuola.staff' in grants:roles.add('educatore')
    return sorted(roles)

def identity(user):
    base,profiles=assigned(user);config=definitions()
    return {'ruolo_base':base,'privilegi':[key for key in sorted(profiles) if config[key]['tipo']=='privilegio'],
            'profili_accesso':sorted(profiles),'permessi':sorted(permissions(user)),'is_admin':is_admin(user)}

def staff_scope(user=None):
    user=user or current_user
    if is_admin(user):return True
    if not user.is_authenticated:return False
    if not has_request_context():return assigned(user)[0]=='segreteria'
    blueprint=request.blueprint or ''
    if blueprint in ('persone_bp','documenti_bp','famiglie_bp','auth_bp'):
        return can('anagrafica.gestione',user)
    if blueprint=='iscrizioni_bp':return can('segreteria.iscrizioni',user) or can('attivita.gestione',user)
    if blueprint=='attivita_bp':return can('attivita.gestione',user)
    if blueprint=='celebrazioni_bp':return can('segreteria.celebrazioni',user)
    return assigned(user)[0]=='segreteria'

def required_permissions():
    """Ogni API privata viene associata a un menu o a una sua funzione."""
    bp=request.blueprint or '';path=request.path;write=request.method not in ('GET','HEAD','OPTIONS');end=request.endpoint or ''
    if bp=='accessi_bp':return []
    if bp=='backup_bp':return ['__admin__']
    if bp=='auth_bp':return [] # accesso e profilo personale non dipendono dai menu
    if bp=='utenti_bp':return ['utenti', 'utenti.elenco'] if not write else ['__admin__']
    if bp=='segreteria_bp':return ['dashboard.cassa']
    if bp=='excel_bp':return ['excel','excel.import' if write else ('excel.template' if path.endswith('/template') else 'excel.export')]
    if bp=='liste_bp':return ['anagrafica.liste'] if can('anagrafica.liste') else ['segreteria.liste']
    if bp=='iscrizioni_bp':
        if 'pagamento' in path:return ['segreteria.pagamenti']
        if any(word in path for word in ('bulk-delete','/squadra')):return ['segreteria.iscrizioni']
        if '/stato' in path and (request.get_json(silent=True) or {}).get('stato')!='annullata':return ['segreteria.iscrizioni']
        if request.method=='POST' and path.rstrip('/')=='/api/iscrizioni':return ['attivita.iscrizioni']
        return ['segreteria.iscrizioni'] if can('segreteria.iscrizioni') else ['attivita.iscrizioni'] if can('attivita.iscrizioni') else ['famiglia.iscrizioni']
    if bp=='celebrazioni_bp':return ['segreteria.celebrazioni'] if write else []
    if bp=='configurazioni_bp':return [('segreteria.campi_account' if 'campi-account' in path else 'segreteria.configurazioni')] if write else []
    if bp=='impostazioni_bp':
        if not write:return []
        return ['segreteria.'+('calendari' if '/calendari' in path else 'avvisi' if '/eventi' in path else 'homepage')]
    if bp=='attivita_bp':return ['attivita.gestione'] if write else []
    if bp=='calendari_gruppi_bp':
        category=(request.view_args or {}).get('category','')
        if category not in ('oratorio','catechismo','doposcuola'):return []
        if path.endswith('/registro'):child='appelli'
        elif path.endswith('/elenco'):child='assegnazioni' if write else 'elenco'
        elif path.endswith('/assegnabili'):child='assegnazioni'
        else:return [category,category+'.calendario']
        return [category,category+'.'+child]
    if bp in ('oratorio_bp','catechismo_bp','doposcuola_bp'):
        category=bp[:-3];caps=[category]
        if path.rsplit('/',1)[-1] in ('animatori','catechisti','educatori'):child='gestione'
        elif 'allergie' in path:child='salute'
        elif '/storico' in path:child='storico'
        elif '/presenze' in path or '/registro' in path or '/incontri/' in path:child='appelli'
        elif 'assegnabili' in path or (write and any(part in path for part in ('/ragazzi','/studenti'))):child='assegnazioni'
        elif write and '/gruppi' in path:child='gestione'
        elif path.endswith('/iscrivi-figlio'):child=None
        else:child=None
        if child:caps.append(category+'.'+child)
        return caps
    if bp=='famiglie_bp':
        if path.endswith('/opportunita'):return [] # autorizzazioni filtrate nella risposta
        if '/registri-gruppi/' in path:return [(request.view_args or {}).get('category','famiglia')]
        if path.endswith('/calendari-gruppi'):return ['calendari.gruppi']
        if path.endswith('/iscrizioni-gruppo'):
            data=request.get_json(silent=True) or {};return [data.get('categoria','famiglia')]
        if path.endswith('/offerte'):return ['famiglia.offerte']
        if '/account' in path:return ['famiglia.accessi']
        if '/richieste' in path:return ['famiglia.inviti']
        return ['famiglia.membri'] if can('famiglia') else ['anagrafica.nuclei']
    if bp=='persone_bp':
        child='documenti' if 'certificato' in path else 'gestione' if write else 'elenco'
        if can('anagrafica.'+child):return ['anagrafica.'+child]
        # Le verifiche di proprietà dei percorsi esistenti restano attive.
        return ['famiglia.'+('documenti' if child=='documenti' else 'membri')]
    if bp=='documenti_bp':return ['anagrafica.documenti'] if can('anagrafica.documenti') else ['famiglia.documenti']
    return ['__admin__'] # le nuove API private richiedono una mappatura esplicita

def authorize_request():
    from werkzeug.exceptions import Forbidden
    if is_admin():return
    for key in required_permissions():
        if key=='__admin__' or not can(key):raise Forbidden('Questa funzione è disattivata per i tuoi ruoli e privilegi')
    if request.blueprint in ('oratorio_bp','catechismo_bp','doposcuola_bp'):
        category=request.blueprint[:-3]
        private=any(word in request.path for word in ('allergie','registro','storico','presenze')) or request.method not in ('GET','HEAD','OPTIONS')
        if private and not request.path.endswith('/iscrivi-figlio'):
            data=request.get_json(silent=True) or {}
            ident=(request.view_args or {}).get('id') or data.get('gruppo_id')
            if ident:
                from models import db
                from services.enrollment_options import GROUP_MODELS
                from services.group_attendance import can_record
                group=db.session.get(GROUP_MODELS[category][0],ident)
                if group and not can_record(category,group):raise Forbidden('Gruppo non assegnato al tuo profilo')

def catalog():
    return [{'chiave':section,'nome':label,'figli':[{'chiave':section+'.'+key,'nome':name,'solo_admin':section+'.'+key in ADMIN_ONLY} for key,name in children.items()]} for section,(label,children) in SECTIONS.items()]

HEALTH_FIELDS={'allergie','intolleranze_alimentari','terapie_medicinali','note_mediche','note_generali'}
DOCUMENT_FIELDS={'documenti','certificato_battesimo_path','certificato_battesimo_url'}

def profile_prefix():
    return 'anagrafica' if can('anagrafica.gestione') or can('anagrafica.elenco') else 'famiglia'

def restrict_profile_data(data):
    if not current_user.is_authenticated or is_admin():return data
    prefix=profile_prefix();result=dict(data)
    if not can(prefix+'.salute'):
        for key in HEALTH_FIELDS:result.pop(key,None)
    return result

def filter_response(response):
    if not current_user.is_authenticated or is_admin() or not response.is_json:return response
    bp=request.blueprint or ''
    if bp in ('accessi_bp','configurazioni_bp'):return response
    if bp in ('oratorio_bp','catechismo_bp','doposcuola_bp'):prefix=bp[:-3]
    elif bp=='calendari_gruppi_bp':prefix=(request.view_args or {}).get('category','famiglia')
    elif bp=='persone_bp':prefix=profile_prefix()
    elif bp=='utenti_bp':prefix='anagrafica'
    elif bp=='famiglie_bp' and '/registri-gruppi/' in request.path:prefix=(request.view_args or {}).get('category','famiglia')
    elif bp=='famiglie_bp' and not request.path.endswith('/mia') and can('anagrafica.nuclei'):prefix='anagrafica'
    else:prefix='famiglia'
    strip=set()
    if not can(prefix+'.salute'):strip|=HEALTH_FIELDS
    if prefix in ('famiglia','anagrafica') and not can(prefix+'.documenti'):strip|=DOCUMENT_FIELDS
    def clean(value):
        if isinstance(value,dict):return {key:clean(item) for key,item in value.items() if key not in strip}
        if isinstance(value,list):return [clean(item) for item in value]
        return value
    if strip:response.set_data(json.dumps(clean(response.get_json())))
    return response

def validate_assignment(role,privileges):
    from werkzeug.exceptions import BadRequest
    config=definitions()
    if role not in config or config[role]['tipo']!='ruolo':raise BadRequest('Seleziona un ruolo base valido')
    if not isinstance(privileges,list) or any(not isinstance(value,str) for value in privileges):raise BadRequest('Elenco dei privilegi non valido')
    # I client precedenti ripetevano il ruolo principale tra gli extra.
    values=sorted(set(privileges)-{role})
    if any(value not in config or config[value]['tipo']!='privilegio' for value in values):raise BadRequest('Seleziona privilegi validi')
    return role,values

def retain_admin(excluded_ids):
    from models import Utente
    from werkzeug.exceptions import BadRequest
    active=Utente.query.filter_by(is_attivo=True).all()
    if not any(user.id not in excluded_ids and is_admin(user) for user in active):raise BadRequest('Deve rimanere almeno un amministratore attivo')
