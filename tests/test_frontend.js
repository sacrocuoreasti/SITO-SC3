// Verifica il contratto del client su errori HTTP, HTML, JSON e timeout.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('static/js/app.js', 'utf8');
const start = source.indexOf('async function safeFetchJson(');
const end = source.indexOf('// ================= GESTIONE CALENDARIO', start);

async function run() {
  let pendingTimers = 0;
  let timeoutCallback;
  const context = vm.createContext({
    AbortController,
    console: { warn() {} },
    setTimeout(callback) { pendingTimers++; timeoutCallback = callback; return 1; },
    clearTimeout() { pendingTimers--; },
  });
  vm.runInContext(source.slice(start, end), context);
  const fallback = { unavailable: true };
  context.fetch = async () => ({ ok: true, headers: { get: () => 'application/json' }, json: async () => ({ title: 'ok' }) });
  assert.equal((await context.safeFetchJson('/api/example')).title, 'ok');
  context.fetch = async () => ({ ok: false, status: 503 });
  assert.strictEqual(await context.safeFetchJson('/api/example', {}, fallback), fallback);
  context.fetch = async () => ({ ok: true, headers: { get: () => 'text/html' } });
  assert.strictEqual(await context.safeFetchJson('/api/example', {}, fallback), fallback);
  context.fetch = async () => ({ ok: true, headers: { get: () => 'application/json' }, json: async () => { throw Error('invalid JSON'); } });
  assert.strictEqual(await context.safeFetchJson('/api/example', {}, fallback), fallback);
  context.fetch = async () => { throw Error('offline'); };
  assert.strictEqual(await context.safeFetchJson('/api/example', {}, fallback), fallback);
  context.fetch = (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Error('timeout')));
  });
  const request = context.safeFetchJson('/api/example', {}, fallback);
  timeoutCallback();
  assert.strictEqual(await request, fallback);
  assert.equal(pendingTimers, 0);
  console.log('Frontend: 6 scenari superati; timer ripuliti.');
}
run().catch(error => { console.error(error); process.exitCode = 1; });

const iframe = {
  attributes: {}, hidden: true,
  getAttribute(key) { return this.attributes[key] || null; },
  removeAttribute(key) { delete this.attributes[key]; },
  set src(value) { this.attributes.src = value; this.loads = (this.loads || 0) + 1; },
};
const overlay = { style: {}, innerHTML: '' };
let timers = new Map();
let timerId = 0;
const calendar = vm.createContext({
  setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
  clearTimeout(id) { timers.delete(id); },
  document: {
    getElementById(id) { return id === 'publicGoogleCalendarIframe' ? iframe : id === 'calendarLoadingOverlay' ? overlay : null; },
    querySelectorAll() { return []; },
  },
});
const calStart = source.indexOf('let currentPublicCalMode');
const calEnd = source.indexOf('// ================= INITIALIZATION', calStart);
vm.runInContext(source.slice(calStart, calEnd), calendar);
assert.equal(iframe.loads || 0, 0); // Nessuna richiesta Google all'apertura del sito.
calendar.loadPublicCalendar();
assert.equal(iframe.loads, 1);
calendar.loadPublicCalendar();
assert.equal(iframe.loads, 1); // Nessun ricaricamento duplicato.
calendar.onCalendarIframeLoaded();
assert.equal(overlay.style.display, 'none');
assert.equal(timers.size, 0);
calendar.setPublicCalendarMode('WEEK');
assert.equal(iframe.loads, 2);
Array.from(timers.values())[0]();
assert.ok(overlay.innerHTML.includes('Apri il calendario'));
calendar.retryPublicCalendar();
assert.equal(iframe.loads, 3);
console.log('Calendario: caricamento su richiesta, timeout, cambio vista e riprova verificati.');

const loginFields = {inputLoginEmail:{value:''},inputLoginPassword:{required:true}};
const loginDocument = {body:{dataset:{quickLogin:'true'}},getElementById:id=>loginFields[id]};
const loginContext = vm.createContext({document:loginDocument});
const loginStart = source.indexOf('function updateQuickLoginRequirement()');
const loginEnd = source.indexOf('async function handleLoginSubmit',loginStart);
vm.runInContext(source.slice(loginStart,loginEnd),loginContext);
for(const alias of ['a','u',' A ','U']) {
  loginFields.inputLoginEmail.value=alias;
  loginContext.updateQuickLoginRequirement();
  assert.equal(loginFields.inputLoginPassword.required,false);
}
loginFields.inputLoginEmail.value='person@example.test';
loginContext.updateQuickLoginRequirement();
assert.equal(loginFields.inputLoginPassword.required,true);
loginDocument.body.dataset.quickLogin='false';
loginFields.inputLoginEmail.value='a';
loginContext.updateQuickLoginRequirement();
assert.equal(loginFields.inputLoginPassword.required,true);
console.log('Accesso rapido: password facoltativa soltanto per gli alias abilitati.');
