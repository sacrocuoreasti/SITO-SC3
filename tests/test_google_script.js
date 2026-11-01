const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
const assert = require('assert');
const secret = 's'.repeat(64);
const properties = new Map([['MAILER_SECRET', secret]]);
let sent = [];
let quota = 10;
let failSend = false;
let locked = false;
const context = vm.createContext({
  console: { log() {} },
  PropertiesService: { getScriptProperties: () => ({
    getProperty: key => properties.get(key) || null,
    setProperty: (key, value) => properties.set(key, value),
    getProperties: () => Object.fromEntries(properties),
    deleteProperty: key => properties.delete(key),
  }) },
  MailApp: {
    getRemainingDailyQuota: () => quota,
    sendEmail: mail => { if (failSend) throw Error('offline'); sent.push(mail); },
  },
  LockService: { getScriptLock: () => ({
    tryLock() { if (locked) return false; locked = true; return true; },
    releaseLock() { locked = false; },
  }) },
  Utilities: { Charset: { UTF_8: 'utf-8' }, getUuid: () => crypto.randomUUID(),
    computeHmacSha256Signature: (value, key) => Array.from(crypto.createHmac('sha256', key).update(value).digest()).map(b => b > 127 ? b - 256 : b),
  },
  ContentService: { MimeType: { JSON: 'application/json' }, createTextOutput: text => ({ setMimeType: () => JSON.parse(text) }) },
});
vm.runInContext(fs.readFileSync('integrations/google-apps-script/Code.gs', 'utf8'), context);
function envelope(mail, timestamp = String(Math.floor(Date.now() / 1000))) {
  const payload = JSON.stringify(mail);
  const nonce = crypto.randomBytes(16).toString('hex');
  const signature = crypto.createHmac('sha256', secret).update(timestamp + '.' + nonce + '.' + payload).digest('hex');
  return { payload, nonce, timestamp, signature };
}
function send(value) { return context.doPost({ postData: { contents: JSON.stringify(value) } }); }
const mail = { to: 'person@example.test', subject: 'Recupero password', html: '<p>È una prova</p>', text: 'Prova' };
assert.equal(context.doGet().ok, true);
assert.equal(send({}).error, 'unauthorized');
const invalid = envelope(mail); invalid.signature = '0'.repeat(64);
assert.equal(send(invalid).error, 'unauthorized');
assert.equal(sent.length, 0);
assert.equal(send(envelope(mail, '1')).error, 'expired');
const request = envelope(mail);
assert.equal(send(request).id, request.nonce);
assert.equal(sent[0].htmlBody, mail.html);
assert.equal(send(request).id, request.nonce);
assert.equal(sent.length, 1);
assert.equal(locked, false);
assert.equal(send(envelope({ ...mail, to: 'one@example.test,two@example.test' })).error, 'invalid_message');
quota = 0;
assert.equal(send(envelope(mail)).error, 'quota_exceeded');
quota = 10; failSend = true;
const failed = envelope(mail);
assert.equal(send(failed).error, 'send_failed');
assert.equal(send(failed).error, 'already_attempted');
assert.equal(locked, false);
assert.equal(sent.length, 1);
console.log('Apps Script: firma, scadenza, invio HTML, replay, quota e errori verificati.');
