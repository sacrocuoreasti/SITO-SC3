import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

import json
import hashlib
import hmac
import time
import uuid
import re
import logging
import ssl
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def email_configuration_status():
    provider = os.environ.get('EMAIL_PROVIDER') or ('google_apps_script' if os.environ.get('GOOGLE_SCRIPT_URL') else 'smtp')
    if provider == 'google_apps_script':
        url = os.environ.get('GOOGLE_SCRIPT_URL', '')
        secret = os.environ.get('GOOGLE_SCRIPT_SECRET', '')
        configured = bool(re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url) and len(secret) >= 32)
        message = 'Google Apps Script configurato' if configured else 'Impostare GOOGLE_SCRIPT_URL (URL /exec) e GOOGLE_SCRIPT_SECRET nelle variabili ambiente Render.'
    elif provider == 'smtp':
        configured = bool(os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASS'))
        message = 'SMTP configurato; le porte SMTP sono bloccate sul piano Render Free.' if configured else 'Email non configurata: impostare GOOGLE_SCRIPT_URL e GOOGLE_SCRIPT_SECRET su Render.'
    else:
        configured = False
        message = 'EMAIL_PROVIDER non valido: scegliere google_apps_script o smtp.'
    return {'provider': provider, 'configured': configured, 'message': message}


def _send_google_script(destinatario, oggetto, corpo_html, corpo_testo):
    payload = json.dumps({'to': destinatario, 'subject': oggetto, 'html': corpo_html,
                          'text': corpo_testo or ''}, ensure_ascii=False, separators=(',', ':'))
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    signature = hmac.new(os.environ['GOOGLE_SCRIPT_SECRET'].encode('utf-8'),
                         (timestamp + '.' + nonce + '.' + payload).encode('utf-8'), hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        os.environ['GOOGLE_SCRIPT_URL'],
        data=json.dumps({'payload': payload, 'timestamp': timestamp, 'nonce': nonce,
                         'signature': signature}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'CuoreInRete/1.0'},
        method='POST',
    )
    try:
        # ContentService reindirizza a googleusercontent.com: urllib segue il redirect.
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            return False, 'Risposta non valida dal servizio Google.'
        if result.get('ok') is True and result.get('id') == nonce:
            return True, 'Email accettata dal servizio Google'
        code = result.get('error', 'unknown')
        if not isinstance(code, str):
            code = 'unknown'
        logger.warning('Invio Google Apps Script non confermato: %s', code if code in {'unauthorized', 'expired', 'quota_exceeded', 'busy', 'send_failed', 'not_configured', 'invalid_message', 'already_attempted'} else 'unknown')
        messages = {
            'unauthorized': 'La chiave GOOGLE_SCRIPT_SECRET non corrisponde a MAILER_SECRET nello script.',
            'expired': 'Richiesta email scaduta. Verificare l’orologio del server.',
            'quota_exceeded': 'Quota giornaliera Google esaurita. Riprova più tardi.',
            'busy': 'Servizio email occupato. Riprova tra poco.',
            'not_configured': 'Eseguire setupMailer nello script Google e configurare MAILER_SECRET.',
        }
        return False, messages.get(code, 'Google non ha confermato l’invio del messaggio.')
    except urllib.error.HTTPError as error:
        logger.warning('Servizio Google Apps Script: HTTP %s', error.code)
        return False, 'Verificare il deployment Google: app web, esegui come proprietario, accesso a Chiunque e URL /exec.'
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        logger.warning('Google Apps Script non raggiungibile o risposta non JSON')
        return False, 'Servizio Google non raggiungibile. Verificare URL /exec e autorizzazione pubblica dell’app web.'


def invia_email(destinatario, oggetto, corpo_html, corpo_testo=None):
    """Invia via HTTPS o SMTP; successo solo dopo conferma del provider."""
    if not destinatario:
        return False, 'Destinatario non specificato'
    configuration = email_configuration_status()
    if not configuration['configured']:
        logger.warning('Invio email non configurato: provider %s', configuration['provider'])
        return False, configuration['message']
    if configuration['provider'] == 'google_apps_script':
        return _send_google_script(destinatario, oggetto, corpo_html, corpo_testo)
    try:
        smtp_user = os.environ['SMTP_USER']
        smtp_host = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        msg = MIMEMultipart('alternative')
        msg['Subject'] = oggetto
        msg['From'] = os.environ.get('EMAIL_FROM') or f'Parrocchia Sacro Cuore di Asti <{smtp_user}>'
        msg['To'] = destinatario
        if corpo_testo:
            msg.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))
        context = ssl.create_default_context()
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=8, context=context)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=8)
        with server:
            if smtp_port != 465:
                server.starttls(context=context)
            server.login(smtp_user, os.environ['SMTP_PASS'])
            refused = server.sendmail(smtp_user, destinatario, msg.as_string())
            if refused:
                return False, 'Il server email ha rifiutato il destinatario.'
        return True, 'Email accettata dal server di invio'
    except smtplib.SMTPAuthenticationError:
        logger.warning('Autenticazione SMTP rifiutata')
        return False, 'Credenziali SMTP non valide. Contattare la segreteria.'
    except (smtplib.SMTPException, OSError, ValueError):
        logger.warning('Invio SMTP non disponibile')
        return False, 'Invio SMTP non disponibile. Sul piano Render Free usare Google Apps Script via HTTPS.'


