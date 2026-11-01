"""Alias senza password richiesti esplicitamente dal proprietario del sito."""
import os
from flask import current_app, request

QUICK_LOGIN_ALIASES = {
    'a': 'admin@sacrocuoreasti.com',
    'u': 'imparato.sacrocuore@gmail.com',
}


def quick_login_enabled():
    if current_app.config.get('PUBLIC_QUICK_LOGIN', False):
        return True
    return (os.environ.get('LOCAL_QUICK_LOGIN') == '1'
            and not os.environ.get('RENDER')
            and request.remote_addr in {'127.0.0.1', '::1'})
