/** Web app per l'invio delle email HTML del portale. Nessuna password Gmail. */
function setupMailer() {
  const properties = PropertiesService.getScriptProperties();
  if (!properties.getProperty('MAILER_SECRET')) {
    properties.setProperty('MAILER_SECRET', Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''));
  }
  // Richiede l'autorizzazione di invio. Non stampa la chiave nei log.
  console.log('Quota destinatari disponibile: ' + MailApp.getRemainingDailyQuota());
  console.log('Copia MAILER_SECRET da Impostazioni progetto > Proprietà script a Render.');
}

function doGet() {
  return jsonResponse({ok: true, service: 'CuoreInRete Mailer'});
}

function doPost(e) {
  try {
    const raw = e && e.postData && e.postData.contents;
    if (!raw || raw.length > 120000) return jsonResponse({ok: false, error: 'invalid_request'});
    const envelope = JSON.parse(raw);
    const properties = PropertiesService.getScriptProperties();
    const secret = properties.getProperty('MAILER_SECRET');
    if (!secret || secret.length < 32) return jsonResponse({ok: false, error: 'not_configured'});
    const timestamp = String(envelope.timestamp || '');
    const nonce = String(envelope.nonce || '');
    const signature = String(envelope.signature || '');
    if (!/^\d+$/.test(timestamp) || !/^[a-f0-9]{32}$/.test(nonce) || !/^[a-f0-9]{64}$/.test(signature) || typeof envelope.payload !== 'string') {
      return jsonResponse({ok: false, error: 'unauthorized'});
    }
    if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return jsonResponse({ok: false, error: 'expired'});
    const signed = timestamp + '.' + nonce + '.' + envelope.payload;
    const expected = Utilities.computeHmacSha256Signature(signed, secret, Utilities.Charset.UTF_8)
      .map(function(byte) { return ('0' + ((byte + 256) % 256).toString(16)).slice(-2); }).join('');
    let difference = 0;
    for (let i = 0; i < expected.length; i++) difference |= expected.charCodeAt(i) ^ signature.charCodeAt(i);
    if (difference !== 0) return jsonResponse({ok: false, error: 'unauthorized'});
    const mail = JSON.parse(envelope.payload);
    if (typeof mail.to !== 'string' || mail.to.length > 254 || !/^[^\s,;@]+@[^\s,;@]+\.[^\s,;@]+$/.test(mail.to)
        || typeof mail.subject !== 'string' || !mail.subject || mail.subject.length > 200 || /[\r\n]/.test(mail.subject)
        || typeof mail.html !== 'string' || !mail.html || mail.html.length > 80000
        || (mail.text !== undefined && (typeof mail.text !== 'string' || mail.text.length > 20000))) {
      return jsonResponse({ok: false, error: 'invalid_message'});
    }
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(1000)) return jsonResponse({ok: false, error: 'busy'});
    try {
      const requestKey = 'request_' + nonce;
      const previous = properties.getProperty(requestKey);
      if (previous) {
        const record = JSON.parse(previous);
        return jsonResponse(record.state === 'sent' ? {ok: true, id: nonce} : {ok: false, error: 'already_attempted'});
      }
      // Rimuove solo metadati scaduti, senza conservare email, destinatari o codici OTP.
      const now = Date.now();
      const records = properties.getProperties();
      Object.keys(records).forEach(function(key) {
        if (key.indexOf('request_') === 0) {
          try { if (JSON.parse(records[key]).expires < now) properties.deleteProperty(key); } catch (_) {}
        }
      });
      if (MailApp.getRemainingDailyQuota() < 1) return jsonResponse({ok: false, error: 'quota_exceeded'});
      // La prenotazione impedisce invii duplicati anche in caso di timeout del chiamante.
      properties.setProperty(requestKey, JSON.stringify({state: 'pending', expires: now + 600000}));
      MailApp.sendEmail({
        to: mail.to,
        subject: mail.subject,
        body: mail.text || 'Messaggio dal portale CuoreInRete. Apri questa email con un client che supporta HTML.',
        htmlBody: mail.html,
        name: properties.getProperty('MAILER_NAME') || 'Parrocchia Sacro Cuore di Asti'
      });
      properties.setProperty(requestKey, JSON.stringify({state: 'sent', expires: now + 600000}));
      return jsonResponse({ok: true, id: nonce});
    } finally {
      lock.releaseLock();
    }
  } catch (_) {
    // Non scrivere nei log destinatari, chiavi, contenuti o codici di recupero.
    return jsonResponse({ok: false, error: 'send_failed'});
  }
}

function jsonResponse(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}