def invia_codice_recupero_password(destinatario, codice_recupero, nominativo=None):
    """Invia email con il codice OTP di recupero password."""
    nome_saluto = f"Gentile {nominativo}," if nominativo else "Gentile utente,"
    oggetto = "✟ Parrocchia Sacro Cuore Asti - Codice di Recupero Password"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; padding: 20px; }}
        .box {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .header {{ text-align: center; border-bottom: 2px solid #85141b; padding-bottom: 16px; margin-bottom: 24px; }}
        .cross {{ color: #85141b; font-size: 28px; }}
        .title {{ font-size: 19px; font-weight: 700; color: #1e293b; margin-top: 6px; }}
        .code-box {{ text-align: center; background: #f1f5f9; border-radius: 8px; padding: 18px; margin: 24px 0; border: 1px dashed #cbd5e1; }}
        .code {{ font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #85141b; font-family: monospace; }}
        .footer {{ text-align: center; font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="box">
        <div class="header">
          <div class="cross">✟</div>
          <div class="title">Parrocchia Sacro Cuore di Gesù · Asti</div>
          <div style="font-size: 13px; color: #64748b;">Portale Iscrizioni & Vita Parrocchiale</div>
        </div>
        <p>{nome_saluto}</p>
        <p>Abbiamo ricevuto una richiesta di recupero password per il tuo account associato a questo indirizzo email.</p>
        <p>Inserisci questo codice di sicurezza per reimpostare la tua password:</p>
        <div class="code-box">
          <div class="code">{codice_recupero}</div>
          <small style="color: #64748b; display: block; margin-top: 6px;">Il codice è valido per 15 minuti</small>
        </div>
        <p style="font-size: 13px; color: #475569;">Se non hai richiesto tu il ripristino della password, puoi ignorare questa email: il tuo account rimane protetto.</p>
        <div class="footer">
          Parrocchia Sacro Cuore di Asti · Via Pier Santi Mattarella 2, 14100 Asti (AT)<br>
          Questa è un'email automatica del sistema parrocchiale.
        </div>
      </div>
    </body>
    </html>
    """

    testo = f"""Parrocchia Sacro Cuore di Asti
Recupero Password

{nome_saluto}
Il tuo codice di sicurezza per reimpostare la password è: {codice_recupero}
(Valido per 15 minuti).

Se non hai richiesto il recupero, ignora questo messaggio.
"""
    return invia_email(destinatario, oggetto, html, testo)


def invia_notifica_nuova_password(destinatario, nuova_password, nominativo=None):
    """Invia email con la nuova password impostata dalla segreteria / admin."""
    nome_saluto = f"Gentile {nominativo}," if nominativo else "Gentile utente,"
    oggetto = "✟ Parrocchia Sacro Cuore Asti - Nuova Password Account"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #1e293b; padding: 20px; }}
        .box {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .header {{ text-align: center; border-bottom: 2px solid #85141b; padding-bottom: 16px; margin-bottom: 24px; }}
        .cross {{ color: #85141b; font-size: 28px; }}
        .title {{ font-size: 19px; font-weight: 700; color: #1e293b; margin-top: 6px; }}
        .pw-box {{ text-align: center; background: #fef2f2; border-radius: 8px; padding: 18px; margin: 24px 0; border: 1px dashed #f87171; }}
        .pw {{ font-size: 24px; font-weight: 800; color: #85141b; font-family: monospace; }}
        .footer {{ text-align: center; font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="box">
        <div class="header">
          <div class="cross">✟</div>
          <div class="title">Parrocchia Sacro Cuore di Gesù · Asti</div>
          <div style="font-size: 13px; color: #64748b;">Portale Iscrizioni & Vita Parrocchiale</div>
        </div>
        <p>{nome_saluto}</p>
        <p>L'amministrazione parrocchiale ha impostato una nuova password per il tuo account:</p>
        <div class="pw-box">
          <div class="pw">{nuova_password}</div>
          <small style="color: #64748b; display: block; margin-top: 6px;">Consigliamo di conservarla con cura</small>
        </div>
        <p style="font-size: 13px; color: #475569;">Puoi accedere subito al portale parrocchiale con questa credenziale.</p>
        <div class="footer">
          Parrocchia Sacro Cuore di Asti · Via Pier Santi Mattarella 2, 14100 Asti (AT)
        </div>
      </div>
    </body>
    </html>
    """
    testo = f"""Parrocchia Sacro Cuore di Asti
Nuova Password Account

{nome_saluto}
La password del tuo account è stata reimpostata su: {nuova_password}

Puoi ora accedere al portale parrocchiale.
"""
    return invia_email(destinatario, oggetto, html, testo)
