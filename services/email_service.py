import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'noreply@sacrocuoreasti.com'
SMTP_PASS = 'llkjugsocuyqkokl'  # App password Gmail configurata

def invia_email(destinatario, oggetto, corpo_html, corpo_testo=None):
    """
    Invia un'email tramite account istituzionale Gmail SMTP.
    Ritorna True se inviata con successo, False altrimenti.
    """
    if not destinatario:
        return False, "Destinatario non specificato"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = oggetto
        msg['From'] = f"Parrocchia Sacro Cuore di Asti <{SMTP_USER}>"
        msg['To'] = destinatario

        if corpo_testo:
            part1 = MIMEText(corpo_testo, 'plain', 'utf-8')
            msg.attach(part1)

        part2 = MIMEText(corpo_html, 'html', 'utf-8')
        msg.attach(part2)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=12)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        return True, "Email inviata con successo"
    except Exception as e:
        print(f"Errore invio email a {destinatario}:", e)
        return False, str(e)


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
