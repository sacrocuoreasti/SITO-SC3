"""Regole condivise per nucleo, salute e registrazione."""
import json
from datetime import datetime
from flask_login import current_user

FAMILY_ROLES = ('Padre', 'Madre', 'Figlio/a', 'Fratello', 'Sorella', 'Nonno', 'Nonna', 'Coniuge', 'Tutore Legale', 'Altro')
HEALTH_PRESETS = {
    'allergie': ['Acari', 'Graminacee', 'Polline', 'Arachidi e frutta secca', 'Punture di insetti', 'Allergia a farmaci (specificare)'],
    'intolleranze_alimentari': ['Lattosio', 'Glutine / celiachia'],
    'terapie_medicinali': ['Terapia continuativa (specificare)', 'Farmaco al bisogno (specificare)', 'Farmaco salvavita prescritto (specificare)'],
}
REGISTRATION_CONSENTS = {
    'privacy': {'titolo': 'Informativa e Trattamento Dati Personali (GDPR)',
                'testo': 'Dichiaro di aver preso visione dell’informativa e acconsento al trattamento dei dati personali per la gestione delle attività parrocchiali. La dichiarazione riguarda tutta la famiglia, per i componenti per i quali sono legittimato a prestare il consenso.'},
    'foto_video': {'titolo': 'Consenso Riprese Foto e Video per la Comunità',
                   'testo': 'Autorizzo fotografie e riprese di gruppo delle attività parrocchiali per la bacheca e le comunicazioni della comunità. La dichiarazione riguarda tutta la famiglia, per i componenti per i quali sono legittimato a prestare il consenso.'},
}


def staff_user():
    return current_user.is_authenticated and bool(set(current_user.get_all_roles()) & {'admin', 'segreteria', 'parroco'})


def can_manage_family(family):
    return staff_user() or (current_user.is_authenticated and current_user.codice_fiscale == family.codice_fiscale_capofamiglia)


def family_member(family):
    return current_user.is_authenticated and current_user.persona and current_user.persona.nucleo_id == family.id


def consent_record(data, actor_id=None):
    supplied = data.get('consensi_registrazione', {})
    if not isinstance(supplied, dict) or any(supplied.get(key) is not True for key in REGISTRATION_CONSENTS):
        raise ValueError('Per creare l’account sono obbligatori entrambi i consensi di registrazione per la famiglia.')
    return json.dumps({'versione': 'alpha 2.0.0', 'accettati_il': datetime.utcnow().isoformat() + 'Z',
                       'ambito': 'famiglia', 'dichiarante_utente_id': actor_id,
                       'consensi': {key: dict(value, accettato=True) for key, value in REGISTRATION_CONSENTS.items()}}, ensure_ascii=False)
