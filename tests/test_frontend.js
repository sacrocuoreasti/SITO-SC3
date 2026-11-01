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
