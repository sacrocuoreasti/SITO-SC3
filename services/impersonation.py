"""Anteprima di un account: identità reale del destinatario, nessuna scrittura."""
from flask import session, request, abort
from flask_login import logout_user
from models import db, Utente
from services.access_control import is_admin

SESSION_KEY = 'impersonation'


def original_admin():
    state = session.get(SESSION_KEY)
    if (not isinstance(state, dict) or type(state.get('admin_id')) is not int
            or type(state.get('target_id')) is not int
            or str(session.get('_user_id')) != str(state['target_id'])):
        return None
    user = db.session.get(Utente, state['admin_id'])
    return user if user and user.is_attivo and is_admin(user) else None


def clear_identity():
    logout_user()
    session.clear()
    session['_remember'] = 'clear'


def preview_info():
    if not original_admin():
        return None
    target = db.session.get(Utente, session[SESSION_KEY]['target_id'])
    return {'attiva': True, 'sola_lettura': True,
            'utente': target.email if target else 'Account non disponibile'}


def protect_preview():
    if SESSION_KEY not in session:
        return
    if not original_admin():
        clear_identity()
        abort(401, description='Sessione amministratore non più valida. Accedi nuovamente.')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.endpoint not in (
            'auth_bp.stop_impersonation', 'auth_bp.logout'):
        abort(403, description='Impersonificazione in sola lettura: torna al profilo amministratore per effettuare modifiche.')
