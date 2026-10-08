/**
 * Portale Parrocchiale Sacro Cuore di Gesù - Asti
 * Frontend Application Logic (app.js)
 */

let currentUser = null;
let currentView = 'dashboard';
let currentSegTab = 'iscrizioni';
let cacheAttivita = [];
let cacheMembriFamiglia = [];
let cacheIscrizioni = [];
let cacheTuttePersone = [];
let cacheListe = [];
let cacheUtenti = [];
let selectedListaId = null;
let debounceTimer = null;

// ================= INITIALIZATION =================
document.addEventListener('DOMContentLoaded', async () => {
  setupDropzone();
  await loadPublicHomepage();
  await checkAuthStatus();

  // Chiusura comoda dei modali al clic sullo sfondo o tasto ESC
  document.addEventListener('click', (e) => {
    if (e.target && e.target.classList && e.target.classList.contains('modal-overlay') && e.target.classList.contains('active')) {
      e.target.classList.remove('active');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
  });
});

// ================= PUBLIC HOMEPAGE =================
async function loadPublicHomepage() {
  try {
    const res = await fetch('/api/impostazioni/dati-pubblici');
    const data = await res.json();
    const imp = data.impostazioni || {};

    // Hero Customization
    if (imp.titolo_hero) document.getElementById('publicHeroTitle').innerHTML = escapeHtml(imp.titolo_hero).replace('Sacro Cuore', '<span>Sacro Cuore</span>');
    if (imp.sottotitolo_hero) document.getElementById('publicHeroSubtitle').textContent = imp.sottotitolo_hero;
    if (imp.testo_benvenuto) document.getElementById('publicHeroDescription').textContent = imp.testo_benvenuto;

    // Banner alert
    const bannerEl = document.getElementById('publicBannerAlert');
    if (imp.mostra_banner && imp.testo_banner) {
      bannerEl.style.display = 'flex';
      document.getElementById('publicBannerText').textContent = imp.testo_banner;
    } else {
      bannerEl.style.display = 'none';
    }

    // Toggle Sezioni
    document.getElementById('sectionMesse').style.display = imp.mostra_orari_messe ? 'block' : 'none';
    document.getElementById('sectionAttivita').style.display = imp.mostra_attivita ? 'block' : 'none';
    document.getElementById('sectionAvvisi').style.display = imp.mostra_avvisi ? 'block' : 'none';
    document.getElementById('sectionContatti').style.display = imp.mostra_contatti ? 'block' : 'none';

    // Segreteria & Recapiti Pubblici personalizzati da admin
    if (imp.segreteria_titolo && document.getElementById('homeSegreteriaTitolo')) document.getElementById('homeSegreteriaTitolo').textContent = imp.segreteria_titolo;
    if (imp.segreteria_sottotitolo && document.getElementById('homeSegreteriaSottotitolo')) document.getElementById('homeSegreteriaSottotitolo').textContent = imp.segreteria_sottotitolo;
    if (imp.segreteria_indirizzo && document.getElementById('homeSegreteriaIndirizzo')) document.getElementById('homeSegreteriaIndirizzo').textContent = imp.segreteria_indirizzo;
    if (imp.segreteria_telefono && document.getElementById('homeSegreteriaTelefono')) document.getElementById('homeSegreteriaTelefono').textContent = imp.segreteria_telefono;
    if (imp.segreteria_email && document.getElementById('homeSegreteriaEmail')) document.getElementById('homeSegreteriaEmail').textContent = imp.segreteria_email;
    if (imp.segreteria_orari && document.getElementById('homeSegreteriaOrari')) document.getElementById('homeSegreteriaOrari').textContent = imp.segreteria_orari;

    // Carica orari celebrazioni pubbliche e calendari comunitari
    await loadCelebrazioniPubbliche();
    await loadPublicCalendari();

    // Render Attività Pubblicate con anteprima locandina
    const attGrid = document.getElementById('publicAttivitaGrid');
    if (!data.attivita || !data.attivita.length) {
      attGrid.innerHTML = `
        <div style="grid-column: 1/-1; padding: 30px; text-align: center; color: var(--ink-500); background: var(--bg-subtle); border-radius: var(--radius-md);">
          Nessuna attività aperta al momento. Torna presto a trovarci!
        </div>
      `;
    } else {
      attGrid.innerHTML = data.attivita.map(a => `
        <div class="public-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
            <h3 style="font-size: 18px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(a.titolo)}</h3>
            <span class="badge badge-info">${escapeHtml(a.categoria.toUpperCase())}</span>
          </div>
          ${a.locandina_url ? `
            <div style="margin: 10px 0; border-radius: 8px; overflow: hidden; max-height: 150px; cursor: pointer; border: 1px solid var(--border-light); background: #f8fafc;" onclick="openPreviewLocandina('${a.locandina_url}', ${a.id})">
              <img src="${a.locandina_url}" alt="Locandina ${escapeHtml(a.titolo)}" style="width: 100%; height: 150px; object-fit: cover; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'" onerror="this.parentElement.style.display='none'">
              <div style="font-size: 11px; padding: 3px 6px; background: rgba(0,0,0,0.65); color: #fff; text-align: center; margin-top: -24px; position: relative;">🔍 Ingrandisci Locandina</div>
            </div>
          ` : ''}
          <p style="font-size: 13px; color: var(--ink-700); line-height: 1.6; margin-bottom: 14px;">${escapeHtml(a.descrizione || '')}</p>
          <div style="font-size: 12.5px; color: var(--ink-500); display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px;">
            <div>👶 Fascia di Età: <strong style="color:var(--ink-800);">${a.eta_min} - ${a.eta_max} anni</strong></div>
            <div>📅 Periodo: ${a.data_inizio_it || 'In corso'} ${a.data_fine_it ? `al ${a.data_fine_it}` : ''}</div>
            <div>💶 Quota: <strong style="color:var(--primary); font-size:15px;">€ ${a.quota_iscrizione.toFixed(2)}</strong></div>
          </div>
          <button class="btn btn-primary btn-sm" style="width: 100%;" onclick="showAuthModal('register')">
            Iscriviti Online →
          </button>
        </div>
      `).join('');
    }

    // Render Avvisi Pubblicati
    const avvisiGrid = document.getElementById('publicAvvisiGrid');
    if (!data.avvisi || !data.avvisi.length) {
      avvisiGrid.innerHTML = `
        <div style="grid-column: 1/-1; padding: 20px; text-align: center; color: var(--ink-500);">
          Nessun avviso straordinario in bacheca.
        </div>
      `;
    } else {
      avvisiGrid.innerHTML = data.avvisi.map(av => `
        <div class="public-card">
          <span class="badge badge-success" style="margin-bottom: 8px;">${av.categoria.toUpperCase()}</span>
          <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">${escapeHtml(av.titolo)}</h3>
          <p style="font-size: 13px; color: var(--ink-700); line-height: 1.6;">${escapeHtml(av.contenuto)}</p>
          ${av.data_evento ? `<small style="color:var(--ink-500); display:block; margin-top:10px;">📅 Data: ${av.data_evento}</small>` : ''}
        </div>
      `).join('');
    }
  } catch (err) {
    console.error('Errore caricamento homepage pubblica:', err);
  }
}

function goToPublicHome() {
  document.getElementById('publicHomepage').style.display = 'flex';
  document.getElementById('loginScreenView').style.display = 'none';
  document.getElementById('appShell').style.display = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showAuthModal(tab = 'login') {
  document.getElementById('publicHomepage').style.display = 'none';
  document.getElementById('appShell').style.display = 'none';
  document.getElementById('loginScreenView').style.display = 'grid';
  showAuthTab(tab);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ================= AUTHENTICATION & SESSIONS =================
async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.authenticated && data.user) {
      currentUser = data.user;
      renderAppShell();
      navigateTo('dashboard');
    }
  } catch (err) {
    console.error('Errore verifica sessione:', err);
  }
}

function renderAppShell() {
  document.getElementById('publicHomepage').style.display = 'none';
  document.getElementById('loginScreenView').style.display = 'none';
  document.getElementById('appShell').style.display = 'flex';

  if (currentUser) {
    const nome = currentUser.nominativo || currentUser.email.split('@')[0];
    document.getElementById('topUserName').textContent = nome;
    document.getElementById('topUserRole').textContent = currentUser.ruolo.toUpperCase();
    
    const topAvatar = document.getElementById('topAvatar');
    const fotoUrl = (currentUser.persona && currentUser.persona.foto_profilo_url) ? currentUser.persona.foto_profilo_url : null;
    if (fotoUrl && fotoUrl.trim() !== '') {
      topAvatar.innerHTML = `<img src="${fotoUrl}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
    } else {
      const initials = nome.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'SC';
      topAvatar.textContent = initials;
    }

    const badge = document.querySelector('.user-profile-badge');
    if (badge && currentUser.persona && currentUser.persona.codice_fiscale) {
      badge.style.cursor = 'pointer';
      badge.title = 'Clicca per visualizzare o aggiornare la tua foto profilo';
      badge.onclick = () => openModalFotoProfilo(currentUser.persona.codice_fiscale, currentUser.persona.nominativo, currentUser.persona.foto_profilo_url || '');
    }

    applyRolePermissions();
  }
}

function applyRolePermissions() {
  const roles = currentUser.tutti_i_ruoli || [currentUser.ruolo];
  const isAdminOrParroco = roles.includes('admin') || roles.includes('parroco');
  const isSegreteria = isAdminOrParroco || roles.includes('segreteria');
  const isCatechista = isSegreteria || roles.includes('catechista');
  const isOratorio = isSegreteria || roles.includes('oratorio');
  const isStaff = isSegreteria;

  const oratorioNav = document.querySelector('.oratorio-nav');
  const catechismoNav = document.querySelector('.catechismo-nav');
  const doposcuolaNav = document.querySelector('.doposcuola-nav');
  const segreteriaNav = document.querySelector('.segreteria-nav');
  const adminNav = document.querySelector('.admin-nav');
  const famigliaNav = document.getElementById('navItemFamiglia');
  const anagraficaNav = document.getElementById('navItemAnagrafica');
  const excelNav = document.getElementById('navItemExcel');
  const gestioneLabel = document.getElementById('sectionLabelGestione');

  const isGestionePura = currentUser.is_gestione_pura || ['segreteria', 'oratorio'].includes(currentUser.ruolo);
  const puoIscrivereFigli = !isGestionePura;

  if (oratorioNav) {
    oratorioNav.style.display = (isOratorio || puoIscrivereFigli) ? 'flex' : 'none';
    oratorioNav.innerHTML = !isOratorio && puoIscrivereFigli ? '<i>🏓</i> Oratorio Figli' : '<i>🏓</i> Oratorio & Allergie';
  }
  if (catechismoNav) {
    catechismoNav.style.display = (isCatechista || puoIscrivereFigli) ? 'flex' : 'none';
    catechismoNav.innerHTML = !isCatechista && puoIscrivereFigli ? '<i>🕮</i> Catechismo Figli' : '<i>🕮</i> Gruppi Catechismo';
  }
  if (doposcuolaNav) {
    doposcuolaNav.style.display = (isStaff || isOratorio || isCatechista || puoIscrivereFigli) ? 'flex' : 'none';
    doposcuolaNav.innerHTML = (!isStaff && !isOratorio && !isCatechista && puoIscrivereFigli) ? '<i>📚</i> Doposcuola Figli' : '<i>📚</i> Doposcuola & Studio';
  }
  if (segreteriaNav) segreteriaNav.style.display = isSegreteria ? 'flex' : 'none';
  if (adminNav) adminNav.style.display = isAdminOrParroco ? 'flex' : 'none';

  // L'utente non deve vedere Anagrafica Parrocchiale né Import/Export Excel
  if (anagraficaNav) anagraficaNav.style.display = isStaff ? 'flex' : 'none';
  if (excelNav) excelNav.style.display = isStaff ? 'flex' : 'none';
  if (gestioneLabel) gestioneLabel.style.display = (isStaff || isAdminOrParroco) ? 'block' : 'none';

  // Gestione Card Cassa Quote (per Staff) vs Card Offerte & Donazioni (per Utente/Famiglia)
  const kpiCassa = document.getElementById('kpiCardCassaQuote');
  const kpiOfferte = document.getElementById('kpiCardOfferteUtente');
  if (kpiCassa) kpiCassa.style.display = isStaff ? 'flex' : 'none';
  if (kpiOfferte) {
    kpiOfferte.style.display = !isStaff ? 'flex' : 'none';
    if (!isStaff) caricaTotaleOfferteCard();
  }

  // Nascondi pulsante "Cerca Anagrafica" nella dashboard per utenti normali
  const btnDashAnagrafica = document.querySelector('#viewDashboard .header-actions button[onclick*="anagrafica"]');
  if (btnDashAnagrafica) btnDashAnagrafica.style.display = isStaff ? 'inline-flex' : 'none';

  // In attività ed iscrizioni togli il pulsante "crea nuova attività" e filtri bozze per utenti non staff
  const btnCreaAtt = document.getElementById('btnCreaNuovaAttivita') || document.querySelector('#viewAttivita button[onclick*="openModalNuovaAttivita"]');
  if (btnCreaAtt) {
    btnCreaAtt.style.display = isStaff ? 'inline-flex' : 'none';
  }
  const filterStatusCont = document.getElementById('filterStatusContainer');
  if (filterStatusCont) {
    filterStatusCont.style.display = isStaff ? 'flex' : 'none';
  }

  // Requirement: "account segreteria, e oratorio non hanno la sezione 'mia famiglia'"
  if (famigliaNav) {
    famigliaNav.style.display = isGestionePura ? 'none' : 'flex';
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('inputLoginEmail').value;
  const password = document.getElementById('inputLoginPassword').value;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore di autenticazione');

    currentUser = data.user;
    showToast(data.message, 'success');
    renderAppShell();
    if (currentUser.is_gestione_pura || ['segreteria', 'oratorio'].includes(currentUser.ruolo)) {
      navigateTo('dashboard');
    } else {
      navigateTo('dashboard');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

let cacheCampiAccount = [];

async function renderCustomRegistrationFields() {
  const container = document.getElementById('regCampiPersonalizzatiContainer');
  if (!container) return;
  try {
    const res = await fetch('/api/configurazioni/campi-account');
    const data = await res.json();
    cacheCampiAccount = (data.campi || []).filter(c => c.is_attivo !== false);
    if (!cacheCampiAccount.length) {
      container.innerHTML = '';
      return;
    }
    container.innerHTML = `
      <div style="border-top: 1px dashed var(--border-light); margin-top: 14px; padding-top: 12px; margin-bottom: 6px;">
        <span style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--ink-500); display: block; margin-bottom: 10px;">
          Campi Addizionali Richiesti dalla Parrocchia:
        </span>
        ${cacheCampiAccount.map(c => {
          let inputHtml = '';
          const reqAttr = c.obbligatorio ? 'required' : '';
          const label = `${escapeHtml(c.nome)}${c.obbligatorio ? ' *' : ''}`;

          if (c.tipo === 'checkbox') {
            inputHtml = `
              <label style="display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer;">
                <input type="checkbox" id="custom_reg_${c.chiave}" data-key="${c.chiave}">
                ${label}
              </label>
            `;
          } else if (c.tipo === 'select') {
            const opts = (c.opzioni || '').split(',').map(o => o.trim()).filter(Boolean);
            inputHtml = `
              <label>${label}</label>
              <select id="custom_reg_${c.chiave}" data-key="${c.chiave}" class="form-control" ${reqAttr}>
                <option value="">-- Seleziona --</option>
                ${opts.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('')}
              </select>
            `;
          } else if (c.tipo === 'numero') {
            inputHtml = `
              <label>${label}</label>
              <input type="number" id="custom_reg_${c.chiave}" data-key="${c.chiave}" class="form-control" ${reqAttr}>
            `;
          } else if (c.tipo === 'data') {
            inputHtml = `
              <label>${label}</label>
              <input type="date" id="custom_reg_${c.chiave}" data-key="${c.chiave}" class="form-control" ${reqAttr}>
            `;
          } else {
            inputHtml = `
              <label>${label}</label>
              <input type="text" id="custom_reg_${c.chiave}" data-key="${c.chiave}" class="form-control" placeholder="${label}" ${reqAttr}>
            `;
          }
          return `<div class="form-group custom-field-group">${inputHtml}</div>`;
        }).join('')}
      </div>
    `;
  } catch (err) {
    console.error('Errore campi account custom:', err);
  }
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  const nome = document.getElementById('regNome').value;
  const cognome = document.getElementById('regCognome').value;
  const cf = document.getElementById('regCF').value.toUpperCase().trim();
  const telefono = document.getElementById('regTelefono').value;
  const nomeFamiglia = document.getElementById('regNomeFamiglia').value;
  const email = document.getElementById('regEmail').value;
  const password = document.getElementById('regPassword').value;

  const extraFields = {};
  for (const c of cacheCampiAccount) {
    const el = document.getElementById(`custom_reg_${c.chiave}`);
    if (el) {
      if (c.tipo === 'checkbox') {
        extraFields[c.chiave] = el.checked;
      } else {
        extraFields[c.chiave] = el.value.trim();
      }
    }
  }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome, cognome, codice_fiscale: cf, telefono, nome_famiglia: nomeFamiglia, email, password,
        campi_extra: extraFields
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore registrazione');

    currentUser = data.user;
    showToast(data.message, 'success');
    renderAppShell();
    navigateTo('famiglia');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleLogout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  currentUser = null;
  showToast('Disconnesso con successo', 'info');
  goToPublicHome();
}

function showAuthTab(tab) {
  const formLogin = document.getElementById('formLogin');
  const formReg = document.getElementById('formRegister');
  const btnLogin = document.getElementById('tabBtnLogin');
  const btnReg = document.getElementById('tabBtnRegister');

  if (tab === 'login') {
    formLogin.style.display = 'block';
    formReg.style.display = 'none';
    btnLogin.className = 'btn btn-sm btn-primary';
    btnReg.className = 'btn btn-sm btn-secondary';
  } else {
    formLogin.style.display = 'none';
    formReg.style.display = 'block';
    btnLogin.className = 'btn btn-sm btn-secondary';
    btnReg.className = 'btn btn-sm btn-primary';
    renderCustomRegistrationFields();
  }
}

// ================= CODICE FISCALE VALIDATION =================
async function validateCFField(input) {
  const cf = input.value.toUpperCase().trim();
  const feedbackEl = document.getElementById('regCFFeedback');
  if (cf.length < 16) {
    feedbackEl.textContent = `${cf.length}/16 caratteri`;
    feedbackEl.className = 'cf-feedback';
    return;
  }

  const res = await fetch('/api/persone/validate-cf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codice_fiscale: cf })
  });
  const data = await res.json();

  if (data.valido) {
    feedbackEl.textContent = `✓ Codice Fiscale valido (${data.estratto.sesso || ''}, nato/a il ${data.estratto.data_nascita || ''})`;
    feedbackEl.className = 'cf-feedback valid';
  } else {
    feedbackEl.textContent = `✗ Codice Fiscale non conforme all'algoritmo ufficiale`;
    feedbackEl.className = 'cf-feedback invalid';
  }
}

async function validateCFFieldMembro(input) {
  const cf = input.value.toUpperCase().trim();
  const feedbackEl = document.getElementById('membroCFFeedback');
  if (cf.length < 16) {
    feedbackEl.textContent = `${cf.length}/16 caratteri`;
    feedbackEl.className = 'cf-feedback';
    return;
  }

  const res = await fetch('/api/persone/validate-cf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codice_fiscale: cf })
  });
  const data = await res.json();

  if (data.valido) {
    feedbackEl.textContent = `✓ Codice Fiscale valido`;
    feedbackEl.className = 'cf-feedback valid';
    if (data.estratto.sesso) document.getElementById('membroSesso').value = data.estratto.sesso;
    if (data.estratto.data_nascita) document.getElementById('membroDataNascita').value = data.estratto.data_nascita;
  } else {
    feedbackEl.textContent = `✗ Codice Fiscale non valido`;
    feedbackEl.className = 'cf-feedback invalid';
  }
}

async function validateCFFieldPersona(input) {
  const cf = input.value.toUpperCase().trim();
  const feedbackEl = document.getElementById('personaCFFeedback');
  if (cf.length < 16) {
    feedbackEl.textContent = `${cf.length}/16 caratteri`;
    feedbackEl.className = 'cf-feedback';
    return;
  }

  const res = await fetch('/api/persone/validate-cf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ codice_fiscale: cf })
  });
  const data = await res.json();

  if (data.valido) {
    feedbackEl.textContent = `✓ CF Valido`;
    feedbackEl.className = 'cf-feedback valid';
    if (data.estratto.sesso) document.getElementById('personaSesso').value = data.estratto.sesso;
    if (data.estratto.data_nascita) document.getElementById('personaDataNascita').value = data.estratto.data_nascita;
  } else {
    feedbackEl.textContent = `✗ CF non valido`;
    feedbackEl.className = 'cf-feedback invalid';
  }
}

// ================= VIEW NAVIGATION =================
function navigateTo(viewName) {
  const roles = currentUser ? (currentUser.tutti_i_ruoli || [currentUser.ruolo]) : [];
  const isStaff = roles.some(r => ['admin', 'segreteria', 'parroco'].includes(r));

  if (viewName === 'famiglia' && currentUser && (currentUser.is_gestione_pura || ['segreteria', 'oratorio'].includes(currentUser.ruolo))) {
    viewName = 'dashboard';
  }
  if (!isStaff && ['anagrafica', 'excel', 'segreteria', 'utenti'].includes(viewName)) {
    viewName = 'dashboard';
  }
  currentView = viewName;

  document.querySelectorAll('.view-panel').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.nav-item').forEach(el => {
    if (el.getAttribute('data-view') === viewName) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  const breadcrumb = document.getElementById('breadcrumbCurrent');
  breadcrumb.textContent = viewName.toUpperCase();

  const viewMap = {
    'dashboard': { id: 'viewDashboard', fn: loadDashboard },
    'famiglia': { id: 'viewFamiglia', fn: loadFamiglia },
    'attivita': { id: 'viewAttivita', fn: loadAttivita },
    'oratorio': { id: 'viewOratorio', fn: loadOratorio },
    'catechismo': { id: 'viewCatechismo', fn: loadCatechismo },
    'doposcuola': { id: 'viewDoposcuola', fn: loadDoposcuola },
    'segreteria': { id: 'viewSegreteria', fn: loadSegreteria },
    'anagrafica': { id: 'viewAnagrafica', fn: () => loadAnagrafica() },
    'excel': { id: 'viewExcel', fn: () => {} },
    'utenti': { id: 'viewUtenti', fn: loadUtenti }
  };

  const current = viewMap[viewName];
  if (current) {
    const el = document.getElementById(current.id);
    if (el) el.style.display = 'block';
    if (current.fn) current.fn();
  }

  document.getElementById('sidebar').classList.remove('open');
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ================= VIEW 1: DASHBOARD =================
async function loadDashboard() {
  try {
    const roles = currentUser ? (currentUser.tutti_i_ruoli || [currentUser.ruolo]) : [];
    const isStaff = roles.some(r => ['admin', 'segreteria', 'parroco'].includes(r));

    if (isStaff) {
      const [statsRes, attRes] = await Promise.all([
        fetch('/api/segreteria/stats'),
        fetch('/api/attivita?include_bozze=true')
      ]);
      const stats = await statsRes.json();
      const attData = await attRes.json();
      cacheAttivita = attData.attivita || [];

      // Mostra etichette parrocchiali
      const kpiCard1 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(1)');
      if (kpiCard1) {
        kpiCard1.querySelector('span').textContent = 'Anagrafica Totale';
        kpiCard1.querySelector('small').textContent = 'Parrocchiani censiti con CF';
      }
      const kpiCard2 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(2)');
      if (kpiCard2) {
        kpiCard2.querySelector('span').textContent = 'Nuclei Familiari';
        kpiCard2.querySelector('small').textContent = 'Famiglie a portale';
      }
      const kpiCard3 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(3)');
      if (kpiCard3) {
        kpiCard3.querySelector('span').textContent = 'Iscrizioni Totali';
        kpiCard3.querySelector('small').textContent = 'Ragazzi alle attività';
      }

      document.getElementById('kpiTotPersone').textContent = stats.totale_persone || '0';
      document.getElementById('kpiTotFamiglie').textContent = stats.totale_famiglie || '0';
      document.getElementById('kpiIscrizioniConfermate').textContent = stats.iscrizioni_confermate || '0';

      if (stats.contabilita) {
        document.getElementById('kpiQuoteIncassate').textContent = `€ ${stats.contabilita.totale_incassato.toFixed(2)}`;
        document.getElementById('kpiQuoteResiduo').textContent = `Da incassare: € ${stats.contabilita.saldo_residuo.toFixed(2)}`;
      }

      if (document.getElementById('kpiCardCassaQuote')) document.getElementById('kpiCardCassaQuote').style.display = 'flex';
      if (document.getElementById('kpiCardOfferteUtente')) document.getElementById('kpiCardOfferteUtente').style.display = 'none';
    } else {
      // Profilo Utente: non vede anagrafica totale parrocchiale ma solo i dati della sua famiglia
      const [famRes, iscRes, attRes] = await Promise.all([
        fetch('/api/famiglie/mia'),
        fetch('/api/iscrizioni?solo_mie=true'),
        fetch('/api/attivita')
      ]);
      const famData = await famRes.json();
      const iscData = await iscRes.json();
      const attData = await attRes.json();

      cacheAttivita = attData.attivita || [];
      const membriCount = famData.nucleo ? (famData.nucleo.componenti || []).length : 1;
      const mieIscrizioni = iscData.iscrizioni || [];

      // Aggiorna KPI personalizzati per la famiglia (senza mostrare quote/cassa)
      const kpiCard1 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(1)');
      if (kpiCard1) {
        kpiCard1.querySelector('span').textContent = 'La Mia Famiglia';
        kpiCard1.querySelector('strong').textContent = `${membriCount}`;
        kpiCard1.querySelector('small').textContent = 'Componenti registrati';
      }
      const kpiCard2 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(2)');
      if (kpiCard2) {
        kpiCard2.querySelector('span').textContent = 'Stato Iscrizioni';
        kpiCard2.querySelector('strong').textContent = `${mieIscrizioni.length}`;
        kpiCard2.querySelector('small').textContent = 'Attività attive nel nucleo';
      }
      const kpiCard3 = document.querySelector('#dashKpiGrid .kpi-card:nth-child(3)');
      if (kpiCard3) {
        kpiCard3.querySelector('span').textContent = 'Comunità Parrocchiale';
        kpiCard3.querySelector('strong').textContent = 'Sacro Cuore';
        kpiCard3.querySelector('small').textContent = 'Anno Pastorale 2025/2026';
      }

      if (document.getElementById('kpiCardCassaQuote')) document.getElementById('kpiCardCassaQuote').style.display = 'none';
      if (document.getElementById('kpiCardOfferteUtente')) document.getElementById('kpiCardOfferteUtente').style.display = 'flex';
    }

    const container = document.getElementById('dashAttivitaList');
    let dashAttivita = cacheAttivita || [];

    // Per utenti normali: mostra solo attività registrabili per la propria famiglia
    if (!isStaff) {
      const familyMembers = (cacheMembriFamiglia && cacheMembriFamiglia.length) ? cacheMembriFamiglia : (currentUser.persona ? [currentUser.persona] : []);
      dashAttivita = dashAttivita.filter(a => {
        if (!a.is_pubblicato) return false;
        if (a.posti_disponibili !== null && a.posti_disponibili <= 0) return false;
        if (familyMembers.length > 0) {
          return familyMembers.some(m => m.eta !== null && m.eta >= a.eta_min && m.eta <= a.eta_max);
        }
        return true;
      });
    }

    if (!dashAttivita.length) {
      container.innerHTML = `<div style="padding: 16px; color: var(--ink-500); text-align: center;">
        ${!isStaff ? 'Nessuna attività attualmente aperta per la fascia d\'età del tuo nucleo familiare.' : 'Nessuna attività registrata. Crea una nuova attività!'}
      </div>`;
      return;
    }

    container.innerHTML = dashAttivita.slice(0, 4).map(a => `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--border-light);">
        <div>
          <strong style="font-size: 14px; color: var(--ink-900); display: block;">${escapeHtml(a.titolo)}</strong>
          <span style="font-size: 12px; color: var(--ink-500);">
            ${escapeHtml(a.categoria.toUpperCase())} · Età: <strong>${a.eta_min}-${a.eta_max} anni</strong> · Quota: <strong>€ ${a.quota_iscrizione.toFixed(2)}</strong>
          </span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
          ${isStaff ? `
            <span class="badge ${a.is_pubblicato ? 'badge-published' : 'badge-draft'}">
              ${a.is_pubblicato ? 'Pubblicata' : 'Bozza'}
            </span>
          ` : ''}
          <button class="btn btn-sm btn-primary" onclick="openModalNuovaIscrizione(${a.id})">Iscriviti</button>
        </div>
      </div>
    `).join('');

    // Carica orari messe e avvisi parrocchiali aggiornati con le impostazioni
    try {
      const [evRes, celRes] = await Promise.all([
        fetch('/api/impostazioni/dati-pubblici'),
        fetch('/api/celebrazioni?sezione=messe')
      ]);
      const evData = await evRes.json();
      const celData = await celRes.json();
      const imp = evData.impostazioni || {};

      // Gestione dinamica blocco Orari Messe
      const messeBlock = document.getElementById('dashOrariMesseBlock');
      const messeCont = document.getElementById('dashOrariMesseContainer');
      if (messeBlock && messeCont) {
        if (imp.mostra_orari_messe === false) {
          messeBlock.style.display = 'none';
        } else {
          messeBlock.style.display = 'block';
          const messeList = (celData.messe || []).filter(c => c.is_attivo !== false);
          if (messeList.length > 0) {
            messeCont.innerHTML = `
              <ul style="padding-left: 18px; font-size: 13px; color: var(--ink-800); line-height: 1.6; margin: 0;">
                ${messeList.map(m => `
                  <li><strong>${escapeHtml(m.giorno || m.titolo)}:</strong> ore ${escapeHtml(m.orario)} ${m.luogo ? `<span style="color:var(--ink-500);">(${escapeHtml(m.luogo)})</span>` : ''}</li>
                `).join('')}
              </ul>
            `;
          } else {
            messeCont.innerHTML = '<p style="font-size: 13px; color: var(--ink-600); margin: 0;">Nessun orario messe configurato nelle celebrazioni parrocchiali.</p>';
          }
        }
      }

      // Gestione dinamica Avvisi
      const avvisiCont = document.getElementById('dashAvvisiContainer');
      if (avvisiCont) {
        if (imp.mostra_avvisi === false) {
          avvisiCont.innerHTML = '<p style="font-size: 13px; color: var(--ink-500);">La bacheca avvisi è momentaneamente disattivata.</p>';
        } else if (evData.avvisi && evData.avvisi.length) {
          avvisiCont.innerHTML = evData.avvisi.map(ev => `
            <div style="border-left: 3px solid var(--primary); padding-left: 10px; margin-bottom: 12px;">
              <span class="badge badge-success" style="font-size:10px; margin-bottom:4px;">${escapeHtml(ev.categoria.toUpperCase())}</span>
              <strong style="display:block; font-size:13.5px; color:var(--ink-900);">${escapeHtml(ev.titolo)}</strong>
              <p style="font-size:12.5px; color:var(--ink-700); margin:4px 0;">${escapeHtml(ev.contenuto)}</p>
              ${ev.data_evento ? `<small style="color:var(--ink-500);">📅 ${ev.data_evento}</small>` : ''}
            </div>
          `).join('');
        } else {
          avvisiCont.innerHTML = '<p style="font-size: 13px; color: var(--ink-500);">Nessun avviso straordinario al momento.</p>';
        }
      }
    // Carica calendari parrocchiali per la dashboard personale
    await loadUserCalendari();
  } catch (err) {
    console.error('Errore caricamento dashboard:', err);
  }
}

// ================= VIEW 2: LA MIA FAMIGLIA =================
async function loadFamiglia() {
  try {
    const res = await fetch('/api/famiglie/mia');
    const data = await res.json();

    const summaryEl = document.getElementById('famigliaInfoSummary');
    const membersGrid = document.getElementById('familyMembersGrid');

    if (!data.nucleo) {
      summaryEl.innerHTML = `
        <div style="padding: 16px; color: var(--ink-500);">
          Nessun nucleo familiare registrato. Clicca "+ Aggiungi Figlio / Membro" per iniziare a comporre la tua famiglia.
        </div>
      `;
      membersGrid.innerHTML = '';
      return;
    }

    const n = data.nucleo;
    document.getElementById('badgeFamigliaNome').textContent = n.nome_famiglia;

    summaryEl.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; font-size: 13px;">
        <div><strong>Capofamiglia:</strong> <br>${escapeHtml(n.capofamiglia_nome)} (${escapeHtml(n.codice_fiscale_capofamiglia || 'N/D')})</div>
        <div><strong>Recapito Telefonico:</strong> <br>${escapeHtml(n.telefono_principale || n.capofamiglia_telefono || 'Non indicato')}</div>
        <div><strong>Indirizzo:</strong> <br>${escapeHtml(n.indirizzo || 'Asti')}, ${escapeHtml(n.citta || 'Asti')}</div>
        <div><strong>Totale Componenti:</strong> <br><span class="badge badge-success">${n.numero_componenti} membri</span></div>
      </div>
    `;

    cacheMembriFamiglia = n.componenti || [];

    if (!cacheMembriFamiglia.length) {
      membersGrid.innerHTML = `<div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--ink-500);">Nessun componente aggiunto. Clicca "+ Aggiungi Figlio / Membro".</div>`;
    } else {
      membersGrid.innerHTML = cacheMembriFamiglia.map(m => {
        const isCapo = m.codice_fiscale === n.codice_fiscale_capofamiglia;
        const fotoUrl = m.foto_profilo_url;
        return `
          <div class="family-member-card">
            <div class="member-top" style="cursor: pointer;" onclick="apriSchedaVisualizzazionePersona('${m.codice_fiscale}')" title="Clicca per visualizzare la scheda anagrafica completa">
              <div style="display: flex; gap: 12px; align-items: center;">
                <div class="member-avatar" style="overflow: hidden; padding: 0;">
                  ${fotoUrl ? `<img src="${fotoUrl}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover;">` : escapeHtml(m.nome[0] || 'F')}
                </div>
                <div class="member-title">
                  <h4 style="color: var(--primary);">${escapeHtml(m.nominativo)}</h4>
                  <span class="member-cf">${escapeHtml(m.codice_fiscale)}</span>
                </div>
              </div>
              <span class="badge ${isCapo ? 'badge-info' : 'badge-neutral'}">${escapeHtml(m.ruolo_famiglia || 'Figlio/a')}</span>
            </div>

            <div class="member-details">
              <div>📅 Data di Nascita: <strong>${m.data_nascita_it || 'Non indicata'} (${m.eta !== null ? `${m.eta} anni` : ''})</strong></div>
              <div>⚧ Sesso: <strong>${m.sesso === 'M' ? 'Maschio' : 'Femmina'}</strong></div>
              ${m.telefono ? `<div>📞 Telefono: <strong>${escapeHtml(m.telefono)}</strong></div>` : ''}
            </div>

            ${(m.allergie || m.intolleranze_alimentari) ? `
              <div class="member-health-alert">
                <strong>⚠️ Scheda Sanitaria:</strong>
                ${m.intolleranze_alimentari ? `<span>Intolleranze: ${escapeHtml(m.intolleranze_alimentari)}</span>` : ''}
                ${m.allergie ? `<span>Allergie: ${escapeHtml(m.allergie)}</span>` : ''}
              </div>
            ` : `
              <div style="font-size: 11px; color: #15803d; background: #f0fdf4; padding: 6px 10px; border-radius: var(--radius-sm);">
                ✓ Nessuna allergia segnalata
              </div>
            `}

            ${m.certificato_battesimo_url ? `
              <div style="margin-top: 8px;">
                <a href="${m.certificato_battesimo_url}" target="_blank" class="certificato-badge presente">
                  🕊 Certificato Battesimo
                </a>
              </div>
            ` : ''}

            <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid var(--border-light); display: flex; gap: 8px;">
              <button class="btn btn-sm btn-primary" style="flex: 1; display: flex; justify-content: center; align-items: center; gap: 6px;" onclick="openModalModificaPersona('${m.codice_fiscale}')">
                ✏️ Modifica
              </button>
              <button class="btn btn-sm btn-secondary" style="display: flex; justify-content: center; align-items: center; gap: 4px;" onclick="openModalFotoProfilo('${m.codice_fiscale}', '${escapeHtml(m.nominativo)}', '${m.foto_profilo_url || ''}')" title="Carica o modifica foto profilo">
                📸 Foto
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    await loadFamilyIscrizioni();
  } catch (err) {
    console.error('Errore caricamento famiglia:', err);
  }
}

async function loadFamilyIscrizioni() {
  try {
    const isStaff = currentUser && (currentUser.tutti_i_ruoli || []).some(r => ['admin', 'segreteria', 'parroco'].includes(r));
    const res = await fetch('/api/iscrizioni?solo_mie=true');
    const data = await res.json();
    const tbody = document.querySelector('#tableFamilyIscrizioni tbody');
    
    if (!data.iscrizioni.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--ink-500); padding:20px;">Nessuna iscrizione attiva al momento.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.iscrizioni.map(i => `
      <tr>
        <td><strong>${escapeHtml(i.partecipante_nome)}</strong><br><small style="color:var(--ink-500); font-family:monospace;">${escapeHtml(i.codice_fiscale_partecipante)}</small></td>
        <td><strong>${escapeHtml(i.attivita_titolo)}</strong><br><span style="font-size:11px; color:var(--ink-500);">${escapeHtml(i.attivita_categoria.toUpperCase())}</span></td>
        <td><span class="badge badge-success">${escapeHtml(i.stato)}</span></td>
        <td><strong>€ ${i.importo_dovuto.toFixed(2)}</strong></td>
        <td>
          <span class="badge ${i.stato_pagamento === 'saldato' ? 'badge-success' : (i.stato_pagamento === 'acconto' ? 'badge-warning' : 'badge-danger')}">
            ${escapeHtml(i.stato_pagamento.toUpperCase())} (€ ${i.importo_pagato.toFixed(2)})
          </span>
        </td>
        <td>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            ${isStaff ? `
              <button class="btn btn-sm btn-secondary" onclick="apriRicevutaIscrizione(${i.id})">
                <i>📄</i> Ricevuta
              </button>
            ` : ''}
            <button class="btn btn-sm btn-danger" onclick="annullaMiaIscrizione(${i.id})">
              ❌ Disiscriviti
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Errore caricamento iscrizioni famiglia:', err);
  }
}

// ================= VIEW 3: ATTIVITÀ & BOZZE/PUBBLICAZIONE =================
async function loadAttivita() {
  try {
    const isStaff = currentUser && (currentUser.tutti_i_ruoli || []).some(r => ['admin', 'segreteria', 'parroco'].includes(r));
    const url = isStaff ? '/api/attivita?include_bozze=true' : '/api/attivita';
    const res = await fetch(url);
    const data = await res.json();
    cacheAttivita = data.attivita || [];
    renderAttivitaCatalog(cacheAttivita);
  } catch (err) {
    console.error('Errore catalogo attività:', err);
  }
}

function renderAttivitaCatalog(items) {
  const container = document.getElementById('activitiesCatalogGrid');
  const isStaff = currentUser && (currentUser.tutti_i_ruoli || []).some(r => ['admin', 'segreteria', 'parroco'].includes(r));

  // Requirement: "non mostrare eventi dove non si possono registrare" (lato utente normale)
  if (!isStaff) {
    const familyMembers = (cacheMembriFamiglia && cacheMembriFamiglia.length) ? cacheMembriFamiglia : (currentUser.persona ? [currentUser.persona] : []);
    items = items.filter(a => {
      // 1. Esclude eventi con posti esauriti
      if (a.posti_disponibili !== null && a.posti_disponibili <= 0) return false;
      // 2. Se ci sono persone nel nucleo, controlla se almeno uno rientra nell'età
      if (familyMembers.length > 0) {
        const canRegister = familyMembers.some(m => m.eta !== null && m.eta >= a.eta_min && m.eta <= a.eta_max);
        return canRegister;
      }
      return true;
    });
  }

  if (!items.length) {
    container.innerHTML = `<div style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--ink-500); background:#fff; border-radius:var(--radius-md); border:1px solid var(--border-light);">
      ${!isStaff ? 'Nessuna attività attualmente aperta per la fascia d\'età del tuo nucleo familiare.' : 'Nessuna attività registrata. Clicca "+ Crea Nuova Attività".'}
    </div>`;
    return;
  }

  container.innerHTML = items.map(a => {
    const extraEntries = Object.entries(a.campi_extra || {});
    return `
    <div class="activity-card">
      <div>
        <div class="activity-header">
          <div>
            <h3>${escapeHtml(a.titolo)}</h3>
            <span class="activity-category-badge">${escapeHtml(a.categoria)}</span>
          </div>
          ${isStaff ? `
            <span class="badge ${a.is_pubblicato ? 'badge-published' : 'badge-draft'}">
              ${a.is_pubblicato ? 'PUBBLICATO' : 'IN BOZZA'}
            </span>
          ` : ''}
        </div>

        ${a.locandina_url ? `
          <div style="margin: 10px 0; border-radius: 8px; overflow: hidden; max-height: 160px; cursor: pointer; border: 1px solid var(--border-light); background: #f8fafc;" onclick="openPreviewLocandina('${a.locandina_url}', ${a.id})">
            <img src="${a.locandina_url}" alt="Locandina ${escapeHtml(a.titolo)}" style="width: 100%; height: 160px; object-fit: cover; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'" onerror="this.parentElement.style.display='none'">
            <div style="font-size: 11px; padding: 3px 6px; background: rgba(0,0,0,0.65); color: #fff; text-align: center; margin-top: -24px; position: relative;">🔍 Ingrandisci Locandina</div>
          </div>
        ` : ''}

        <p class="activity-desc" style="margin-top: 10px;">${escapeHtml(a.descrizione || '')}</p>

        ${extraEntries.length > 0 ? `
          <div style="margin: 10px 0; padding: 8px 10px; background: var(--bg-subtle); border-radius: var(--radius-sm); font-size: 12px; display: flex; flex-direction: column; gap: 4px;">
            ${extraEntries.map(([k, v]) => `
              <div><strong style="color:var(--primary);">${escapeHtml(k)}:</strong> <span style="color:var(--ink-800);">${escapeHtml(v)}</span></div>
            `).join('')}
          </div>
        ` : ''}
      </div>

      <div class="activity-meta">
        <span>👶 <strong>Età: ${a.eta_min} - ${a.eta_max} anni</strong></span>
        <span>👥 Posti: <strong>${a.posti_disponibili !== null ? `${a.posti_disponibili} rimasti` : 'Illimitati'}</strong></span>
        <span>📅 ${a.data_inizio_it || 'In corso'} ${a.data_fine_it ? `- ${a.data_fine_it}` : ''}</span>
      </div>

      <div class="activity-footer">
        <div class="activity-price">
          € ${a.quota_iscrizione.toFixed(2)}
          <small>/ quota</small>
        </div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${isStaff ? `
            <button class="btn btn-sm btn-secondary" onclick="openModalModificaAttivita(${a.id})" title="Modifica dettagli attività">
              ✏ Modifica
            </button>
            <button class="btn btn-sm btn-secondary" onclick="togglePubblicazioneAttivita(${a.id})">
              ${a.is_pubblicato ? 'Bozza' : 'Pubblica'}
            </button>
            <button class="btn btn-sm btn-danger" onclick="eliminaAttivita(${a.id})" title="Elimina definitivamente questa attività">
              🗑️ Elimina
            </button>
          ` : ''}
          <button class="btn btn-sm btn-primary" onclick="openModalNuovaIscrizione(${a.id})">
            Iscriviti →
          </button>
        </div>
      </div>
    </div>
  `;
  }).join('');
}

async function togglePubblicazioneAttivita(id) {
  try {
    const res = await fetch(`/api/attivita/${id}/toggle-pubblicazione`, { method: 'PUT' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica stato');
    showToast(data.message, 'success');
    await loadAttivita();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

let currentCatFilter = '';
let currentStatusFilter = 'all';

function applyAttivitaFilters() {
  let list = cacheAttivita;
  if (currentCatFilter) {
    list = list.filter(a => a.categoria === currentCatFilter);
  }
  if (currentStatusFilter === 'published') {
    list = list.filter(a => a.is_pubblicato);
  } else if (currentStatusFilter === 'draft') {
    list = list.filter(a => !a.is_pubblicato);
  }
  renderAttivitaCatalog(list);
}

function filterAttivitaByCategory(cat, btn) {
  currentCatFilter = cat;
  document.querySelectorAll('.filter-att-btn').forEach(b => {
    b.className = 'btn btn-sm btn-secondary filter-att-btn';
  });
  btn.className = 'btn btn-sm btn-primary filter-att-btn active';
  applyAttivitaFilters();
}

function filterAttivitaByStatus(status, btn) {
  currentStatusFilter = status;
  document.querySelectorAll('.filter-status-btn').forEach(b => {
    b.className = 'btn btn-sm btn-secondary filter-status-btn';
  });
  btn.className = 'btn btn-sm btn-primary filter-status-btn active';
  applyAttivitaFilters();
}

// ================= VIEW 4: ORATORIO (ESTIVO, INVERNALE, ALLERGIE) =================
let cacheGruppiOratorio = [];
let currentOratorioTipoTab = 'estivo'; // 'estivo' | 'invernale' | 'allergie'
let currentOratorioAnnoFilter = '2026/2027';
let cacheRegistroOratorio = null;
let statoPresenzeCorrentiOratorio = {};
let currentEditingOratorioId = null;

async function loadOratorio() {
  const roles = (currentUser && currentUser.tutti_i_ruoli) || [currentUser ? currentUser.ruolo : 'utente'];
  const isSupervisor = roles.some(r => ['admin', 'parroco', 'segreteria'].includes(r));
  const isAnimatore = isSupervisor || roles.includes('oratorio');

  if (!isAnimatore) {
    // Genitore / Fedele: visualizza iscrizioni e presenze dei propri figli
    const staffSec = document.getElementById('oratorioStaffSection');
    const staffActions = document.getElementById('oratorioStaffHeaderActions');
    const parentSec = document.getElementById('oratorioParentSection');
    if (staffSec) staffSec.style.display = 'none';
    if (staffActions) staffActions.style.display = 'none';
    if (parentSec) parentSec.style.display = 'block';
    const titleEl = document.getElementById('oratorioPageTitle');
    const descEl = document.getElementById('oratorioPageDesc');
    if (titleEl) titleEl.textContent = 'Oratorio & Estate Ragazzi dei Tuoi Figli';
    if (descEl) descEl.textContent = 'Consulta i gruppi assegnati a tuo figlio/a per l\'Oratorio Estivo o Invernale, gli animatori di riferimento e il registro presenze.';
    await loadOratorioParentView();
    return;
  }

  // Staff / Animatori / Segreteria
  const staffSec = document.getElementById('oratorioStaffSection');
  const staffActions = document.getElementById('oratorioStaffHeaderActions');
  const parentSec = document.getElementById('oratorioParentSection');
  if (staffSec) staffSec.style.display = 'block';
  if (staffActions) staffActions.style.display = 'flex';
  if (parentSec) parentSec.style.display = 'none';
  const titleEl = document.getElementById('oratorioPageTitle');
  const descEl = document.getElementById('oratorioPageDesc');
  if (titleEl) titleEl.textContent = 'Oratorio & Estate Ragazzi (Sacro Cuore)';
  if (descEl) descEl.textContent = 'Gestione gruppi Oratorio Estivo ed Invernale, registro presenze giornaliero, animatori e schede allergie per la cucina.';

  try {
    const [gruppiRes, allergieRes] = await Promise.all([
      fetch('/api/oratorio/gruppi'),
      fetch('/api/oratorio/allergie')
    ]);

    const dataG = await gruppiRes.json();
    const dataA = await allergieRes.json();

    cacheGruppiOratorio = dataG.gruppi || [];

    // Aggiorna KPI Cucina & Allergie
    const kpiEl = document.getElementById('allergiesKpiRow');
    if (kpiEl && dataA.conteggi) {
      const c = dataA.conteggi;
      kpiEl.innerHTML = `
        <span class="allergy-tag celiac" style="font-size: 13px; padding: 6px 12px;">🌾 Celiachia: <strong>${c.celiachia_glutine || 0}</strong></span>
        <span class="allergy-tag lactose" style="font-size: 13px; padding: 6px 12px;">🥛 Lattosio: <strong>${c.lattosio || 0}</strong></span>
        <span class="allergy-tag peanut" style="font-size: 13px; padding: 6px 12px;">🥜 Arachidi: <strong>${c.arachidi_frutta_secca || 0}</strong></span>
        <span class="allergy-tag meds" style="font-size: 13px; padding: 6px 12px;">💊 Farmaci: <strong>${c.farmaci_salvavita || 0}</strong></span>
      `;
    }

    // Popola tabella riassuntiva allergie
    const tbodyAllergie = document.querySelector('#tableAllergieOratorio tbody');
    if (tbodyAllergie) {
      if (!dataA.segnalazioni || !dataA.segnalazioni.length) {
        tbodyAllergie.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--ink-500);">Nessun partecipante con intolleranze/allergie censito.</td></tr>`;
      } else {
        tbodyAllergie.innerHTML = dataA.segnalazioni.map(s => `
          <tr>
            <td><strong>${escapeHtml(s.nominativo)}</strong></td>
            <td>${s.eta ? `${s.eta} anni` : '-'}<br><small style="font-family:monospace; color:var(--ink-500);">${escapeHtml(s.codice_fiscale)}</small></td>
            <td><strong>${escapeHtml(s.attivita_titolo || 'Oratorio')}</strong><br><span class="badge badge-info">${escapeHtml(s.squadra || 'Generale')}</span></td>
            <td><strong style="color:#b45309;">${escapeHtml(s.intolleranze_alimentari || '-')}</strong></td>
            <td><strong style="color:#b91c1c;">${escapeHtml(s.allergie || '-')}</strong></td>
            <td><strong>📞 ${escapeHtml(s.telefono_emergenza || '-')}</strong></td>
          </tr>
        `).join('');
      }
    }

    renderGruppiOratorioGrid();
  } catch (err) {
    console.error('Errore caricamento oratorio:', err);
  }
}

function switchOratorioTab(tab) {
  currentOratorioTipoTab = tab;
  document.querySelectorAll('.tab-ora-btn').forEach(btn => {
    btn.className = 'btn btn-sm btn-secondary tab-ora-btn';
  });
  const activeBtn = document.getElementById(`tabOra${tab.charAt(0).toUpperCase() + tab.slice(1)}Btn`);
  if (activeBtn) activeBtn.className = 'btn btn-sm btn-primary tab-ora-btn active';

  const gruppiSec = document.getElementById('tabContentOraGruppi');
  const allergieSec = document.getElementById('tabContentOraAllergie');

  if (tab === 'allergie') {
    if (gruppiSec) gruppiSec.style.display = 'none';
    if (allergieSec) allergieSec.style.display = 'block';
  } else {
    if (gruppiSec) gruppiSec.style.display = 'block';
    if (allergieSec) allergieSec.style.display = 'none';
    renderGruppiOratorioGrid();
  }
}

function selezionaAnnoOratorio(anno) {
  currentOratorioAnnoFilter = anno;
  document.querySelectorAll('.ora-anno-btn').forEach(btn => {
    const text = btn.textContent.trim();
    const isMatch = (!anno && text === 'Tutti') || (anno && text.startsWith(anno));
    btn.className = isMatch 
      ? 'btn btn-sm btn-primary ora-anno-btn active' 
      : 'btn btn-sm btn-secondary ora-anno-btn';
  });
  renderGruppiOratorioGrid();
}

function filtraGruppiOratorio() {
  renderGruppiOratorioGrid();
}

function renderGruppiOratorioGrid() {
  const container = document.getElementById('oratorioGruppiGrid');
  if (!container) return;

  const q = ((document.getElementById('searchOratorioGruppi')?.value || document.getElementById('searchOratorioInput')?.value || '')).toLowerCase().trim();

  const filtrati = cacheGruppiOratorio.filter(g => {
    const matchTipo = (g.tipo_oratorio || 'estivo') === currentOratorioTipoTab;
    const matchAnno = !currentOratorioAnnoFilter || g.anno_pastorale === currentOratorioAnnoFilter;
    if (!matchTipo || !matchAnno) return false;

    if (q) {
      const matchText = (g.nome || '').toLowerCase().includes(q) ||
                        (g.luogo || '').toLowerCase().includes(q) ||
                        (g.animatori_nomi || '').toLowerCase().includes(q);
      if (!matchText) return false;
    }
    return true;
  });

  const countBadge = document.getElementById('oratorioGruppiCountBadge');
  if (countBadge) {
    countBadge.textContent = `${filtrati.length} gruppi (${currentOratorioTipoTab === 'estivo' ? 'Estivo' : 'Invernale'} ${currentOratorioAnnoFilter})`;
  }

  if (!filtrati.length) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; padding: 40px; text-align: center; background: #fff; border: 1px dashed var(--border-light); border-radius: var(--radius-md);">
        <div style="font-size: 32px; margin-bottom: 8px;">🏓</div>
        <h3 style="font-size: 16px; margin-bottom: 6px;">Nessun gruppo ${currentOratorioTipoTab === 'estivo' ? 'Estivo' : 'Invernale'} per l'anno ${escapeHtml(currentOratorioAnnoFilter)}</h3>
        <p style="color: var(--ink-500); font-size: 13.5px; margin-bottom: 16px;">Crea il primo gruppo o squadra cliccando sul pulsante "+ Nuovo Gruppo Oratorio".</p>
        <button class="btn btn-primary" onclick="openModalNuovoGruppoOratorio('${currentOratorioTipoTab}')">+ Nuovo Gruppo ${currentOratorioTipoTab === 'estivo' ? 'Estivo' : 'Invernale'}</button>
      </div>
    `;
    return;
  }

  container.innerHTML = filtrati.map(g => {
    const numIscritti = (g.ragazzi || []).length;
    const isChiuso = g.stato === 'chiuso';
    const isBozza = g.stato === 'bozza';
    const statoBadge = isChiuso 
      ? '<span class="badge badge-danger" style="font-size: 11px;">🔴 Chiuso</span>' 
      : (isBozza ? '<span class="badge badge-warning" style="font-size: 11px;">🟡 Bozza</span>' : '<span class="badge badge-success" style="font-size: 11px;">🟢 Pubblico</span>');

    const animatoriBadges = (g.animatori && g.animatori.length)
      ? g.animatori.map(a => `<span class="badge badge-neutral" style="font-size: 11.5px; margin-right: 4px;">👤 ${escapeHtml(a.nominativo)}</span>`).join('')
      : `<span style="color: var(--ink-500); font-size: 12px; font-style: italic;">Nessun animatore assegnato</span>`;

    return `
      <div class="card" style="border-top: 4px solid ${currentOratorioTipoTab === 'estivo' ? '#eab308' : '#3b82f6'}; display: flex; flex-direction: column; justify-content: space-between;">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
              <span style="font-size: 18px;">${currentOratorioTipoTab === 'estivo' ? '☀️' : '❄️'}</span>
              <h3 style="margin: 0; font-size: 16.5px; font-weight: 700; color: var(--ink-900);">${escapeHtml(g.nome)}</h3>
            </div>
            <span style="font-size: 12px; color: var(--ink-500); font-weight: 600;">Anno Pastorale: ${escapeHtml(g.anno_pastorale)}</span>
          </div>
          <div>${statoBadge}</div>
        </div>

        <div class="card-body" style="padding-top: 10px; padding-bottom: 10px;">
          <div style="font-size: 13px; color: var(--ink-700); margin-bottom: 8px;">
            <div>🕒 <strong>Orario:</strong> ${escapeHtml(g.orario_incontri || 'Sabato / Pomeriggio')}</div>
            <div>📍 <strong>Luogo:</strong> ${escapeHtml(g.luogo || 'Cortile / Salone Oratorio')}</div>
            <div style="margin-top: 4px;">👥 <strong>Iscritti:</strong> <span class="badge badge-info">${numIscritti} ragazzi</span> ${g.max_iscritti ? `<small style="color:var(--ink-500);">(Max: ${g.max_iscritti})</small>` : ''}</div>
          </div>

          <div style="margin-top: 10px; border-top: 1px dashed var(--border-light); padding-top: 8px;">
            <strong style="font-size: 12px; color: var(--ink-600); display: block; margin-bottom: 4px;">Animatori Responsabili:</strong>
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">${animatoriBadges}</div>
          </div>
        </div>

        <div class="card-footer" style="background: #f8fafc; border-top: 1px solid var(--border-light); display: flex; gap: 6px; flex-wrap: wrap; justify-content: space-between; align-items: center; padding: 10px 14px;">
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button type="button" class="btn btn-xs btn-primary" onclick="openModalRegistroPresenzeOratorio(${g.id})">
              📋 Registro Presenze
            </button>
            <button type="button" class="btn btn-xs btn-secondary" onclick="openModalAllergieGruppoOratorio(${g.id}, '${escapeHtml(g.nome)}')">
              ⚠️ Allergie
            </button>
          </div>
          <button type="button" class="btn btn-xs btn-outline-primary" onclick="openModalModificaGruppoOratorio(${g.id})">
            ✏️ Modifica
          </button>
        </div>
      </div>
    `;
  }).join('');
}

async function loadOratorioParentView() {
  const container = document.getElementById('oratorioParentContainer');
  if (!container) return;
  container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--ink-500);">Caricamento oratorio dei tuoi figli...</div>';

  try {
    const res = await fetch('/api/oratorio/miei-figli');
    const data = await res.json();
    if (!data.ha_famiglia || !data.figli || !data.figli.length) {
      container.innerHTML = `
        <div class="card" style="padding: 30px; text-align: center;">
          <h3 style="font-size: 16px; margin-bottom: 8px;">Nessun componente registrato nel nucleo familiare</h3>
          <p style="color: var(--ink-500); font-size: 13.5px; margin-bottom: 16px;">
            Aggiungi i tuoi figli nella sezione "La Mia Famiglia" per visualizzare e gestire le iscrizioni all'Oratorio Estivo o Invernale.
          </p>
          <button class="btn btn-primary" onclick="navigateTo('famiglia')">Vai a La Mia Famiglia →</button>
        </div>
      `;
      return;
    }

    container.innerHTML = data.figli.map(figlio => {
      const isAssegnato = figlio.is_assegnato;
      const gruppi = figlio.gruppi || [];

      return `
        <div class="card" style="border-left: 4px solid var(--primary); padding: 22px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; border-bottom: 1px solid var(--border-light); padding-bottom: 14px;">
            <div>
              <span class="badge ${isAssegnato ? 'badge-success' : 'badge-neutral'}" style="font-size: 11px; margin-bottom: 6px;">
                ${isAssegnato ? 'ISCRITTO ALL\'ORATORIO' : 'NON ANCORA ISCRITTO'}
              </span>
              <h2 style="font-size: 20px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(figlio.nominativo)}</h2>
              <div style="font-size: 13px; color: var(--ink-600); margin-top: 4px;">
                Età: <strong>${figlio.eta !== null ? figlio.eta + ' anni' : 'N/D'}</strong> · Data Nascita: <strong>${figlio.data_nascita_it || 'N/D'}</strong> · CF: <code>${figlio.codice_fiscale}</code>
              </div>
            </div>
            <div>
              <button class="btn btn-sm btn-primary" onclick="openModalIscriviFiglioOratorio('${figlio.codice_fiscale}', '${escapeHtml(figlio.nominativo)}')">
                🏓 + Iscrivi a Oratorio Estivo / Invernale
              </button>
            </div>
          </div>

          ${gruppi.length > 0 ? `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
              ${gruppi.map(g => `
                <div style="background: var(--bg-subtle); border-radius: var(--radius-md); padding: 14px; border: 1px solid var(--border-light);">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="font-size: 15px; color: var(--primary);">
                      ${g.tipo_oratorio === 'estivo' ? '☀️ Oratorio Estivo' : '❄️ Oratorio Invernale'}: ${escapeHtml(g.nome)}
                    </strong>
                    <span class="badge badge-info" style="font-size: 11px;">${escapeHtml(g.anno_pastorale)}</span>
                  </div>
                  <div style="font-size: 12.5px; color: var(--ink-700); line-height: 1.5;">
                    <div>🕒 <strong>Orario:</strong> ${escapeHtml(g.orario_incontri || 'Sabato / Pomeriggio')}</div>
                    <div>📍 <strong>Luogo:</strong> ${escapeHtml(g.luogo || 'Oratorio Sacro Cuore')}</div>
                    <div>👤 <strong>Animatori:</strong> ${escapeHtml(g.animatori_nomi || 'In definizione')}</div>
                  </div>
                </div>
              `).join('')}
            </div>
          ` : `
            <div style="background: #f8fafc; border: 1px dashed var(--border-light); padding: 14px; border-radius: var(--radius-sm); font-size: 13px; color: var(--ink-600); text-align: center;">
              Nessun gruppo assegnato attualmente. Clicca su "+ Iscrivi a Oratorio" per registrare tuo figlio.
            </div>
          `}
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Errore oratorio parent view:', err);
  }
}

async function openModalNuovoGruppoOratorio(tipoPredefinito = 'estivo') {
  document.getElementById('nuovoOratorioTipo').value = tipoPredefinito;
  document.getElementById('nuovoOratorioAnno').value = currentOratorioAnnoFilter || '2026/2027';
  document.getElementById('nuovoOratorioNome').value = '';
  document.getElementById('nuovoOratorioOrario').value = '';
  document.getElementById('nuovoOratorioLuogo').value = '';
  document.getElementById('nuovoOratorioMaxIscritti').value = '0';
  document.getElementById('nuovoOratorioStato').value = 'pubblico';

  const sel = document.getElementById('nuovoOratorioAnimatoriSelect');
  sel.innerHTML = '<option value="">Caricamento persone...</option>';

  try {
    const res = await fetch('/api/persone');
    const data = await res.json();
    const persone = data.persone || [];

    sel.innerHTML = persone.map(p => `
      <option value="${p.id}">${escapeHtml(p.nominativo)} (${escapeHtml(p.codice_fiscale)})</option>
    `).join('');
  } catch (err) {
    console.error('Errore caricamento persone per animatori:', err);
  }

  openModal('modalNuovoGruppoOratorio');
}

async function handleSalvaNuovoGruppoOratorio(e) {
  e.preventDefault();
  const animatoriSel = document.getElementById('nuovoOratorioAnimatoriSelect');
  const animatoriIds = Array.from(animatoriSel.selectedOptions).map(o => parseInt(o.value)).filter(Boolean);

  const payload = {
    tipo_oratorio: document.getElementById('nuovoOratorioTipo').value,
    anno_pastorale: document.getElementById('nuovoOratorioAnno').value.trim(),
    nome: document.getElementById('nuovoOratorioNome').value.trim(),
    orario_incontri: document.getElementById('nuovoOratorioOrario').value.trim(),
    luogo: document.getElementById('nuovoOratorioLuogo').value.trim(),
    max_iscritti: parseInt(document.getElementById('nuovoOratorioMaxIscritti').value) || 0,
    stato: document.getElementById('nuovoOratorioStato').value,
    animatori_ids: animatoriIds
  };

  try {
    const res = await fetch('/api/oratorio/gruppi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio gruppo');

    showToast(data.message, 'success');
    closeModal('modalNuovoGruppoOratorio');
    await loadOratorio();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalModificaGruppoOratorio(id) {
  currentEditingOratorioId = id;
  const g = cacheGruppiOratorio.find(x => x.id === id);
  if (!g) return;

  document.getElementById('modOratorioId').value = g.id;
  document.getElementById('modOratorioTipo').value = g.tipo_oratorio || 'estivo';
  document.getElementById('modOratorioAnno').value = g.anno_pastorale || '2026/2027';
  document.getElementById('modOratorioNome').value = g.nome || '';
  document.getElementById('modOratorioOrario').value = g.orario_incontri || '';
  document.getElementById('modOratorioLuogo').value = g.luogo || '';
  document.getElementById('modOratorioMaxIscritti').value = g.max_iscritti || 0;
  document.getElementById('modOratorioStato').value = g.stato || 'pubblico';

  const sel = document.getElementById('modOratorioAnimatoriSelect');
  sel.innerHTML = '<option value="">Caricamento animatori...</option>';

  try {
    const res = await fetch('/api/persone');
    const data = await res.json();
    const persone = data.persone || [];
    const animatoriIds = new Set((g.animatori || []).map(a => a.id));

    sel.innerHTML = persone.map(p => `
      <option value="${p.id}" ${animatoriIds.has(p.id) ? 'selected' : ''}>
        ${escapeHtml(p.nominativo)} (${escapeHtml(p.codice_fiscale)})
      </option>
    `).join('');
  } catch (err) {
    console.error('Errore animatori:', err);
  }

  openModal('modalModificaGruppoOratorio');
}

async function handleSalvaModificaGruppoOratorio(e) {
  e.preventDefault();
  if (!currentEditingOratorioId) return;

  const animatoriSel = document.getElementById('modOratorioAnimatoriSelect');
  const animatoriIds = Array.from(animatoriSel.selectedOptions).map(o => parseInt(o.value)).filter(Boolean);

  const payload = {
    tipo_oratorio: document.getElementById('modOratorioTipo').value,
    anno_pastorale: document.getElementById('modOratorioAnno').value.trim(),
    nome: document.getElementById('modOratorioNome').value.trim(),
    orario_incontri: document.getElementById('modOratorioOrario').value.trim(),
    luogo: document.getElementById('modOratorioLuogo').value.trim(),
    max_iscritti: parseInt(document.getElementById('modOratorioMaxIscritti').value) || 0,
    stato: document.getElementById('modOratorioStato').value,
    animatori_ids: animatoriIds
  };

  try {
    const res = await fetch(`/api/oratorio/gruppi/${currentEditingOratorioId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica gruppo');

    showToast(data.message, 'success');
    closeModal('modalModificaGruppoOratorio');
    await loadOratorio();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleEliminaGruppoOratorioCorrente() {
  if (!currentEditingOratorioId) return;
  if (!confirm('Sei sicuro di voler eliminare questo gruppo oratorio? I ragazzi torneranno non assegnati.')) return;

  try {
    const res = await fetch(`/api/oratorio/gruppi/${currentEditingOratorioId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione gruppo');

    showToast(data.message, 'success');
    closeModal('modalModificaGruppoOratorio');
    await loadOratorio();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalRegistroPresenzeOratorio(gruppoId) {
  document.getElementById('registroOratorioGruppoId').value = gruppoId;
  const g = cacheGruppiOratorio.find(x => x.id === gruppoId);
  if (!g) return;

  document.getElementById('registroOratorioTitle').textContent = `📋 Registro Presenze: ${g.nome}`;
  document.getElementById('registroOratorioSubTitle').textContent = `${g.tipo_oratorio === 'estivo' ? '☀️ Oratorio Estivo' : '❄️ Oratorio Invernale'} · Anno ${g.anno_pastorale}`;

  const today = new Date().toISOString().split('T')[0];
  document.getElementById('registroOratorioData').value = today;

  await caricaPresenzeOratorioData();
  openModal('modalRegistroPresenzeOratorio');
}

async function caricaPresenzeOratorioData() {
  const gruppoId = document.getElementById('registroOratorioGruppoId').value;
  const data = document.getElementById('registroOratorioData').value;
  const tbody = document.getElementById('registroOratorioTableBody');
  if (!tbody || !gruppoId) return;

  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Caricamento presenze...</td></tr>';

  try {
    const res = await fetch(`/api/oratorio/gruppi/${gruppoId}/presenze?data=${data}`);
    const resData = await res.json();
    cacheRegistroOratorio = resData;

    const ragazzi = resData.ragazzi || [];
    if (!ragazzi.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--ink-500);">Nessun ragazzo iscritto a questo gruppo.</td></tr>';
      return;
    }

    statoPresenzeCorrentiOratorio = {};
    tbody.innerHTML = ragazzi.map(r => {
      statoPresenzeCorrentiOratorio[r.codice_fiscale] = r.presente || false;
      const noteSanitarie = [r.allergie, r.intolleranze_alimentari].filter(Boolean).join('; ');

      return `
        <tr>
          <td style="text-align: center;">
            <input type="checkbox" class="presenza-oratorio-chk" data-cf="${r.codice_fiscale}" ${r.presente ? 'checked' : ''} onchange="statoPresenzeCorrentiOratorio['${r.codice_fiscale}'] = this.checked">
          </td>
          <td>
            <strong>${escapeHtml(r.nominativo)}</strong><br>
            <code>${escapeHtml(r.codice_fiscale)}</code>
          </td>
          <td>${r.eta !== null ? `${r.eta} anni` : 'N/D'}</td>
          <td>
            ${noteSanitarie ? `<span style="color:#b91c1c; font-weight:600; font-size:12px;">⚠️ ${escapeHtml(noteSanitarie)}</span>` : '<span style="color:#15803d; font-size:12px;">✓ Regolare</span>'}
          </td>
          <td>
            <input type="text" class="form-control form-control-sm presenza-oratorio-nota" data-cf="${r.codice_fiscale}" value="${escapeHtml(r.note_presenza || '')}" placeholder="Note..." style="font-size:12px;">
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--danger); padding:20px;">Errore: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function segnaTuttiPresenzeOratorio(presente) {
  document.querySelectorAll('.presenza-oratorio-chk').forEach(chk => {
    chk.checked = presente;
    const cf = chk.getAttribute('data-cf');
    if (cf) statoPresenzeCorrentiOratorio[cf] = presente;
  });
}

async function handleSalvaPresenzeOratorio(e) {
  e.preventDefault();
  const gruppoId = document.getElementById('registroOratorioGruppoId').value;
  const data = document.getElementById('registroOratorioData').value;

  const presenze = [];
  document.querySelectorAll('.presenza-oratorio-chk').forEach(chk => {
    const cf = chk.getAttribute('data-cf');
    const notaInput = document.querySelector(`.presenza-oratorio-nota[data-cf="${cf}"]`);
    presenze.push({
      codice_fiscale: cf,
      presente: chk.checked,
      note: notaInput ? notaInput.value.trim() : ''
    });
  });

  try {
    const res = await fetch(`/api/oratorio/gruppi/${gruppoId}/presenze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, presenze })
    });
    const resData = await res.json();
    if (!res.ok) throw new Error(resData.error || 'Errore salvataggio presenze');

    showToast(resData.message || 'Presenze salvate con successo!', 'success');
    closeModal('modalRegistroPresenzeOratorio');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalAllergieGruppoOratorio(gruppoId, nomeGruppo) {
  document.getElementById('allergieGruppoTitle').textContent = `⚠️ Scheda Allergie & Sanitaria: ${nomeGruppo}`;
  document.getElementById('allergieGruppoSubTitle').textContent = `Report medico per animatori e cucina oratorio`;

  const tbody = document.getElementById('allergieGruppoTableBody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Caricamento schede sanitarie...</td></tr>';
  openModal('modalAllergieGruppoOratorio');

  try {
    const res = await fetch(`/api/oratorio/gruppi/${gruppoId}/allergie`);
    const data = await res.json();
    const segnalazioni = data.segnalazioni || [];

    if (!segnalazioni.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--ink-500);">Nessuna allergia o intolleranza segnalata tra i ragazzi di questo gruppo.</td></tr>';
      return;
    }

    tbody.innerHTML = segnalazioni.map(s => `
      <tr>
        <td><strong>${escapeHtml(s.nominativo)}</strong><br><code>${escapeHtml(s.codice_fiscale)}</code></td>
        <td>${s.eta !== null ? `${s.eta} anni` : '-'}</td>
        <td>
          ${escapeHtml(s.nome_famiglia || '-')}<br>
          <strong>📞 ${escapeHtml(s.telefono || '-')}</strong>
        </td>
        <td><strong style="color: #b91c1c;">${escapeHtml(s.allergie || s.intolleranze_alimentari || '-')}</strong></td>
        <td>${escapeHtml(s.note_mediche || s.farmaci_salvavita || 'Nessuna prescrizione specifica')}</td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); padding: 20px;">Errore: ${escapeHtml(err.message)}</td></tr>`;
  }
}

let cacheGruppiIscrizioneFiglioOra = [];
async function openModalIscriviFiglioOratorio(cf, nominativo) {
  document.getElementById('iscriviFiglioOraCF').value = cf;
  document.getElementById('iscriviFiglioOraNominativo').textContent = nominativo;

  const sel = document.getElementById('iscriviFiglioOraGruppoSelect');
  sel.innerHTML = '<option value="">Caricamento gruppi oratorio...</option>';
  const preview = document.getElementById('iscriviFiglioOraPreviewInfo');
  preview.innerHTML = '';

  try {
    const res = await fetch('/api/oratorio/miei-figli');
    const data = await res.json();
    const child = (data.figli || []).find(f => f.codice_fiscale === cf);
    cacheGruppiIscrizioneFiglioOra = (child && child.gruppi_disponibili && child.gruppi_disponibili.length) ? child.gruppi_disponibili : (data.gruppi_disponibili || []);

    if (!cacheGruppiIscrizioneFiglioOra.length) {
      sel.innerHTML = '<option value="">Nessun gruppo oratorio aperto alle iscrizioni</option>';
      return;
    }

    sel.innerHTML = '<option value="">-- Scegli gruppo / squadra oratorio --</option>' +
      cacheGruppiIscrizioneFiglioOra.map(g => `
        <option value="${g.id}">
          ${g.tipo_oratorio === 'estivo' ? '☀️ Estivo' : '❄️ Invernale'}: ${escapeHtml(g.nome)} (${escapeHtml(g.anno_pastorale)}) · Animatori: ${escapeHtml(g.animatori_nomi || 'In definizione')}
        </option>
      `).join('');

    sel.onchange = function() {
      const gId = parseInt(this.value);
      const g = cacheGruppiIscrizioneFiglioOra.find(x => x.id === gId);
      if (g) {
        preview.innerHTML = `
          <strong>Stagione:</strong> ${g.tipo_oratorio === 'estivo' ? '☀️ Oratorio Estivo (Estate Ragazzi)' : '❄️ Oratorio Invernale'}<br>
          <strong>Orario:</strong> ${escapeHtml(g.orario_incontri || 'Sabato pomeriggio')}<br>
          <strong>Luogo:</strong> ${escapeHtml(g.luogo || 'Oratorio Sacro Cuore')}<br>
          <strong>Animatori:</strong> ${escapeHtml(g.animatori_nomi || 'In definizione')}
        `;
      } else {
        preview.innerHTML = '';
      }
    };
  } catch (err) {
    console.error('Errore gruppi oratorio:', err);
  }

  openModal('modalIscriviFiglioOratorio');
}

async function handleSalvaIscrizioneFiglioOratorio(e) {
  e.preventDefault();
  const cf = document.getElementById('iscriviFiglioOraCF').value;
  const gruppoId = parseInt(document.getElementById('iscriviFiglioOraGruppoSelect').value);

  if (!gruppoId) {
    showToast('Seleziona un gruppo dell\'oratorio', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/oratorio/iscrivi-figlio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf, gruppo_id: gruppoId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore iscrizione');

    showToast(data.message, 'success');
    closeModal('modalIscriviFiglioOratorio');
    await loadOratorioParentView();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function salvaPresenzeOratorio() {
  const data = document.getElementById('inputDataPresenzeOratorio')?.value;
  const checkboxes = document.querySelectorAll('.check-presenza');
  const presenze = [];

  checkboxes.forEach(cb => {
    presenze.push({
      codice_fiscale: cb.getAttribute('data-cf'),
      presente: cb.checked
    });
  });

  try {
    const res = await fetch('/api/oratorio/presenze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, presenze })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore salvataggio presenze');
    showToast(d.message, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= VIEW 5: CATECHISMO (GRUPPI MULTIPLI) =================
let cacheGruppiCatechismo = [];
let cacheIsCatechistaOnly = false;
let currentCatechismoAnnoFilter = '2026/2027';
let cacheRegistroCatechismo = null;
let statoPresenzeCorrentiCatechismo = {};

async function loadCatechismo() {
  const roles = (currentUser && currentUser.tutti_i_ruoli) || [currentUser ? currentUser.ruolo : 'utente'];
  const isSupervisor = roles.some(r => ['admin', 'parroco', 'segreteria'].includes(r));
  const isCatechista = isSupervisor || roles.includes('catechista');

  if (!isCatechista) {
    // Profilo Utente / Genitore: carica SOLO la vista per i propri figli
    const staffSec = document.getElementById('catechismoStaffSection');
    const staffActions = document.getElementById('catechismoStaffHeaderActions');
    const parentSec = document.getElementById('catechismoParentSection');
    if (staffSec) staffSec.style.display = 'none';
    if (staffActions) staffActions.style.display = 'none';
    if (parentSec) parentSec.style.display = 'block';
    const titleEl = document.getElementById('catechismoPageTitle');
    const descEl = document.getElementById('catechismoPageDesc');
    if (titleEl) titleEl.textContent = 'Catechismo dei Tuoi Figli';
    if (descEl) descEl.textContent = 'Consulta il gruppo assegnato, il catechista di riferimento, gli orari degli incontri e il registro presenze dei tuoi figli.';
    await loadCatechismoParentView();
    return;
  }

  // Profilo Staff / Catechista / Amministrazione
  const staffSec = document.getElementById('catechismoStaffSection');
  const staffActions = document.getElementById('catechismoStaffHeaderActions');
  const parentSec = document.getElementById('catechismoParentSection');
  if (staffSec) staffSec.style.display = 'block';
  if (staffActions) staffActions.style.display = 'flex';
  if (parentSec) parentSec.style.display = 'none';
  const titleEl = document.getElementById('catechismoPageTitle');
  const descEl = document.getElementById('catechismoPageDesc');
  if (titleEl) titleEl.textContent = 'Gruppi di Catechismo & Archivio';
  if (descEl) descEl.textContent = 'Archivio per anni pastorali, appello presenze, storico incontri svolti, allergie e intolleranze dei ragazzi.';

  try {
    const res = await fetch('/api/catechismo/gruppi');
    const data = await res.json();
    cacheGruppiCatechismo = data.gruppi || [];
    cacheIsCatechistaOnly = data.is_catechista_only || false;

    // Se è solo catechista, nascondi pulsanti di creazione e assegnazione di massa
    const btnCreaGruppo = document.querySelector('#catechismoStaffHeaderActions button[onclick*="openModalNuovoGruppoCatechismo"]');
    const btnMassa = document.querySelector('#catechismoStaffHeaderActions button[onclick*="openModalAssegnaPersoneMassa"]');
    if (btnCreaGruppo) btnCreaGruppo.style.display = cacheIsCatechistaOnly ? 'none' : 'inline-flex';
    if (btnMassa) btnMassa.style.display = cacheIsCatechistaOnly ? 'none' : 'inline-flex';

    renderGruppiCatechismoGrid();
  } catch (err) {
    console.error('Errore catechismo:', err);
  }
}

async function loadCatechismoParentView() {
  const container = document.getElementById('catechismoParentContainer');
  if (!container) return;
  container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--ink-500);">Caricamento dati catechismo dei tuoi figli...</div>';

  try {
    const res = await fetch('/api/catechismo/miei-figli');
    const data = await res.json();
    if (!data.ha_famiglia || !data.figli || !data.figli.length) {
      container.innerHTML = `
        <div class="card" style="padding: 30px; text-align: center;">
          <h3 style="font-size: 16px; margin-bottom: 8px;">Nessun figlio registrato nel nucleo familiare</h3>
          <p style="color: var(--ink-500); font-size: 13.5px; margin-bottom: 16px;">
            Aggiungi i componenti della tua famiglia nella sezione "La Mia Famiglia" per poter visualizzare e gestire le iscrizioni al catechismo.
          </p>
          <button class="btn btn-primary" onclick="navigateTo('famiglia')">Vai a La Mia Famiglia →</button>
        </div>
      `;
      return;
    }

    container.innerHTML = data.figli.map(figlio => {
      if (figlio.is_assegnato && figlio.gruppo) {
        const g = figlio.gruppo;
        const stats = figlio.statistiche || { totale_incontri: 0, presenti: 0, assenti: 0, percentuale: 0 };
        const presenze = figlio.storico_presenze || [];
        const catNomi = g.catechisti && g.catechisti.length > 0 
          ? g.catechisti.map(c => `<strong>${escapeHtml(c.nominativo)}</strong>${c.email ? ` (${escapeHtml(c.email)})` : ''}${c.telefono ? ` · Tel: ${escapeHtml(c.telefono)}` : ''}`).join('<br>')
          : `<strong>${escapeHtml(g.catechista_nome)}</strong>`;

        return `
          <div class="card" style="border-left: 4px solid var(--primary); padding: 22px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; border-bottom: 1px solid var(--border-light); padding-bottom: 14px;">
              <div>
                <span class="badge badge-success" style="font-size: 11px; margin-bottom: 6px;">ISCRITTO / ASSEGNATO</span>
                <h2 style="font-size: 20px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(figlio.nominativo)}</h2>
                <div style="font-size: 13px; color: var(--ink-600); margin-top: 4px;">
                  Età: <strong>${figlio.eta !== null ? figlio.eta + ' anni' : 'N/D'}</strong> · Data di Nascita: <strong>${figlio.data_nascita_it || 'N/D'}</strong> · CF: <code>${figlio.codice_fiscale}</code>
                </div>
              </div>
              <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 6px;">
                <span style="font-size: 13px; font-weight: 700; color: var(--wine-700); background: #fdf2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 4px 10px;">
                  📖 ${escapeHtml(g.nome)} (${escapeHtml(g.anno_pastorale)})
                </span>
                ${g.google_calendar_url ? `
                  <a href="${escapeHtml(g.google_calendar_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-xs btn-outline-primary" style="font-weight: 700; display: inline-flex; align-items: center; gap: 4px; background: #fff;">
                    📅 Aggiungi al mio Google Calendar ↗
                  </a>
                ` : ''}
              </div>
            </div>

            <!-- Dettagli Gruppo & Catechista -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px; background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md);">
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Catechista di Riferimento</div>
                <div style="font-size: 13.5px; color: var(--ink-800); line-height: 1.5;">${catNomi}</div>
              </div>
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Orario Incontri & Aula</div>
                <div style="font-size: 13.5px; color: var(--ink-800);">
                  🕒 <strong>${escapeHtml(g.orario_incontri || 'In definizione')}</strong><br>
                  🏫 Aula: <strong>${escapeHtml(g.aula || 'Chiesa / Oratorio')}</strong>
                </div>
              </div>
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Presenze agli Incontri</div>
                <div style="font-size: 13.5px; color: var(--ink-800);">
                  <strong style="color: var(--primary); font-size: 17px;">${stats.percentuale}%</strong> di frequenza<br>
                  <span>${stats.presenti} presenti, ${stats.assenti} assenti su ${stats.totale_incontri} incontri</span>
                </div>
              </div>
            </div>

            <!-- Registro Incontri del Singolo Figlio -->
            <h4 style="font-size: 14px; font-weight: 700; color: var(--ink-800); margin-bottom: 10px;">
              📅 Registro Personale Incontri & Presenze
            </h4>
            ${!presenze.length ? `
              <p style="font-size: 13px; color: var(--ink-500); font-style: italic;">
                Nessun appello ancora registrato per questo gruppo nell'anno pastorale in corso.
              </p>
            ` : `
              <div class="table-responsive" style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border-light); border-radius: var(--radius-sm);">
                <table class="custom-table" style="font-size: 12.5px;">
                  <thead>
                    <tr>
                      <th>Data Incontro</th>
                      <th>Esito Presenza</th>
                      <th>Note Incontro / Titolo</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${presenze.map(p => `
                      <tr>
                        <td>
                          <strong>${p.data_it}</strong>
                          ${p.concorre_percentuale === false ? '<br><span class="badge badge-neutral" style="font-size: 10px;">Non concorre a %</span>' : ''}
                        </td>
                        <td>
                          ${p.presente 
                            ? '<span class="badge badge-success">✓ Presente</span>' 
                            : '<span class="badge badge-danger">✗ Assente</span>'}
                        </td>
                        <td style="color: var(--ink-600);">
                          ${p.titolo_incontro ? `<strong>${escapeHtml(p.titolo_incontro)}</strong> ` : ''}
                          ${p.note ? escapeHtml(p.note) : (!p.titolo_incontro ? '-' : '')}
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            `}
          </div>
        `;
      } else {
        // Figlio non ancora iscritto
        return `
          <div class="card" style="border-left: 4px solid var(--accent-gold); padding: 22px;">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap;">
              <div>
                <span class="badge badge-warning" style="font-size: 11px; margin-bottom: 6px;">NON ANCORA ISCRITTO</span>
                <h2 style="font-size: 19px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(figlio.nominativo)}</h2>
                <div style="font-size: 13px; color: var(--ink-600); margin-top: 4px;">
                  Età: <strong>${figlio.eta !== null ? figlio.eta + ' anni' : 'N/D'}</strong> · Data di Nascita: <strong>${figlio.data_nascita_it || 'N/D'}</strong>
                </div>
                <p style="font-size: 13px; color: var(--ink-700); margin: 8px 0 0;">
                  Questo fanciullo non risulta ancora assegnato ad un gruppo di catechesi per l'anno in corso.
                </p>
              </div>
              <div>
                <button class="btn btn-primary" onclick="openModalIscriviFiglioCatechismo('${figlio.codice_fiscale}', '${escapeHtml(figlio.nominativo)}')">
                  + Iscrivi al Gruppo Catechismo
                </button>
              </div>
            </div>
          </div>
        `;
      }
    }).join('');
  } catch (err) {
    container.innerHTML = `<div style="color: var(--danger); padding: 20px;">Errore: ${escapeHtml(err.message)}</div>`;
  }
}

function selezionaAnnoCatechismo(anno) {
  currentCatechismoAnnoFilter = anno;
  document.querySelectorAll('.cat-anno-btn').forEach(btn => {
    const text = btn.textContent.trim();
    if ((!anno && text === 'Tutti') || (anno && text.startsWith(anno))) {
      btn.className = 'btn btn-sm btn-primary cat-anno-btn active';
    } else {
      btn.className = 'btn btn-sm btn-secondary cat-anno-btn';
    }
  });
  renderGruppiCatechismoGrid();
}

function filtraGruppiCatechismo() {
  renderGruppiCatechismoGrid();
}

function renderGruppiCatechismoGrid() {
  const container = document.getElementById('catechismoGruppiGrid');
  if (!container) return;

  const annoFilter = (currentCatechismoAnnoFilter || '').trim();
  const searchFilter = (document.getElementById('searchCatechismoGruppi')?.value || '').trim().toLowerCase();

  let items = cacheGruppiCatechismo;

  if (annoFilter) {
    items = items.filter(g => (g.anno_pastorale || '2026/2027') === annoFilter);
  }

  if (searchFilter) {
    items = items.filter(g => 
      (g.nome || '').toLowerCase().includes(searchFilter) ||
      (g.catechista_nome || '').toLowerCase().includes(searchFilter) ||
      (g.aula || '').toLowerCase().includes(searchFilter) ||
      (g.anno_catechismo || '').toLowerCase().includes(searchFilter)
    );
  }

  if (!items.length) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--ink-500); background: #fff; border-radius: var(--radius-lg); border: 1px solid var(--border-light);">
        ${cacheIsCatechistaOnly 
          ? 'Nessun gruppo di catechismo assegnato trovato con i filtri correnti.' 
          : 'Nessun gruppo di catechismo trovato nell\'anno o nella ricerca selezionata. Clicca "+ Crea Nuovo Gruppo Catechismo" per aggiungere una classe.'}
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(g => {
    const badgeStato = g.stato === 'bozza'
      ? '<span class="badge" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; font-size:10.5px;">🔒 BOZZA</span>'
      : (g.stato === 'chiuso'
          ? '<span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecaca; font-size:10.5px;">🔴 CHIUSO</span>'
          : '<span class="badge" style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-size:10.5px;">🟢 PUBBLICO</span>');

    return `
    <div class="catechismo-card">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: var(--ink-900); margin: 0 0 4px 0;">${escapeHtml(g.nome)}</h3>
          <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
            <span class="badge badge-info" style="font-size: 11px;">📁 ${escapeHtml(g.anno_pastorale || '2026/2027')}</span>
            ${badgeStato}
            <span style="font-size: 12px; color: var(--accent-gold); font-weight: 600;">${escapeHtml(g.anno_catechismo || 'Anno Generale')}</span>
          </div>
        </div>
        <span class="badge badge-success" style="font-size: 12px;">${g.totale_ragazzi} ragazzi</span>
      </div>

      <div style="font-size: 12.5px; color: var(--ink-700); line-height: 1.5; background: var(--bg-subtle); padding: 10px; border-radius: var(--radius-md);">
        <div>👤 Catechista: <strong>${escapeHtml(g.catechista_nome || 'Non assegnato')}</strong></div>
        <div>🕒 Orario: <strong>${escapeHtml(g.orario_incontri || 'Non specificato')}</strong></div>
        <div>📍 Aula: <strong>${escapeHtml(g.aula || 'Non specificata')}</strong></div>
        ${g.note ? `<div style="margin-top: 4px; font-style: italic; color: var(--ink-500);">📝 ${escapeHtml(g.note)}</div>` : ''}
      </div>

      <div style="flex: 1;">
        <strong style="font-size: 12px; text-transform: uppercase; color: var(--ink-500); display: block; margin-bottom: 6px;">Ragazzi nel Gruppo:</strong>
        ${g.ragazzi && g.ragazzi.length ? `
          <div style="display: flex; flex-direction: column; gap: 4px; max-height: 140px; overflow-y: auto;">
            ${g.ragazzi.map(r => `
              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; padding: 4px 6px; background: #fff; border: 1px solid var(--border-light); border-radius: var(--radius-sm);">
                <span><strong>${escapeHtml(r.nominativo)}</strong> <small style="color:var(--ink-500);">(${r.eta !== null ? `${r.eta} anni` : r.codice_fiscale})</small></span>
                ${!cacheIsCatechistaOnly ? `<button onclick="rimuoviRagazzoDaGruppo(${g.id}, '${r.codice_fiscale}')" style="background:none; border:none; color:#dc2626; cursor:pointer; font-weight:bold; font-size:14px;" title="Rimuovi dal gruppo">×</button>` : ''}
              </div>
            `).join('')}
          </div>
        ` : `<small style="color:var(--ink-500);">Nessun ragazzo ancora assegnato al gruppo.</small>`}
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px solid var(--border-light); padding-top: 10px;">
        <button class="btn btn-sm btn-primary" onclick="openModalAppelloCatechismo(${g.id})">
          📖 Appello & Registro
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalStoricoIncontriCatechismo(${g.id})">
          📅 Storico Incontri
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalAllergieGruppoCatechismo(${g.id})" style="color: #b45309; border-color: #fde68a; background: #fffbeb;">
          ⚠️ Allergie & Info
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalModificaGruppoCatechismo(${g.id})">
          ✏️ Modifica
        </button>
      </div>

      ${!cacheIsCatechistaOnly ? `
        <div style="display: flex; gap: 6px; margin-top: 6px;">
          <button class="btn btn-sm btn-secondary" style="flex: 1;" onclick="openModalAssegnaRagazzoCatechismo(${g.id})">
            + Aggiungi Ragazzo
          </button>
          <button class="btn btn-sm btn-danger" onclick="eliminaGruppoCatechismo(${g.id})" title="Elimina gruppo">
            🗑️
          </button>
        </div>
      ` : ''}
    </div>
    `;
  }).join('');
}

async function openModalAppelloCatechismo(gruppoId) {
  const g = cacheGruppiCatechismo.find(x => x.id === gruppoId);
  if (!g) return;

  document.getElementById('appelloGruppoId').value = g.id;
  document.getElementById('appelloAttivitaId').value = g.attivita_id || g.id;
  document.getElementById('appelloGruppoNome').textContent = g.nome;
  document.getElementById('appelloGruppoDettaglio').textContent = 
    `Catechista: ${g.catechista_nome || 'Non assegnato'} · Anno: ${g.anno_pastorale || '2026/2027'} ${g.aula ? '· Aula: ' + g.aula : ''}`;

  const today = new Date().toISOString().split('T')[0];
  document.getElementById('appelloDataIncontro').value = today;

  openModal('modalAppelloCatechismo');

  const bodyEl = document.getElementById('registroElettronicoCatechismoBody');
  bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--ink-500);"><div class="spinner" style="margin:0 auto 10px;"></div>Caricamento registro elettronico e presenze passate in corso...</td></tr>`;

  try {
    const res = await fetch(`/api/catechismo/gruppi/${gruppoId}/registro`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore caricamento registro');

    cacheRegistroCatechismo = data;
    const statsBadge = document.getElementById('appelloStatsGruppo');
    if (statsBadge) {
      statsBadge.textContent = `${data.totale_date} incontri registrati · ${data.studenti.length} iscritti`;
    }

    aggiornaCampiIncontroCorrente();
    inizializzaStatoPresenzeCatechismo();
    renderTabellaRegistroCatechismo();
  } catch (err) {
    bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--crimson-600);">Errore: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function aggiornaCampiIncontroCorrente() {
  if (!cacheRegistroCatechismo) return;
  const dataSel = document.getElementById('appelloDataIncontro').value;
  const found = (cacheRegistroCatechismo.date_incontri || []).find(d => d.data === dataSel);

  const titoloInput = document.getElementById('appelloTitoloIncontro');
  const concorreChk = document.getElementById('appelloConcorrePercentuale');
  const btnCanc = document.getElementById('btnCancellaIncontroCatechismo');

  if (found) {
    if (titoloInput) titoloInput.value = found.titolo_incontro || '';
    if (concorreChk) concorreChk.checked = found.concorre_percentuale !== false;
    if (btnCanc) btnCanc.style.display = 'inline-flex';
  } else {
    if (titoloInput) titoloInput.value = '';
    if (concorreChk) concorreChk.checked = true;
    if (btnCanc) btnCanc.style.display = 'none';
  }
}

function inizializzaStatoPresenzeCatechismo() {
  statoPresenzeCorrentiCatechismo = {};
  if (!cacheRegistroCatechismo || !cacheRegistroCatechismo.studenti) return;

  const dataSel = document.getElementById('appelloDataIncontro').value;
  cacheRegistroCatechismo.studenti.forEach(s => {
    if (s.presenze_map && typeof s.presenze_map[dataSel] !== 'undefined') {
      statoPresenzeCorrentiCatechismo[s.codice_fiscale] = s.presenze_map[dataSel];
    } else {
      statoPresenzeCorrentiCatechismo[s.codice_fiscale] = true;
    }
  });
}

function impostaOggiDataCatechismo() {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('appelloDataIncontro').value = today;
  onDataIncontroCatechismoChanged();
}

function onDataIncontroCatechismoChanged() {
  aggiornaCampiIncontroCorrente();
  inizializzaStatoPresenzeCatechismo();
  renderTabellaRegistroCatechismo();
}

async function confermaCancellaIncontroCatechismo() {
  const gruppoId = parseInt(document.getElementById('appelloGruppoId').value);
  const dataStr = document.getElementById('appelloDataIncontro').value;
  if (!gruppoId || !dataStr) return;

  if (!confirm(`Sei sicuro di voler cancellare l'incontro del ${dataStr} dall'appello? Le presenze di questa data verranno rimosse definitivamente.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/catechismo/gruppi/${gruppoId}/incontri/${dataStr}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore cancellazione incontro');

    showToast(data.message || `Incontro del ${dataStr} cancellato con successo`, 'success');
    await openModalAppelloCatechismo(gruppoId);
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function segnaTuttiPresentiCatechismo() {
  if (!cacheRegistroCatechismo || !cacheRegistroCatechismo.studenti) return;
  cacheRegistroCatechismo.studenti.forEach(s => {
    statoPresenzeCorrentiCatechismo[s.codice_fiscale] = true;
  });
  renderTabellaRegistroCatechismo();
}

function segnaTuttiAssentiCatechismo() {
  if (!cacheRegistroCatechismo || !cacheRegistroCatechismo.studenti) return;
  cacheRegistroCatechismo.studenti.forEach(s => {
    statoPresenzeCorrentiCatechismo[s.codice_fiscale] = false;
  });
  renderTabellaRegistroCatechismo();
}

function togglePresenzaRagazzoCatechismo(cf, valore) {
  statoPresenzeCorrentiCatechismo[cf] = valore;
  aggiornaRigaRegistroCatechismo(cf);
  aggiornaConteggioLiveCatechismo();
}

function aggiornaConteggioLiveCatechismo() {
  const liveEl = document.getElementById('appelloConteggioLive');
  if (!liveEl || !cacheRegistroCatechismo) return;

  const total = cacheRegistroCatechismo.studenti.length;
  if (!total) {
    liveEl.textContent = '0 iscritti';
    return;
  }

  let presenti = 0;
  cacheRegistroCatechismo.studenti.forEach(s => {
    if (statoPresenzeCorrentiCatechismo[s.codice_fiscale]) presenti++;
  });
  const assenti = total - presenti;
  const perc = Math.round((presenti / total) * 100);
  liveEl.innerHTML = `<span style="color:#166534;">🟢 ${presenti} Presenti</span> · <span style="color:#991b1b;">🔴 ${assenti} Assenti</span> (${perc}%)`;
}

function aggiornaRigaRegistroCatechismo(cf) {
  const btnPres = document.getElementById(`btn-pres-cat-${cf}`);
  const btnAss = document.getElementById(`btn-ass-cat-${cf}`);
  const isPresente = statoPresenzeCorrentiCatechismo[cf] === true;

  if (btnPres && btnAss) {
    if (isPresente) {
      btnPres.className = 'btn btn-sm btn-success';
      btnPres.style.fontWeight = '700';
      btnAss.className = 'btn btn-sm btn-outline-danger';
      btnAss.style.fontWeight = 'normal';
    } else {
      btnPres.className = 'btn btn-sm btn-outline-success';
      btnPres.style.fontWeight = 'normal';
      btnAss.className = 'btn btn-sm btn-danger';
      btnAss.style.fontWeight = '700';
    }
  }
}

function renderTabellaRegistroCatechismo() {
  const bodyEl = document.getElementById('registroElettronicoCatechismoBody');
  if (!bodyEl || !cacheRegistroCatechismo) return;

  const studenti = cacheRegistroCatechismo.studenti || [];
  const dateIncontri = cacheRegistroCatechismo.date_incontri || [];
  const dataSel = document.getElementById('appelloDataIncontro').value;

  if (!studenti.length) {
    bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--ink-500);">Nessun ragazzo iscritto in questo gruppo di catechismo.</td></tr>`;
    aggiornaConteggioLiveCatechismo();
    return;
  }

  bodyEl.innerHTML = studenti.map((s, idx) => {
    const isPresente = statoPresenzeCorrentiCatechismo[s.codice_fiscale] === true;

    // Storico incontri passati
    let storicoHtml = '';
    const datePassate = dateIncontri.filter(d => d.data !== dataSel);
    if (!datePassate.length) {
      storicoHtml = '<span style="color:var(--ink-400); font-size:11.5px; font-style:italic;">Nessun altro incontro registrato</span>';
    } else {
      storicoHtml = '<div style="display:flex; gap:4px; flex-wrap:wrap; align-items:center;">' +
        datePassate.slice(-6).map(d => {
          const pres = s.presenze_map ? s.presenze_map[d.data] : undefined;
          const noPercTag = d.concorre_percentuale === false ? ' (no %)' : '';
          if (pres === true) {
            return `<span class="badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; font-size:11px; padding:2px 6px;" title="${d.data_it}${noPercTag}: Presente">✓ ${d.data_it.substring(0,5)}${d.concorre_percentuale === false ? '*' : ''}</span>`;
          } else if (pres === false) {
            return `<span class="badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-size:11px; padding:2px 6px;" title="${d.data_it}${noPercTag}: Assente">✗ ${d.data_it.substring(0,5)}${d.concorre_percentuale === false ? '*' : ''}</span>`;
          } else {
            return `<span class="badge" style="background:#f1f5f9; color:#64748b; font-size:11px; padding:2px 6px;" title="${d.data_it}: Non iscritto">- ${d.data_it.substring(0,5)}</span>`;
          }
        }).join('') +
        '</div>';
    }

    const percColor = s.percentuale >= 75 ? '#10b981' : (s.percentuale >= 50 ? '#f59e0b' : '#ef4444');

    return `
      <tr style="border-bottom: 1px solid var(--border-light);">
        <td style="text-align: center; color: var(--ink-400); font-weight: 600; font-size: 12px;">${idx + 1}</td>
        <td>
          <div style="font-weight: 700; color: var(--ink-900); font-size: 13.5px;">${escapeHtml(s.nominativo)}</div>
          <div style="font-size: 11px; color: var(--ink-500);">${escapeHtml(s.codice_fiscale)}${s.eta !== null && s.eta !== undefined ? ` · ${s.eta} anni` : ''}</div>
        </td>
        <td style="text-align: center; background: #f0f9ff; border-left: 2px solid #38bdf8; border-right: 2px solid #38bdf8; padding: 6px;">
          <div style="display: inline-flex; border-radius: var(--radius-sm); overflow: hidden; border: 1px solid var(--border-light); background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <button type="button" id="btn-pres-cat-${s.codice_fiscale}" class="btn btn-sm ${isPresente ? 'btn-success' : 'btn-outline-success'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${isPresente ? 'font-weight:700;' : ''}" onclick="togglePresenzaRagazzoCatechismo('${s.codice_fiscale}', true)">
              ✓ Presente
            </button>
            <button type="button" id="btn-ass-cat-${s.codice_fiscale}" class="btn btn-sm ${!isPresente ? 'btn-danger' : 'btn-outline-danger'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${!isPresente ? 'font-weight:700;' : ''}" onclick="togglePresenzaRagazzoCatechismo('${s.codice_fiscale}', false)">
              ✗ Assente
            </button>
          </div>
        </td>
        <td>
          ${storicoHtml}
        </td>
        <td style="text-align: center; font-size: 12.5px; font-weight: 600; color: var(--ink-700);">
          ${s.presenti} / ${s.totale_incontri}
        </td>
        <td style="text-align: center;">
          <div style="display: flex; flex-direction: column; align-items: center; gap: 3px;">
            <strong style="font-size: 12px; color: ${percColor};">${s.percentuale}%</strong>
            <div style="width: 48px; background: #e2e8f0; height: 5px; border-radius: 3px; overflow: hidden;">
              <div style="width: ${s.percentuale}%; background: ${percColor}; height: 100%;"></div>
            </div>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  aggiornaConteggioLiveCatechismo();
}

async function handleSalvaAppelloCatechismo(e) {
  e.preventDefault();
  const gruppoId = parseInt(document.getElementById('appelloGruppoId').value);
  const attivitaId = parseInt(document.getElementById('appelloAttivitaId').value);
  const data = document.getElementById('appelloDataIncontro').value;
  const titoloIncontro = (document.getElementById('appelloTitoloIncontro')?.value || '').trim();
  const concorrePercentuale = document.getElementById('appelloConcorrePercentuale')?.checked !== false;

  const presenze = Object.keys(statoPresenzeCorrentiCatechismo).map(cf => ({
    codice_fiscale: cf,
    presente: statoPresenzeCorrentiCatechismo[cf]
  }));

  const btnSalva = document.getElementById('btnSalvaRegistroCatechismo');
  if (btnSalva) {
    btnSalva.disabled = true;
    btnSalva.textContent = 'Salvataggio in corso...';
  }

  try {
    const res = await fetch('/api/catechismo/presenze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gruppo_id: gruppoId,
        attivita_id: attivitaId,
        data: data,
        titolo_incontro: titoloIncontro,
        concorre_percentuale: concorrePercentuale,
        presenze: presenze
      })
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || 'Errore salvataggio presenze');

    showToast(result.message || 'Presenze incontro registrate con successo!', 'success');
    closeModal('modalAppelloCatechismo');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btnSalva) {
      btnSalva.disabled = false;
      btnSalva.textContent = '💾 Salva Registro Presenze';
    }
  }
}

let cacheCatechisti = [];

async function loadCatechistiCheckboxes(containerId, selectedIds = []) {
  const container = document.getElementById(containerId);
  if (!container) return;
  try {
    const res = await fetch('/api/catechismo/catechisti');
    const data = await res.json();
    cacheCatechisti = data.catechisti || [];

    if (!cacheCatechisti.length) {
      container.innerHTML = '<span style="color:var(--ink-500); font-size:12.5px;">Nessun account con ruolo catechista registrato.</span>';
      return;
    }
    const prefix = containerId.startsWith('catNuovo') ? 'nuovo_cat_' : 'mod_cat_';
    container.innerHTML = cacheCatechisti.map(c => {
      const isChecked = selectedIds.includes(c.id);
      return `
        <label style="display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; padding: 3px 0;">
          <input type="checkbox" class="${prefix}chk" value="${c.id}" ${isChecked ? 'checked' : ''}>
          <span><strong>${escapeHtml(c.nominativo)}</strong> <small style="color:var(--ink-500);">(${escapeHtml(c.email)})</small></span>
        </label>
      `;
    }).join('');
  } catch (err) {
    console.error('Errore caricamento catechisti:', err);
  }
}

async function openModalNuovoGruppoCatechismo() {
  document.getElementById('catNomeGruppo').value = '';
  document.getElementById('catAnnoPercorso').value = '';
  const selAnno = document.getElementById('catAnnoPastorale');
  if (selAnno) selAnno.value = '2026/2027';
  if (document.getElementById('catStatoGruppo')) document.getElementById('catStatoGruppo').value = 'pubblico';
  document.getElementById('catOrario').value = '';
  document.getElementById('catAula').value = '';
  if (document.getElementById('catGoogleCalendarUrl')) document.getElementById('catGoogleCalendarUrl').value = '';
  document.getElementById('catNote').value = '';
  await loadCatechistiCheckboxes('catNuovoCatechistiContainer', []);
  openModal('modalNuovoGruppoCatechismo');
}

async function handleSalvaGruppoCatechismo(e) {
  e.preventDefault();
  const nome = document.getElementById('catNomeGruppo').value.trim();
  const annoPastorale = document.getElementById('catAnnoPastorale')?.value || '2026/2027';
  const stato = document.getElementById('catStatoGruppo')?.value || 'pubblico';
  const annoPercorso = document.getElementById('catAnnoPercorso').value.trim();
  const chks = document.querySelectorAll('.nuovo_cat_chk:checked');
  const catechistiIds = Array.from(chks).map(x => parseInt(x.value));
  const orario = document.getElementById('catOrario').value.trim();
  const aula = document.getElementById('catAula').value.trim();
  const googleCalendarUrl = (document.getElementById('catGoogleCalendarUrl')?.value || '').trim();
  const note = document.getElementById('catNote').value.trim();

  try {
    const res = await fetch('/api/catechismo/gruppi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome,
        anno_pastorale: annoPastorale,
        stato,
        anno_catechismo: annoPercorso,
        catechisti_ids: catechistiIds,
        orario_incontri: orario,
        aula,
        google_calendar_url: googleCalendarUrl,
        note
      })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalNuovoGruppoCatechismo');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= MODIFICA GRUPPO CATECHISMO =================
async function openModalModificaGruppoCatechismo(id) {
  const g = cacheGruppiCatechismo.find(x => x.id === id);
  if (!g) return;

  document.getElementById('modCatGruppoId').value = g.id;
  document.getElementById('modCatNomeGruppo').value = g.nome || '';
  document.getElementById('modCatAnnoPastorale').value = g.anno_pastorale || '2026/2027';
  if (document.getElementById('modCatStatoGruppo')) {
    document.getElementById('modCatStatoGruppo').value = g.stato || 'pubblico';
  }
  document.getElementById('modCatAnnoCatechismo').value = g.anno_catechismo || '';
  document.getElementById('modCatOrario').value = g.orario_incontri || '';
  document.getElementById('modCatAula').value = g.aula || '';
  if (document.getElementById('modCatGoogleCalendarUrl')) {
    document.getElementById('modCatGoogleCalendarUrl').value = g.google_calendar_url || '';
  }
  document.getElementById('modCatNote').value = g.note || '';

  // Popola selezione multipla catechisti con quelli già assegnati
  const selCatIds = g.catechisti_ids && g.catechisti_ids.length ? g.catechisti_ids : (g.catechista_utente_id ? [g.catechista_utente_id] : []);
  await loadCatechistiCheckboxes('modCatCatechistiContainer', selCatIds);

  // Popola selezione attività collegate
  try {
    const resAtt = await fetch('/api/attivita');
    const dataAtt = await resAtt.json();
    const attivitaList = dataAtt.attivita || [];
    const selAtt = document.getElementById('modCatAttivitaSelect');
    if (selAtt) {
      selAtt.innerHTML = '<option value="">-- Nessuna attività specifica collegata --</option>' + attivitaList.map(a => `
        <option value="${a.id}" ${g.attivita_id === a.id ? 'selected' : ''}>
          ${escapeHtml(a.titolo)} (${escapeHtml(a.categoria.toUpperCase())})
        </option>
      `).join('');
    }
  } catch (err) {
    console.error('Errore attivita select:', err);
  }

  openModal('modalModificaGruppoCatechismo');
}

async function handleSalvaModificaGruppoCatechismo(e) {
  e.preventDefault();
  const id = document.getElementById('modCatGruppoId').value;
  const nome = document.getElementById('modCatNomeGruppo').value.trim();
  const annoPastorale = document.getElementById('modCatAnnoPastorale').value;
  const stato = document.getElementById('modCatStatoGruppo')?.value || 'pubblico';
  const annoCatechismo = document.getElementById('modCatAnnoCatechismo').value.trim();
  const chks = document.querySelectorAll('.mod_cat_chk:checked');
  const catechistiIds = Array.from(chks).map(x => parseInt(x.value));
  const orario = document.getElementById('modCatOrario').value.trim();
  const aula = document.getElementById('modCatAula').value.trim();
  const googleCalendarUrl = (document.getElementById('modCatGoogleCalendarUrl')?.value || '').trim();
  const selAtt = document.getElementById('modCatAttivitaSelect');
  const attId = selAtt && selAtt.value ? parseInt(selAtt.value) : null;
  const note = document.getElementById('modCatNote').value.trim();

  try {
    const res = await fetch(`/api/catechismo/gruppi/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome,
        anno_pastorale: annoPastorale,
        stato,
        anno_catechismo: annoCatechismo,
        catechisti_ids: catechistiIds,
        orario_incontri: orario,
        aula,
        google_calendar_url: googleCalendarUrl,
        attivita_id: attId,
        note
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica gruppo');

    showToast(data.message || 'Gruppo aggiornato con successo!', 'success');
    closeModal('modalModificaGruppoCatechismo');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= STORICO INCONTRI & APPELLO =================
async function openModalStoricoIncontriCatechismo(id) {
  try {
    const res = await fetch(`/api/catechismo/gruppi/${id}/storico`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore recupero storico');

    const g = data.gruppo;
    document.getElementById('storicoGruppoNomeSubtitle').textContent = `${g.nome} · Anno ${g.anno_pastorale || '2025/2026'} · Catechista: ${g.catechista_nome || 'N/D'}`;
    const content = document.getElementById('storicoIncontriContent');

    const incontri = data.incontri || [];
    const stats = data.statistiche_ragazzi || [];

    content.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 20px;">
        <div style="background: var(--bg-subtle); padding: 12px; border-radius: 8px; text-align: center;">
          <span style="font-size: 11px; color: var(--ink-500); text-transform: uppercase;">Incontri Registrati</span>
          <strong style="display: block; font-size: 22px; color: var(--primary);">${data.totale_incontri || 0}</strong>
        </div>
        <div style="background: var(--bg-subtle); padding: 12px; border-radius: 8px; text-align: center;">
          <span style="font-size: 11px; color: var(--ink-500); text-transform: uppercase;">Ragazzi nel Gruppo</span>
          <strong style="display: block; font-size: 22px; color: var(--ink-900);">${g.totale_ragazzi || 0}</strong>
        </div>
      </div>

      <div style="margin-bottom: 24px;">
        <h4 style="font-size: 14.5px; font-weight: 700; margin-bottom: 10px; color: var(--ink-900);">📅 Diario degli Incontri Svolti</h4>
        ${!incontri.length ? `
          <div style="padding: 16px; background: var(--bg-subtle); border-radius: 8px; text-align: center; color: var(--ink-500); font-size: 13px;">
            Nessun incontro o appello ancora registrato per questo gruppo.
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 8px; max-height: 220px; overflow-y: auto;">
            ${incontri.map(inc => `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #fff; border: 1px solid var(--border-light); border-radius: 6px;">
                <div>
                  <strong style="font-size: 13.5px; color: var(--ink-900);">Data: ${escapeHtml(inc.data_it || inc.data)}</strong>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                  <span class="badge badge-success" style="font-size: 11px;">✓ ${inc.presenti_count} Presenti</span>
                  <span class="badge ${inc.assenti_count > 0 ? 'badge-danger' : 'badge-neutral'}" style="font-size: 11px;">✗ ${inc.assenti_count} Assenti</span>
                </div>
              </div>
            `).join('')}
          </div>
        `}
      </div>

      <div>
        <h4 style="font-size: 14.5px; font-weight: 700; margin-bottom: 10px; color: var(--ink-900);">📊 Riepilogo Presenze per Ragazzo</h4>
        ${!stats.length ? `
          <div style="padding: 16px; background: var(--bg-subtle); border-radius: 8px; text-align: center; color: var(--ink-500); font-size: 13px;">
            Nessun ragazzo iscritto a questo gruppo.
          </div>
        ` : `
          <div class="table-responsive" style="max-height: 250px; overflow-y: auto;">
            <table class="custom-table" style="font-size: 12.5px;">
              <thead>
                <tr>
                  <th>Ragazzo</th>
                  <th>Presenti</th>
                  <th>Assenti</th>
                  <th>% Presenza</th>
                </tr>
              </thead>
              <tbody>
                ${stats.map(s => `
                  <tr>
                    <td><strong>${escapeHtml(s.nominativo)}</strong> <small style="color:var(--ink-500);">(${s.eta ? `${s.eta}a` : s.codice_fiscale})</small></td>
                    <td><span style="color:#16a34a; font-weight:bold;">${s.presenti}</span> / ${s.totale_incontri}</td>
                    <td><span style="color:#dc2626; font-weight:bold;">${s.assenti}</span></td>
                    <td style="min-width: 120px;">
                      <div style="display:flex; align-items:center; gap:8px;">
                        <div style="flex:1; background:#e2e8f0; height:8px; border-radius:4px; overflow:hidden;">
                          <div style="width:${s.percentuale_presenza}%; background:${s.percentuale_presenza >= 75 ? '#16a34a' : (s.percentuale_presenza >= 50 ? '#f59e0b' : '#dc2626')}; height:100%;"></div>
                        </div>
                        <span style="font-weight:600; font-size:11.5px;">${s.percentuale_presenza}%</span>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;

    openModal('modalStoricoIncontriCatechismo');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= SCHEDA ALLERGIE, INTOLLERANZE & CONTATTI =================
let cacheAllergieGruppoData = null;

async function openModalAllergieGruppoCatechismo(id) {
  try {
    const res = await fetch(`/api/catechismo/gruppi/${id}/allergie`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore recupero scheda medica');

    cacheAllergieGruppoData = data;
    const g = data.gruppo;
    document.getElementById('allergieGruppoNomeSubtitle').textContent = `${g.nome} · Anno ${g.anno_pastorale || '2025/2026'} · Catechista: ${g.catechista_nome || 'N/D'}`;
    const content = document.getElementById('allergieGruppoContent');

    const ragazzi = data.ragazzi || [];
    const conSegnalazioni = data.ragazzi_con_segnalazioni || 0;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: ${conSegnalazioni > 0 ? '#fef3c7' : '#f0fdf4'}; border-radius: 8px; margin-bottom: 16px; border: 1px solid ${conSegnalazioni > 0 ? '#fde68a' : '#bbf7d0'};">
        <div>
          <strong style="color: ${conSegnalazioni > 0 ? '#92400e' : '#166534'}; font-size: 14px;">
            ${conSegnalazioni > 0 ? `⚠️ ${conSegnalazioni} ragazzi con allergie/intolleranze segnalate` : '✓ Nessuna allergia o intolleranza segnalata nel gruppo'}
          </strong>
          <small style="display: block; color: var(--ink-700); font-size: 12px;">Totale ragazzi iscritti al gruppo: ${data.totale_ragazzi}</small>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 12px; max-height: 400px; overflow-y: auto; padding-right: 4px;">
        ${!ragazzi.length ? `
          <div style="padding: 24px; text-align: center; color: var(--ink-500);">Nessun ragazzo ancora assegnato a questo gruppo.</div>
        ` : ragazzi.map(r => `
          <div style="padding: 14px; border-radius: 8px; border: 1px solid ${r.ha_segnalazione ? '#f59e0b' : 'var(--border-light)'}; background: ${r.ha_segnalazione ? '#fffbeb' : '#fff'};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <div>
                <strong style="font-size: 14.5px; color: var(--ink-900);">${escapeHtml(r.nominativo)}</strong>
                <span style="font-size: 12px; color: var(--ink-500); margin-left: 6px;">(${r.eta !== null ? `${r.eta} anni` : 'Età N/D'} · Sesso: ${r.sesso})</span>
              </div>
              ${r.ha_segnalazione ? `
                <span class="badge" style="background: #f59e0b; color: #fff; font-size: 11px;">ATTENZIONE MEDICA</span>
              ` : `
                <span class="badge badge-neutral" style="font-size: 11px;">Ordinario</span>
              `}
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 12.5px; margin-bottom: 8px;">
              <div>
                <span style="color: var(--ink-500); display: block;">Allergie:</span>
                <strong style="color: ${r.allergie ? '#b45309' : 'var(--ink-700)'};">${escapeHtml(r.allergie || 'Nessuna')}</strong>
              </div>
              <div>
                <span style="color: var(--ink-500); display: block;">Intolleranze Alimentari:</span>
                <strong style="color: ${r.intolleranze_alimentari ? '#b45309' : 'var(--ink-700)'};">${escapeHtml(r.intolleranze_alimentari || 'Nessuna')}</strong>
              </div>
            </div>

            ${r.note_mediche ? `
              <div style="font-size: 12px; background: rgba(0,0,0,0.03); padding: 6px 10px; border-radius: 4px; margin-bottom: 8px; color: var(--ink-800);">
                <strong>Note Sanitarie / Farmaci:</strong> ${escapeHtml(r.note_mediche)}
              </div>
            ` : ''}

            <div style="font-size: 12px; color: var(--ink-700); border-top: 1px dashed var(--border-light); padding-top: 8px; display: flex; flex-wrap: wrap; gap: 12px;">
              <div>👨‍👩‍👧 <strong>Famiglia:</strong> ${escapeHtml(r.famiglia_nome || 'N/D')} (${escapeHtml(r.capofamiglia_nome || 'Genitore')})</div>
              <div>📞 <strong>Emergenza:</strong> <a href="tel:${escapeHtml(r.telefono_famiglia || r.cellulare || '')}" style="color: var(--primary); font-weight: 700;">${escapeHtml(r.telefono_famiglia || r.cellulare || 'Non indicato')}</a></div>
              ${r.indirizzo ? `<div>📍 ${escapeHtml(r.indirizzo)}</div>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    `;

    openModal('modalAllergieGruppoCatechismo');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function stampaSchedaAllergieGruppo() {
  if (!cacheAllergieGruppoData) return;
  const d = cacheAllergieGruppoData;
  const g = d.gruppo;

  const w = window.open('', '_blank');
  w.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Scheda Allergie & Emergenza - ${escapeHtml(g.nome)}</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 12px; margin: 20px; color: #1e293b; }
        h1 { font-size: 18px; color: #800020; margin-bottom: 4px; }
        .subtitle { font-size: 12px; color: #64748b; margin-bottom: 16px; border-bottom: 2px solid #800020; padding-bottom: 6px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }
        th { background: #f8fafc; font-weight: bold; font-size: 11px; text-transform: uppercase; }
        .alert { background: #fef3c7; color: #92400e; font-weight: bold; }
        @media print {
          body { margin: 10mm; }
          button { display: none; }
        }
      </style>
    </head>
    <body>
      <h1>Parrocchia Sacro Cuore di Gesù - Asti</h1>
      <div class="subtitle">
        <strong>GRUPPO CATECHISMO: ${escapeHtml(g.nome)}</strong> (Anno Pastorale: ${escapeHtml(g.anno_pastorale || '2025/2026')})<br>
        Catechista: ${escapeHtml(g.catechista_nome || 'N/D')} · Aula: ${escapeHtml(g.aula || 'N/D')} · Data stampa: ${new Date().toLocaleDateString('it-IT')}
      </div>

      <table>
        <thead>
          <tr>
            <th style="width: 25%;">Ragazzo / Nascita</th>
            <th style="width: 20%;">Allergie</th>
            <th style="width: 20%;">Intolleranze</th>
            <th style="width: 35%;">Contatto Genitori / Telefono Emergenza</th>
          </tr>
        </thead>
        <tbody>
          ${(d.ragazzi || []).map(r => `
            <tr class="${r.ha_segnalazione ? 'alert' : ''}">
              <td>
                <strong>${escapeHtml(r.nominativo)}</strong><br>
                ${r.data_nascita_it || ''} (${r.eta !== null ? `${r.eta} anni` : ''})
              </td>
              <td>${escapeHtml(r.allergie || 'Nessuna')}</td>
              <td>${escapeHtml(r.intolleranze_alimentari || 'Nessuna')}</td>
              <td>
                <strong>${escapeHtml(r.capofamiglia_nome || r.famiglia_nome || 'Genitore')}</strong><br>
                Tel: <strong>${escapeHtml(r.telefono_famiglia || r.cellulare || 'N/D')}</strong><br>
                <small>${escapeHtml(r.indirizzo || '')}</small>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <script>
        window.onload = function() { window.print(); }
      </script>
    </body>
    </html>
  `);
  w.document.close();
}

async function openModalAssegnaRagazzoCatechismo(gruppoId, gruppoNome) {
  if (!gruppoNome) {
    const g = (cacheGruppiCatechismo || []).find(x => x.id === gruppoId);
    gruppoNome = g ? g.nome : '';
  }
  document.getElementById('assegnaCatGruppoId').value = gruppoId;
  document.getElementById('assegnaCatGruppoNome').textContent = `Gruppo: ${gruppoNome}`;

  const res = await fetch('/api/persone');
  const d = await res.json();
  const select = document.getElementById('selectRagazzoCatechismo');
  select.innerHTML = (d.persone || []).map(p => `
    <option value="${p.codice_fiscale}">${escapeHtml(p.nominativo)} (${p.eta !== null ? `${p.eta} anni` : ''} - ${p.codice_fiscale})</option>
  `).join('');

  openModal('modalAssegnaRagazzoCatechismo');
}

async function handleSalvaAssegnaRagazzo(e) {
  e.preventDefault();
  const gruppoId = document.getElementById('assegnaCatGruppoId').value;
  const cf = document.getElementById('selectRagazzoCatechismo').value;

  try {
    const res = await fetch(`/api/catechismo/gruppi/${gruppoId}/ragazzi`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalAssegnaRagazzoCatechismo');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rimuoviRagazzoDaGruppo(gruppoId, cf) {
  if (!confirm('Rimuovere questo ragazzo dal gruppo di catechismo?')) return;
  try {
    const res = await fetch(`/api/catechismo/gruppi/${gruppoId}/ragazzi/${cf}`, { method: 'DELETE' });
    const d = await res.json();
    showToast(d.message, 'success');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaGruppoCatechismo(id) {
  if (!confirm('Sei sicuro di voler eliminare questo gruppo di catechismo?')) return;
  try {
    const res = await fetch(`/api/catechismo/gruppi/${id}`, { method: 'DELETE' });
    const d = await res.json();
    showToast(d.message, 'success');
    await loadCatechismo();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= VIEW: DOPOSCUOLA (GRUPPI & REGISTRO ELETTRONICO) =================
let cacheGruppiDoposcuola = [];
let currentDoposcuolaAnnoFilter = '2026/2027';
let cacheRegistroDoposcuola = null;
let statoPresenzeCorrentiDoposcuola = {};

async function loadDoposcuola() {
  const roles = (currentUser && currentUser.tutti_i_ruoli) || [currentUser ? currentUser.ruolo : 'utente'];
  const isSupervisor = roles.some(r => ['admin', 'parroco', 'segreteria'].includes(r));
  const isStaffOrEducatore = isSupervisor || roles.some(r => ['educatore', 'oratorio', 'catechista'].includes(r));

  if (!isStaffOrEducatore) {
    const staffSec = document.getElementById('doposcuolaStaffSection');
    const staffActions = document.getElementById('doposcuolaStaffHeaderActions');
    const parentSec = document.getElementById('doposcuolaParentSection');
    if (staffSec) staffSec.style.display = 'none';
    if (staffActions) staffActions.style.display = 'none';
    if (parentSec) parentSec.style.display = 'block';
    const titleEl = document.getElementById('doposcuolaPageTitle');
    const descEl = document.getElementById('doposcuolaPageDesc');
    if (titleEl) titleEl.textContent = 'Doposcuola dei Tuoi Figli';
    if (descEl) descEl.textContent = 'Consulta il gruppo di studio pomeridiano, gli educatori di riferimento e le presenze dei tuoi figli.';
    await loadDoposcuolaParentView();
    return;
  }

  const staffSec = document.getElementById('doposcuolaStaffSection');
  const staffActions = document.getElementById('doposcuolaStaffHeaderActions');
  const parentSec = document.getElementById('doposcuolaParentSection');
  if (staffSec) staffSec.style.display = 'block';
  if (staffActions) staffActions.style.display = 'flex';
  if (parentSec) parentSec.style.display = 'none';
  const titleEl = document.getElementById('doposcuolaPageTitle');
  const descEl = document.getElementById('doposcuolaPageDesc');
  if (titleEl) titleEl.textContent = 'Doposcuola & Supporto allo Studio';
  if (descEl) descEl.textContent = 'Gruppi di studio pomeridiani, educatori e volontari, registro presenze elettronico e note sui ragazzi.';

  try {
    const res = await fetch('/api/doposcuola/gruppi');
    const data = await res.json();
    cacheGruppiDoposcuola = data.gruppi || [];
    renderGruppiDoposcuolaGrid();
  } catch (err) {
    console.error('Errore caricamento doposcuola:', err);
  }
}

async function loadDoposcuolaParentView() {
  const container = document.getElementById('doposcuolaParentContainer');
  if (!container) return;
  container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--ink-500);">Caricamento dati doposcuola dei tuoi figli...</div>';

  try {
    const res = await fetch('/api/doposcuola/miei-figli');
    const data = await res.json();
    if (!data.ha_famiglia || !data.figli || !data.figli.length) {
      container.innerHTML = `
        <div class="card" style="padding: 30px; text-align: center;">
          <h3 style="font-size: 16px; margin-bottom: 8px;">Nessun figlio registrato nel nucleo familiare</h3>
          <p style="color: var(--ink-500); font-size: 13.5px; margin-bottom: 16px;">
            Aggiungi i componenti della tua famiglia nella sezione "La Mia Famiglia" per poter visualizzare e gestire le iscrizioni al doposcuola.
          </p>
          <button class="btn btn-primary" onclick="navigateTo('famiglia')">Vai a La Mia Famiglia →</button>
        </div>
      `;
      return;
    }

    container.innerHTML = data.figli.map(figlio => {
      if (figlio.is_assegnato && figlio.gruppo) {
        const g = figlio.gruppo;
        const stats = figlio.statistiche || { totale_incontri: 0, presenti: 0, assenti: 0, percentuale: 0 };
        const presenze = figlio.storico_presenze || [];

        return `
          <div class="card" style="border-left: 4px solid #0284c7; padding: 22px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; border-bottom: 1px solid var(--border-light); padding-bottom: 14px;">
              <div>
                <span class="badge badge-success" style="font-size: 11px; margin-bottom: 6px;">ISCRITTO / ASSEGNATO</span>
                <h2 style="font-size: 20px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(figlio.nominativo)}</h2>
                <div style="font-size: 13px; color: var(--ink-600); margin-top: 4px;">
                  Età: <strong>${figlio.eta !== null ? figlio.eta + ' anni' : 'N/D'}</strong> · Data di Nascita: <strong>${figlio.data_nascita_it || 'N/D'}</strong> · CF: <code>${figlio.codice_fiscale}</code>
                </div>
              </div>
              <div style="text-align: right;">
                <span style="font-size: 13px; font-weight: 700; color: #0284c7; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 4px 10px;">
                  📚 ${escapeHtml(g.nome)} (${escapeHtml(g.anno_scolastico)})
                </span>
              </div>
            </div>

            <!-- Dettagli Doposcuola & Educatore -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px; background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md);">
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Educatore / Volontario</div>
                <div style="font-size: 13.5px; color: var(--ink-800); line-height: 1.5;">
                  <strong>${escapeHtml(g.educatore_nome || 'In assegnazione')}</strong>
                </div>
              </div>
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Giorni, Orario & Aula</div>
                <div style="font-size: 13.5px; color: var(--ink-800);">
                  🕒 <strong>${escapeHtml(g.giorni_orari || 'Pomeriggio')}</strong><br>
                  🏫 Aula: <strong>${escapeHtml(g.aula || 'Salone Studio')}</strong>
                </div>
              </div>
              <div>
                <div style="font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--ink-500); font-weight: 700; margin-bottom: 4px;">Informazioni Attività</div>
                <div style="font-size: 13.5px; color: var(--ink-800);">
                  <span class="badge badge-info" style="font-size: 11.5px;">${escapeHtml(g.fascia_eta || 'Tutte le età')}</span>
                  ${g.note ? `<div style="font-size: 12px; color: var(--ink-600); margin-top: 4px;">${escapeHtml(g.note)}</div>` : ''}
                </div>
              </div>
            </div>
          </div>
        `;
      } else {
        // Figlio non ancora iscritto al doposcuola
        return `
          <div class="card" style="border-left: 4px solid var(--accent-gold); padding: 22px;">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap;">
              <div>
                <span class="badge badge-warning" style="font-size: 11px; margin-bottom: 6px;">NON ISCRITTO AL DOPOSCUOLA</span>
                <h2 style="font-size: 19px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(figlio.nominativo)}</h2>
                <div style="font-size: 13px; color: var(--ink-600); margin-top: 4px;">
                  Età: <strong>${figlio.eta !== null ? figlio.eta + ' anni' : 'N/D'}</strong> · Data di Nascita: <strong>${figlio.data_nascita_it || 'N/D'}</strong>
                </div>
                <p style="font-size: 13px; color: var(--ink-700); margin: 8px 0 0;">
                  Questo fanciullo non risulta iscritto ad alcun gruppo di doposcuola o supporto allo studio.
                </p>
              </div>
              <div>
                <button class="btn btn-primary" onclick="openModalIscriviFiglioDoposcuola('${figlio.codice_fiscale}', '${escapeHtml(figlio.nominativo)}')">
                  + Iscrivi al Doposcuola
                </button>
              </div>
            </div>
          </div>
        `;
      }
    }).join('');
  } catch (err) {
    container.innerHTML = `<div style="color: var(--danger); padding: 20px;">Errore: ${escapeHtml(err.message)}</div>`;
  }
}

function selezionaAnnoDoposcuola(anno) {
  currentDoposcuolaAnnoFilter = anno;
  document.querySelectorAll('.dop-anno-btn').forEach(btn => {
    const text = btn.textContent.trim();
    if ((!anno && text === 'Tutti') || (anno && text.startsWith(anno))) {
      btn.className = 'btn btn-sm btn-primary dop-anno-btn active';
    } else {
      btn.className = 'btn btn-sm btn-secondary dop-anno-btn';
    }
  });
  renderGruppiDoposcuolaGrid();
}

function filtraGruppiDoposcuola() {
  renderGruppiDoposcuolaGrid();
}

function renderGruppiDoposcuolaGrid() {
  const container = document.getElementById('doposcuolaGruppiGrid');
  if (!container) return;

  const annoFilter = (currentDoposcuolaAnnoFilter || '').trim();
  const searchFilter = (document.getElementById('searchDoposcuolaGruppi')?.value || '').trim().toLowerCase();

  let items = cacheGruppiDoposcuola;

  if (annoFilter) {
    items = items.filter(g => (g.anno_scolastico || g.anno_pastorale || '2026/2027') === annoFilter);
  }

  if (searchFilter) {
    items = items.filter(g => 
      (g.nome || '').toLowerCase().includes(searchFilter) ||
      (g.educatore_nome || '').toLowerCase().includes(searchFilter) ||
      (g.aula || '').toLowerCase().includes(searchFilter) ||
      (g.fascia_eta || '').toLowerCase().includes(searchFilter)
    );
  }

  if (!items.length) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--ink-500); background: #fff; border-radius: var(--radius-lg); border: 1px solid var(--border-light);">
        Nessun gruppo di doposcuola trovato nell'anno o nella ricerca selezionata. Clicca "+ Crea Nuovo Gruppo Doposcuola" per aggiungere una classe.
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(g => {
    const badgeStato = g.stato === 'bozza'
      ? '<span class="badge" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; font-size:10.5px;">🔒 BOZZA</span>'
      : (g.stato === 'chiuso'
          ? '<span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecaca; font-size:10.5px;">🔴 CHIUSO</span>'
          : '<span class="badge" style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-size:10.5px;">🟢 PUBBLICO</span>');

    return `
    <div class="catechismo-card" style="border-top: 4px solid #d97706;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 700; color: var(--ink-900); margin: 0 0 4px 0;">${escapeHtml(g.nome)}</h3>
          <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
            <span class="badge badge-warning" style="font-size: 11px;">📁 ${escapeHtml(g.anno_scolastico || '2026/2027')}</span>
            ${badgeStato}
            <span style="font-size: 12px; color: #b45309; font-weight: 600;">${escapeHtml(g.fascia_eta || 'Tutte le classi')}</span>
          </div>
        </div>
        <span class="badge badge-info" style="font-size: 12px;">${g.totale_studenti || g.totale_ragazzi || 0} iscritti</span>
      </div>

      <div style="font-size: 12.5px; color: var(--ink-700); line-height: 1.5; background: var(--bg-subtle); padding: 10px; border-radius: var(--radius-md);">
        <div>👤 Educatore: <strong>${escapeHtml(g.educatore_nome || 'Da assegnare')}</strong></div>
        <div>🕒 Pomeriggi: <strong>${escapeHtml(g.giorni_orari || g.orario_incontri || 'Non specificato')}</strong></div>
        <div>📍 Aula: <strong>${escapeHtml(g.aula || 'Non specificata')}</strong></div>
        ${g.note ? `<div style="margin-top: 4px; font-style: italic; color: var(--ink-500);">📝 ${escapeHtml(g.note)}</div>` : ''}
      </div>

      <div style="flex: 1;">
        <strong style="font-size: 12px; text-transform: uppercase; color: var(--ink-500); display: block; margin-bottom: 6px;">Studenti nel Gruppo:</strong>
        ${g.studenti && g.studenti.length ? `
          <div style="display: flex; flex-direction: column; gap: 4px; max-height: 140px; overflow-y: auto;">
            ${g.studenti.map(r => `
              <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; padding: 4px 6px; background: #fff; border: 1px solid var(--border-light); border-radius: var(--radius-sm);">
                <span><strong>${escapeHtml(r.nominativo)}</strong> <small style="color:var(--ink-500);">(${r.eta !== null ? `${r.eta} anni` : r.codice_fiscale})</small></span>
                <button onclick="rimuoviStudenteDoposcuola(${g.id}, '${r.codice_fiscale}')" style="background:none; border:none; color:#dc2626; cursor:pointer; font-weight:bold; font-size:14px;" title="Rimuovi dal gruppo">×</button>
              </div>
            `).join('')}
          </div>
        ` : `<small style="color:var(--ink-500);">Nessuno studente iscritto a questo gruppo.</small>`}
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; border-top: 1px solid var(--border-light); padding-top: 10px;">
        <button class="btn btn-sm btn-primary" onclick="openModalAppelloDoposcuola(${g.id})" style="background: #d97706; border-color: #d97706;">
          📖 Appello & Registro
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalStoricoIncontriDoposcuola(${g.id})">
          📅 Storico Pomeriggi
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalAllergieGruppoDoposcuola(${g.id})" style="color: #b45309; border-color: #fde68a; background: #fffbeb;">
          ⚠️ Allergie & Note
        </button>
        <button class="btn btn-sm btn-secondary" onclick="openModalModificaGruppoDoposcuola(${g.id})">
          ✏️ Modifica
        </button>
      </div>

      <div style="display: flex; gap: 6px; margin-top: 6px;">
        <button class="btn btn-sm btn-secondary" style="flex: 1;" onclick="openModalAssegnaStudenteDoposcuola(${g.id})">
          + Iscrivi Studente
        </button>
        <button class="btn btn-sm btn-danger" onclick="eliminaGruppoDoposcuola(${g.id})" title="Elimina gruppo doposcuola">
          🗑️
        </button>
      </div>
    </div>
    `;
  }).join('');
}

async function loadEducatoriDoposcuolaSelect(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  try {
    const res = await fetch('/api/doposcuola/educatori');
    const data = await res.json();
    const educatori = data.educatori || [];
    if (!educatori.length) {
      sel.innerHTML = '<option value="">(Nessun educatore registrato)</option>';
    } else {
      sel.innerHTML = '<option value="">-- Seleziona Educatore / Volontario --</option>' + educatori.map(e => `
        <option value="${escapeHtml(e.nominativo)}" data-id="${e.id}" data-cf="${e.codice_fiscale || ''}">
          ${escapeHtml(e.nominativo)} (${escapeHtml(e.email)})
        </option>
      `).join('');
    }
  } catch (err) {
    console.error('Errore educatori doposcuola:', err);
  }
}

async function openModalNuovoGruppoDoposcuola() {
  document.getElementById('dopNomeGruppo').value = '';
  document.getElementById('dopFasciaEta').value = '';
  document.getElementById('dopAnnoScolastico').value = '2026/2027';
  if (document.getElementById('dopStatoGruppo')) document.getElementById('dopStatoGruppo').value = 'pubblico';
  document.getElementById('dopOrario').value = 'Lun, Mer, Ven 16:30 - 18:30';
  document.getElementById('dopAula').value = '';
  document.getElementById('dopNote').value = '';
  await loadEducatoriDoposcuolaSelect('dopSelectEducatore');
  openModal('modalNuovoGruppoDoposcuola');
}

async function handleSalvaGruppoDoposcuola(e) {
  e.preventDefault();
  const nome = document.getElementById('dopNomeGruppo').value.trim();
  const anno = document.getElementById('dopAnnoScolastico')?.value || '2026/2027';
  const stato = document.getElementById('dopStatoGruppo')?.value || 'pubblico';
  const fascia = document.getElementById('dopFasciaEta').value.trim();
  const sel = document.getElementById('dopSelectEducatore');
  const educatoreNome = sel ? sel.value.trim() : '';
  const selectedOpt = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
  const edId = selectedOpt ? selectedOpt.getAttribute('data-id') : null;
  const edCF = selectedOpt ? selectedOpt.getAttribute('data-cf') : null;
  const orario = document.getElementById('dopOrario').value.trim();
  const aula = document.getElementById('dopAula').value.trim();
  const note = document.getElementById('dopNote').value.trim();

  try {
    const res = await fetch('/api/doposcuola/gruppi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome,
        anno_scolastico: anno,
        stato,
        fascia_eta: fascia,
        educatore_nome: educatoreNome,
        educatore_cf: edCF,
        educatore_utente_id: edId ? parseInt(edId) : null,
        giorni_orari: orario,
        aula,
        note
      })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message || 'Gruppo doposcuola creato!', 'success');
    closeModal('modalNuovoGruppoDoposcuola');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalModificaGruppoDoposcuola(id) {
  const g = cacheGruppiDoposcuola.find(x => x.id === id);
  if (!g) return;

  document.getElementById('modDopGruppoId').value = g.id;
  document.getElementById('modDopNomeGruppo').value = g.nome || '';
  document.getElementById('modDopAnnoScolastico').value = g.anno_scolastico || '2026/2027';
  if (document.getElementById('modDopStatoGruppo')) {
    document.getElementById('modDopStatoGruppo').value = g.stato || 'pubblico';
  }
  document.getElementById('modDopFasciaEta').value = g.fascia_eta || '';
  document.getElementById('modDopOrario').value = g.giorni_orari || '';
  document.getElementById('modDopAula').value = g.aula || '';
  document.getElementById('modDopNote').value = g.note || '';

  await loadEducatoriDoposcuolaSelect('modDopEducatoreSelect');
  const sel = document.getElementById('modDopEducatoreSelect');
  if (sel && g.educatore_utente_id) {
    for (let opt of sel.options) {
      if (opt.getAttribute('data-id') == g.educatore_utente_id) {
        opt.selected = true;
        break;
      }
    }
  }

  openModal('modalModificaGruppoDoposcuola');
}

async function handleSalvaModificaGruppoDoposcuola(e) {
  e.preventDefault();
  const id = document.getElementById('modDopGruppoId').value;
  const nome = document.getElementById('modDopNomeGruppo').value.trim();
  const anno = document.getElementById('modDopAnnoScolastico').value;
  const stato = document.getElementById('modDopStatoGruppo')?.value || 'pubblico';
  const fascia = document.getElementById('modDopFasciaEta').value.trim();
  const sel = document.getElementById('modDopEducatoreSelect');
  const edNome = sel ? sel.value.trim() : '';
  const selectedOpt = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
  const edId = selectedOpt ? selectedOpt.getAttribute('data-id') : null;
  const edCF = selectedOpt ? selectedOpt.getAttribute('data-cf') : null;
  const orario = document.getElementById('modDopOrario').value.trim();
  const aula = document.getElementById('modDopAula').value.trim();
  const note = document.getElementById('modDopNote').value.trim();

  try {
    const res = await fetch(`/api/doposcuola/gruppi/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome,
        anno_scolastico: anno,
        stato,
        fascia_eta: fascia,
        educatore_nome: edNome,
        educatore_cf: edCF,
        educatore_utente_id: edId ? parseInt(edId) : null,
        giorni_orari: orario,
        aula,
        note
      })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message || 'Gruppo doposcuola aggiornato!', 'success');
    closeModal('modalModificaGruppoDoposcuola');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaGruppoDoposcuola(id) {
  if (!confirm('Sei sicuro di voler eliminare questo gruppo di doposcuola?')) return;
  try {
    const res = await fetch(`/api/doposcuola/gruppi/${id}`, { method: 'DELETE' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');
    showToast(d.message || 'Gruppo doposcuola eliminato', 'success');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// Registro Elettronico Doposcuola
async function openModalAppelloDoposcuola(gruppoId) {
  const g = cacheGruppiDoposcuola.find(x => x.id === gruppoId);
  if (!g) return;

  document.getElementById('appelloDopGruppoId').value = g.id;
  document.getElementById('appelloDopAttivitaId').value = g.attivita_id || g.id;
  document.getElementById('appelloDopGruppoNome').textContent = g.nome;
  document.getElementById('appelloDopGruppoDettaglio').textContent = 
    `Educatore: ${g.educatore_nome || 'Da assegnare'} · Anno: ${g.anno_scolastico || '2025/2026'} ${g.aula ? '· Aula: ' + g.aula : ''}`;

  const today = new Date().toISOString().split('T')[0];
  document.getElementById('appelloDopDataIncontro').value = today;

  openModal('modalAppelloDoposcuola');

  const bodyEl = document.getElementById('registroElettronicoDoposcuolaBody');
  bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--ink-500);">Caricamento registro doposcuola...</td></tr>`;

  try {
    const res = await fetch(`/api/doposcuola/gruppi/${gruppoId}/registro`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore');

    cacheRegistroDoposcuola = data;
    const statsBadge = document.getElementById('appelloDopStatsGruppo');
    if (statsBadge) {
      statsBadge.textContent = `${data.totale_date} pomeriggi registrati · ${data.studenti.length} iscritti`;
    }

    inizializzaStatoPresenzeDoposcuola();
    renderTabellaRegistroDoposcuola();
  } catch (err) {
    bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--crimson-600);">Errore: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function inizializzaStatoPresenzeDoposcuola() {
  statoPresenzeCorrentiDoposcuola = {};
  if (!cacheRegistroDoposcuola || !cacheRegistroDoposcuola.studenti) return;

  const dataSel = document.getElementById('appelloDopDataIncontro').value;
  cacheRegistroDoposcuola.studenti.forEach(s => {
    if (s.presenze_map && typeof s.presenze_map[dataSel] !== 'undefined') {
      statoPresenzeCorrentiDoposcuola[s.codice_fiscale] = s.presenze_map[dataSel];
    } else {
      statoPresenzeCorrentiDoposcuola[s.codice_fiscale] = true;
    }
  });
}

function impostaOggiDataDoposcuola() {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('appelloDopDataIncontro').value = today;
  onDataIncontroDoposcuolaChanged();
}

function onDataIncontroDoposcuolaChanged() {
  inizializzaStatoPresenzeDoposcuola();
  renderTabellaRegistroDoposcuola();
}

function segnaTuttiPresentiDoposcuola() {
  if (!cacheRegistroDoposcuola || !cacheRegistroDoposcuola.studenti) return;
  cacheRegistroDoposcuola.studenti.forEach(s => {
    statoPresenzeCorrentiDoposcuola[s.codice_fiscale] = true;
  });
  renderTabellaRegistroDoposcuola();
}

function segnaTuttiAssentiDoposcuola() {
  if (!cacheRegistroDoposcuola || !cacheRegistroDoposcuola.studenti) return;
  cacheRegistroDoposcuola.studenti.forEach(s => {
    statoPresenzeCorrentiDoposcuola[s.codice_fiscale] = false;
  });
  renderTabellaRegistroDoposcuola();
}

function togglePresenzaStudenteDoposcuola(cf, valore) {
  statoPresenzeCorrentiDoposcuola[cf] = valore;
  aggiornaRigaRegistroDoposcuola(cf);
  aggiornaConteggioLiveDoposcuola();
}

function aggiornaConteggioLiveDoposcuola() {
  const liveEl = document.getElementById('appelloDopConteggioLive');
  if (!liveEl || !cacheRegistroDoposcuola) return;

  const total = cacheRegistroDoposcuola.studenti.length;
  if (!total) {
    liveEl.textContent = '0 iscritti';
    return;
  }

  let presenti = 0;
  cacheRegistroDoposcuola.studenti.forEach(s => {
    if (statoPresenzeCorrentiDoposcuola[s.codice_fiscale]) presenti++;
  });
  const assenti = total - presenti;
  const perc = Math.round((presenti / total) * 100);
  liveEl.innerHTML = `<span style="color:#166534;">🟢 ${presenti} Presenti</span> · <span style="color:#991b1b;">🔴 ${assenti} Assenti</span> (${perc}%)`;
}

function aggiornaRigaRegistroDoposcuola(cf) {
  const btnPres = document.getElementById(`btn-pres-dop-${cf}`);
  const btnAss = document.getElementById(`btn-ass-dop-${cf}`);
  const isPresente = statoPresenzeCorrentiDoposcuola[cf] === true;

  if (btnPres && btnAss) {
    if (isPresente) {
      btnPres.className = 'btn btn-sm btn-success';
      btnPres.style.fontWeight = '700';
      btnAss.className = 'btn btn-sm btn-outline-danger';
      btnAss.style.fontWeight = 'normal';
    } else {
      btnPres.className = 'btn btn-sm btn-outline-success';
      btnPres.style.fontWeight = 'normal';
      btnAss.className = 'btn btn-sm btn-danger';
      btnAss.style.fontWeight = '700';
    }
  }
}

function renderTabellaRegistroDoposcuola() {
  const bodyEl = document.getElementById('registroElettronicoDoposcuolaBody');
  if (!bodyEl || !cacheRegistroDoposcuola) return;

  const studenti = cacheRegistroDoposcuola.studenti || [];
  const dateIncontri = cacheRegistroDoposcuola.date_incontri || [];
  const dataSel = document.getElementById('appelloDopDataIncontro').value;

  if (!studenti.length) {
    bodyEl.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 24px; color: var(--ink-500);">Nessuno studente iscritto in questo gruppo doposcuola.</td></tr>`;
    aggiornaConteggioLiveDoposcuola();
    return;
  }

  bodyEl.innerHTML = studenti.map((s, idx) => {
    const isPresente = statoPresenzeCorrentiDoposcuola[s.codice_fiscale] === true;

    // Storico pomeriggi passati
    let storicoHtml = '';
    const datePassate = dateIncontri.filter(d => d.data !== dataSel);
    if (!datePassate.length) {
      storicoHtml = '<span style="color:var(--ink-400); font-size:11.5px; font-style:italic;">Nessun altro pomeriggio registrato</span>';
    } else {
      storicoHtml = '<div style="display:flex; gap:4px; flex-wrap:wrap; align-items:center;">' +
        datePassate.slice(-6).map(d => {
          const pres = s.presenze_map ? s.presenze_map[d.data] : undefined;
          if (pres === true) {
            return `<span class="badge" style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; font-size:11px; padding:2px 6px;" title="${d.data_it}: Presente">✓ ${d.data_it.substring(0,5)}</span>`;
          } else if (pres === false) {
            return `<span class="badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fecaca; font-size:11px; padding:2px 6px;" title="${d.data_it}: Assente">✗ ${d.data_it.substring(0,5)}</span>`;
          } else {
            return `<span class="badge" style="background:#f1f5f9; color:#64748b; font-size:11px; padding:2px 6px;" title="${d.data_it}: Non iscritto">- ${d.data_it.substring(0,5)}</span>`;
          }
        }).join('') +
        '</div>';
    }

    const percColor = s.percentuale >= 75 ? '#10b981' : (s.percentuale >= 50 ? '#f59e0b' : '#ef4444');

    return `
      <tr style="border-bottom: 1px solid var(--border-light);">
        <td style="text-align: center; color: var(--ink-400); font-weight: 600; font-size: 12px;">${idx + 1}</td>
        <td>
          <div style="font-weight: 700; color: var(--ink-900); font-size: 13.5px;">${escapeHtml(s.nominativo)}</div>
          <div style="font-size: 11px; color: var(--ink-500);">${escapeHtml(s.codice_fiscale)}${s.eta !== null && s.eta !== undefined ? ` · ${s.eta} anni` : ''}</div>
        </td>
        <td style="text-align: center; background: #fffbeb; border-left: 2px solid #f59e0b; border-right: 2px solid #f59e0b; padding: 6px;">
          <div style="display: inline-flex; border-radius: var(--radius-sm); overflow: hidden; border: 1px solid var(--border-light); background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <button type="button" id="btn-pres-dop-${s.codice_fiscale}" class="btn btn-sm ${isPresente ? 'btn-success' : 'btn-outline-success'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${isPresente ? 'font-weight:700;' : ''}" onclick="togglePresenzaStudenteDoposcuola('${s.codice_fiscale}', true)">
              ✓ Presente
            </button>
            <button type="button" id="btn-ass-dop-${s.codice_fiscale}" class="btn btn-sm ${!isPresente ? 'btn-danger' : 'btn-outline-danger'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${!isPresente ? 'font-weight:700;' : ''}" onclick="togglePresenzaStudenteDoposcuola('${s.codice_fiscale}', false)">
              ✗ Assente
            </button>
          </div>
        </td>
        <td>
          ${storicoHtml}
        </td>
        <td style="text-align: center; font-size: 12.5px; font-weight: 600; color: var(--ink-700);">
          ${s.presenti} / ${s.totale_incontri}
        </td>
        <td style="text-align: center;">
          <div style="display: flex; flex-direction: column; align-items: center; gap: 3px;">
            <strong style="font-size: 12px; color: ${percColor};">${s.percentuale}%</strong>
            <div style="width: 48px; background: #e2e8f0; height: 5px; border-radius: 3px; overflow: hidden;">
              <div style="width: ${s.percentuale}%; background: ${percColor}; height: 100%;"></div>
            </div>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  aggiornaConteggioLiveDoposcuola();
}

async function handleSalvaAppelloDoposcuola(e) {
  e.preventDefault();
  const gruppoId = parseInt(document.getElementById('appelloDopGruppoId').value);
  const attivitaId = parseInt(document.getElementById('appelloDopAttivitaId').value);
  const data = document.getElementById('appelloDopDataIncontro').value;

  const presenze = Object.keys(statoPresenzeCorrentiDoposcuola).map(cf => ({
    codice_fiscale: cf,
    presente: statoPresenzeCorrentiDoposcuola[cf]
  }));

  const btnSalva = document.getElementById('btnSalvaRegistroDoposcuola');
  if (btnSalva) {
    btnSalva.disabled = true;
    btnSalva.textContent = 'Salvataggio in corso...';
  }

  try {
    const res = await fetch('/api/doposcuola/presenze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gruppo_id: gruppoId,
        attivita_id: attivitaId,
        data: data,
        presenze: presenze
      })
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || 'Errore salvataggio presenze');

    showToast(result.message || 'Presenze doposcuola registrate con successo!', 'success');
    closeModal('modalAppelloDoposcuola');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btnSalva) {
      btnSalva.disabled = false;
      btnSalva.textContent = '💾 Salva Registro Presenze';
    }
  }
}

async function openModalStoricoIncontriDoposcuola(id) {
  try {
    const res = await fetch(`/api/doposcuola/gruppi/${id}/storico`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore');

    const g = data.gruppo;
    document.getElementById('storicoDopGruppoNomeSubtitle').textContent = 
      `${g.nome} · ${data.totale_incontri} pomeriggi svolti`;

    const content = document.getElementById('storicoIncontriDopContent');
    const incontri = data.incontri || [];
    if (!incontri.length) {
      content.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--ink-500);">Nessun pomeriggio ancora registrato per questo gruppo.</div>';
    } else {
      content.innerHTML = incontri.map(inc => `
        <div style="background: var(--bg-subtle); padding: 12px 14px; border-radius: var(--radius-md); margin-bottom: 10px; border-left: 3px solid #d97706;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong>📅 ${inc.data_it}</strong>
            <span class="badge badge-info">${inc.presenti_count} presenti / ${inc.assenti_count} assenti</span>
          </div>
          <div style="font-size: 12px; color: var(--ink-600); display: flex; flex-wrap: wrap; gap: 6px;">
            ${(inc.dettaglio || []).map(d => `
              <span class="badge ${d.presente ? 'badge-success' : 'badge-danger'}" style="font-size: 11px;">
                ${d.presente ? '✓' : '✗'} ${escapeHtml(d.nominativo)}
              </span>
            `).join('')}
          </div>
        </div>
      `).join('');
    }

    openModal('modalStoricoIncontriDoposcuola');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalAllergieGruppoDoposcuola(id) {
  try {
    const res = await fetch(`/api/doposcuola/gruppi/${id}/allergie`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore');

    const g = data.gruppo;
    document.getElementById('allergieDopGruppoNomeSubtitle').textContent = 
      `${g.nome} · ${data.con_allergie_count} studenti con note o allergie`;

    const content = document.getElementById('allergieDopGruppoContent');
    const ragazzi = data.ragazzi || [];
    if (!ragazzi.length) {
      content.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--ink-500);">Nessuno studente iscritto a questo gruppo.</div>';
    } else {
      content.innerHTML = ragazzi.map(r => `
        <div style="background: ${r.ha_condizioni ? '#fffbeb' : '#fff'}; border: 1px solid ${r.ha_condizioni ? '#fde68a' : 'var(--border-light)'}; padding: 12px 14px; border-radius: var(--radius-md); margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: var(--ink-900); font-size: 14px;">${escapeHtml(r.nominativo)}</strong>
            <span class="badge ${r.ha_condizioni ? 'badge-warning' : 'badge-neutral'}">${r.ha_condizioni ? '⚠️ Note Mediche' : 'Ordinario'}</span>
          </div>
          <div style="font-size: 12.5px; margin-top: 4px; color: var(--ink-700);">
            ${r.allergie ? `<div>Allergie: <strong style="color: #b45309;">${escapeHtml(r.allergie)}</strong></div>` : ''}
            ${r.intolleranze_alimentari ? `<div>Intolleranze: <strong style="color: #b45309;">${escapeHtml(r.intolleranze_alimentari)}</strong></div>` : ''}
            ${r.note_mediche ? `<div>Note: <em>${escapeHtml(r.note_mediche)}</em></div>` : ''}
            ${r.telefono_genitore ? `<div style="margin-top: 4px; font-size: 12px; color: var(--ink-600);">📞 Genitore: ${escapeHtml(r.nominativo_genitore)} (${escapeHtml(r.telefono_genitore)})</div>` : ''}
          </div>
        </div>
      `).join('');
    }

    openModal('modalAllergieGruppoDoposcuola');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalAssegnaStudenteDoposcuola(gruppoId) {
  const g = cacheGruppiDoposcuola.find(x => x.id === gruppoId);
  document.getElementById('assDopGruppoId').value = gruppoId;
  document.getElementById('assDopGruppoNome').textContent = g ? g.nome : '';

  const res = await fetch('/api/persone');
  const d = await res.json();
  const select = document.getElementById('assDopSelectPersona');
  select.innerHTML = '<option value="">-- Seleziona Ragazzo/a dall\'Anagrafica --</option>' + (d.persone || []).map(p => `
    <option value="${p.codice_fiscale}">${escapeHtml(p.nominativo)} (${p.eta !== null ? `${p.eta} anni` : ''} - ${p.codice_fiscale})</option>
  `).join('');

  openModal('modalAssegnaStudenteDoposcuola');
}

async function handleSalvaAssegnaStudenteDoposcuola(e) {
  e.preventDefault();
  const gruppoId = document.getElementById('assDopGruppoId').value;
  const cf = document.getElementById('assDopSelectPersona').value;

  try {
    const res = await fetch(`/api/doposcuola/gruppi/${gruppoId}/studenti`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalAssegnaStudenteDoposcuola');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rimuoviStudenteDoposcuola(gruppoId, cf) {
  if (!confirm('Rimuovere questo studente dal gruppo doposcuola?')) return;
  try {
    const res = await fetch(`/api/doposcuola/gruppi/${gruppoId}/studenti/${cf}`, { method: 'DELETE' });
    const d = await res.json();
    showToast(d.message || 'Studente rimosso', 'success');
    await loadDoposcuola();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= VIEW 6: SEGRETERIA (TABS, LISTE, HOMEPAGE CUSTOMIZER) =================
async function loadSegreteria() {
  switchSegreteriaTab(currentSegTab);
}

function switchSegreteriaTab(tab) {
  currentSegTab = tab;
  document.getElementById('tabContentSegIscrizioni').style.display = tab === 'iscrizioni' ? 'block' : 'none';
  document.getElementById('tabContentSegListe').style.display = tab === 'liste' ? 'block' : 'none';
  const celEl = document.getElementById('tabContentSegCelebrazioni');
  if (celEl) celEl.style.display = tab === 'celebrazioni' ? 'block' : 'none';
  document.getElementById('tabContentSegHomepage').style.display = tab === 'homepage' ? 'block' : 'none';
  const confEl = document.getElementById('tabContentSegConfigurazioni');
  if (confEl) confEl.style.display = tab === 'configurazioni' ? 'block' : 'none';
  const campiEl = document.getElementById('tabContentSegCampiAccount');
  if (campiEl) campiEl.style.display = tab === 'campi_account' ? 'block' : 'none';

  document.getElementById('tabSegIscrizioniBtn').className = `btn btn-sm ${tab === 'iscrizioni' ? 'btn-primary active' : 'btn-secondary'}`;
  document.getElementById('tabSegListeBtn').className = `btn btn-sm ${tab === 'liste' ? 'btn-primary active' : 'btn-secondary'}`;
  const celBtn = document.getElementById('tabSegCelebrazioniBtn');
  if (celBtn) celBtn.className = `btn btn-sm ${tab === 'celebrazioni' ? 'btn-primary active' : 'btn-secondary'}`;
  document.getElementById('tabSegHomepageBtn').className = `btn btn-sm ${tab === 'homepage' ? 'btn-primary active' : 'btn-secondary'}`;
  const confBtn = document.getElementById('tabSegConfigurazioniBtn');
  if (confBtn) confBtn.className = `btn btn-sm ${tab === 'configurazioni' ? 'btn-primary active' : 'btn-secondary'}`;
  const campiBtn = document.getElementById('tabSegCampiAccountBtn');
  if (campiBtn) campiBtn.className = `btn btn-sm ${tab === 'campi_account' ? 'btn-primary active' : 'btn-secondary'}`;

  if (tab === 'iscrizioni') loadSegreteriaIscrizioni();
  if (tab === 'liste') loadSegreteriaListe();
  if (tab === 'celebrazioni') loadSegreteriaCelebrazioni();
  if (tab === 'homepage') {
    loadImpostazioniHomepage();
    loadSegreteriaEventi();
  }
  if (tab === 'configurazioni') loadConfigurazioniSegreteria();
  if (tab === 'campi_account') loadCampiAccountSegreteria();
}

async function loadSegreteriaIscrizioni() {
  try {
    const [statsRes, iscRes, attRes] = await Promise.all([
      fetch('/api/segreteria/stats'),
      fetch('/api/iscrizioni'),
      fetch('/api/attivita')
    ]);

    const stats = await statsRes.json();
    const iscData = await iscRes.json();
    const attData = await attRes.json();
    cacheIscrizioni = iscData.iscrizioni || [];

    // Popola il menu a tendina delle attività parrocchiali per il filtraggio
    const selAtt = document.getElementById('filterSegAttivita');
    if (selAtt) {
      const currentVal = selAtt.value;
      const attivitaList = attData.attivita || [];
      selAtt.innerHTML = '<option value="">-- Tutte le Attività Parrocchiali --</option>' + 
        attivitaList.map(a => `<option value="${escapeHtml(a.titolo)}">${escapeHtml(a.titolo)}</option>`).join('');
      if (currentVal) selAtt.value = currentVal;
    }

    aggiornaKPIeTabellaSegreteria(cacheIscrizioni);
  } catch (err) {
    console.error('Errore segreteria iscrizioni:', err);
  }
}

function aggiornaKPIeTabellaSegreteria(items) {
  const totDovuto = items.reduce((acc, x) => acc + (x.importo_dovuto || 0), 0);
  const totIncassato = items.reduce((acc, x) => acc + (x.importo_pagato || 0), 0);
  const totResiduo = Math.max(0, totDovuto - totIncassato);

  const dovEl = document.getElementById('segTotDovuto');
  const incEl = document.getElementById('segTotIncassato');
  const resEl = document.getElementById('segTotResiduo');
  if (dovEl) dovEl.textContent = `€ ${totDovuto.toFixed(2)}`;
  if (incEl) incEl.textContent = `€ ${totIncassato.toFixed(2)}`;
  if (resEl) resEl.textContent = `€ ${totResiduo.toFixed(2)}`;

  renderTableSegreteria(items);
}

let selectedSegIscrizioniIds = new Set();
let filteredSegIscrizioni = [];

function renderTableSegreteria(items) {
  filteredSegIscrizioni = items || [];
  const tbody = document.querySelector('#tableSegreteriaIscrizioni tbody');
  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--ink-500);">Nessuna iscrizione trovata con i filtri impostati.</td></tr>`;
    aggiornaBulkSegIscrizioniBar();
    return;
  }

  tbody.innerHTML = items.map(i => `
    <tr>
      <td style="text-align: center;">
        <input type="checkbox" class="seg-iscrizione-select-checkbox" data-id="${i.id}" ${selectedSegIscrizioniIds.has(i.id) ? 'checked' : ''} onchange="onSegIscrizioneSelectChange(${i.id}, this)">
      </td>
      <td><strong>${escapeHtml(i.partecipante_nome)}</strong></td>
      <td style="font-family:monospace; font-size:12px;">${escapeHtml(i.codice_fiscale_partecipante)}</td>
      <td><strong>${escapeHtml(i.attivita_titolo)}</strong></td>
      <td>${escapeHtml(i.nome_famiglia)}<br><small>📞 ${escapeHtml(i.telefono_contatto || 'N/D')}</small></td>
      <td><span class="badge badge-success">${escapeHtml(i.stato)}</span></td>
      <td><strong>€ ${i.importo_dovuto.toFixed(2)}</strong></td>
      <td>
        <span class="badge ${i.stato_pagamento === 'saldato' ? 'badge-success' : (i.stato_pagamento === 'acconto' ? 'badge-warning' : 'badge-danger')}">
          € ${i.importo_pagato.toFixed(2)} (${escapeHtml(i.stato_pagamento)})
        </span>
      </td>
      <td>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-sm btn-secondary" onclick="openModalRegistraPagamento(${i.id})">
            💶 Quota
          </button>
          <button class="btn btn-sm btn-secondary" onclick="apriRicevutaIscrizione(${i.id})">
            📄 Ricevuta
          </button>
        </div>
      </td>
    </tr>
  `).join('');

  aggiornaBulkSegIscrizioniBar();
}

function filtraTabellaSegreteria(text) {
  const textInput = document.getElementById('filterSegIscrizioni');
  const query = textInput ? textInput.value.toLowerCase().trim() : '';
  const selAtt = document.getElementById('filterSegAttivita');
  const selectedAtt = selAtt ? selAtt.value.trim() : '';
  const selPag = document.getElementById('filterSegStatoPagamento');
  const selectedPag = selPag ? selPag.value.trim() : '';

  const filtered = cacheIscrizioni.filter(i => {
    const matchText = !query || (
      (i.partecipante_nome && i.partecipante_nome.toLowerCase().includes(query)) ||
      (i.codice_fiscale_partecipante && i.codice_fiscale_partecipante.toLowerCase().includes(query)) ||
      (i.attivita_titolo && i.attivita_titolo.toLowerCase().includes(query))
    );
    const matchAtt = !selectedAtt || (i.attivita_titolo === selectedAtt);
    const matchPag = !selectedPag || (i.stato_pagamento === selectedPag);
    return matchText && matchAtt && matchPag;
  });

  const badge = document.getElementById('segIscrizioniBadge');
  if (badge) badge.textContent = `${filtered.length} iscrizioni`;

  aggiornaKPIeTabellaSegreteria(filtered);
}

function resetFiltriSegreteriaIscrizioni() {
  const textInput = document.getElementById('filterSegIscrizioni');
  if (textInput) textInput.value = '';
  const selAtt = document.getElementById('filterSegAttivita');
  if (selAtt) selAtt.value = '';
  const selPag = document.getElementById('filterSegStatoPagamento');
  if (selPag) selPag.value = '';
  filtraTabellaSegreteria();
}

function toggleSelectAllSegIscrizioni(masterCheckbox) {
  const isChecked = masterCheckbox.checked;
  filteredSegIscrizioni.forEach(i => {
    if (isChecked) {
      selectedSegIscrizioniIds.add(i.id);
    } else {
      selectedSegIscrizioniIds.delete(i.id);
    }
  });
  document.querySelectorAll('.seg-iscrizione-select-checkbox').forEach(cb => {
    cb.checked = isChecked;
  });
  aggiornaBulkSegIscrizioniBar();
}

function onSegIscrizioneSelectChange(id, cb) {
  if (cb.checked) {
    selectedSegIscrizioniIds.add(id);
  } else {
    selectedSegIscrizioniIds.delete(id);
  }
  aggiornaBulkSegIscrizioniBar();
}

function deselezionaTutteSegIscrizioni() {
  selectedSegIscrizioniIds.clear();
  const master = document.getElementById('selectAllSegIscrizioniCheckbox');
  if (master) master.checked = false;
  document.querySelectorAll('.seg-iscrizione-select-checkbox').forEach(cb => {
    cb.checked = false;
  });
  aggiornaBulkSegIscrizioniBar();
}

function aggiornaBulkSegIscrizioniBar() {
  const bar = document.getElementById('bulkSegIscrizioniBar');
  const countText = document.getElementById('bulkSegIscrizioniCountText');
  const master = document.getElementById('selectAllSegIscrizioniCheckbox');
  const count = selectedSegIscrizioniIds.size;

  if (master) {
    master.checked = filteredSegIscrizioni.length > 0 && filteredSegIscrizioni.every(i => selectedSegIscrizioniIds.has(i.id));
  }

  if (bar && countText) {
    if (count > 0) {
      bar.style.display = 'flex';
      countText.textContent = `${count} iscrizion${count === 1 ? 'e' : 'i'} selezionat${count === 1 ? 'a' : 'e'}`;
    } else {
      bar.style.display = 'none';
    }
  }
}

async function eseguiBulkPagamentoIscrizioni(nuovoStato) {
  const ids = Array.from(selectedSegIscrizioniIds);
  if (!ids.length) return;
  const statoLabel = nuovoStato === 'saldato' ? 'SALDATE (saldo azzerato)' : 'DA SALDARE';
  if (!confirm(`Confermi di voler impostare come ${statoLabel} le ${ids.length} iscrizioni selezionate?`)) {
    return;
  }
  try {
    const res = await fetch('/api/iscrizioni/bulk-pagamento', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, stato_pagamento: nuovoStato })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore aggiornamento quote');
    showNotification(data.message || 'Iscrizioni aggiornate con successo', 'success');
    selectedSegIscrizioniIds.clear();
    await loadSegreteriaIscrizioni();
  } catch (err) {
    showNotification(err.message, 'error');
  }
}

async function eseguiBulkDeleteIscrizioni() {
  const ids = Array.from(selectedSegIscrizioniIds);
  if (!ids.length) return;
  if (!confirm(`ATTENZIONE: Stai per eliminare definitivamente ${ids.length} iscrizioni selezionate. Continuare?`)) {
    return;
  }
  try {
    const res = await fetch('/api/iscrizioni/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione iscrizioni');
    showNotification(data.message || 'Iscrizioni eliminate con successo', 'success');
    selectedSegIscrizioniIds.clear();
    await loadSegreteriaIscrizioni();
  } catch (err) {
    showNotification(err.message, 'error');
  }
}

function filtraTabellaSegreteriaPerAttivita(attivitaTitolo) {
  filtraTabellaSegreteria();
}

// ---------------- LISTE SEGRETERIA (Multi-list membership) ----------------
async function loadSegreteriaListe() {
  try {
    const res = await fetch('/api/liste');
    const data = await res.json();
    cacheListe = data.liste || [];
    const grid = document.getElementById('segListeGrid');

    if (!cacheListe.length) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--ink-500); background: #fff; border-radius: var(--radius-md); border: 1px solid var(--border-light);">
          Nessuna lista creata. Puoi crearne una manualmente o generarla in automatico da un'attività parrocchiale!
        </div>
      `;
      document.getElementById('cardDettaglioLista').style.display = 'none';
      return;
    }

    grid.innerHTML = cacheListe.map(l => `
      <div class="list-card" style="border-left-color: ${l.colore}; cursor: pointer;" onclick="selezionaLista(${l.id})">
        <div>
          <div class="list-card-header">
            <h4>${escapeHtml(l.nome)}</h4>
            <span class="badge badge-info">${l.totale_iscritti} persone</span>
          </div>
          <p style="font-size: 12.5px; color: var(--ink-700); margin: 6px 0;">${escapeHtml(l.descrizione || 'Lista generale')}</p>
          ${l.attivita_titolo ? `<small style="color:var(--accent-gold); font-weight:600;">✦ Da attività: ${escapeHtml(l.attivita_titolo)}</small>` : ''}
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-light); padding-top: 8px;">
          <small style="color:var(--ink-500);">Creato il ${l.created_at}</small>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button class="btn btn-sm btn-secondary" style="padding: 2px 8px; font-size: 11px;" onclick="event.stopPropagation(); openModalModificaLista(${l.id})" title="Modifica Lista">✏️ Modifica</button>
            <button class="btn btn-sm btn-danger" style="padding: 2px 8px; font-size: 11px;" onclick="event.stopPropagation(); eliminaLista(${l.id})" title="Elimina Lista">🗑️</button>
            <span style="font-size: 12px; font-weight: 700; color: var(--primary); margin-left: 4px;">Apri →</span>
          </div>
        </div>
      </div>
    `).join('');

    if (selectedListaId) selezionaLista(selectedListaId);
  } catch (err) {
    console.error('Errore liste:', err);
  }
}

async function selezionaLista(id) {
  selectedListaId = id;
  try {
    const res = await fetch(`/api/liste/${id}`);
    const data = await res.json();
    const l = data.lista;
    if (!l) return;

    document.getElementById('cardDettaglioLista').style.display = 'block';
    document.getElementById('dettaglioListaTitolo').textContent = `Membri di: ${l.nome} (${l.totale_iscritti} persone)`;
    document.getElementById('dettaglioListaDesc').textContent = l.descrizione;
    document.getElementById('btnExportExcelLista').onclick = () => window.location.href = `/api/liste/${id}/export-excel`;
    document.getElementById('btnAddMembroLista').onclick = () => openModalAggiungiMembroLista(l.id, l.nome);

    const btnMod = document.getElementById('btnModificaLista');
    if (btnMod) btnMod.onclick = () => openModalModificaLista(id);
    const btnDel = document.getElementById('btnEliminaLista');
    if (btnDel) btnDel.onclick = () => eliminaLista(id);

    const tbody = document.querySelector('#tableMembriLista tbody');
    if (!l.membri || !l.membri.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--ink-500);">Nessun membro inserito in questa lista. Clicca "+ Aggiungi Persona".</td></tr>`;
      return;
    }

    tbody.innerHTML = l.membri.map(m => `
      <tr>
        <td><strong>${escapeHtml(m.nominativo)}</strong></td>
        <td style="font-family:monospace; font-size:12px;">${escapeHtml(m.codice_fiscale)}</td>
        <td>${m.eta !== null ? `${m.eta} anni` : '-'}</td>
        <td>${escapeHtml(m.nome_famiglia || '-')}</td>
        <td>📞 ${escapeHtml(m.telefono || '-')}<br><small>${escapeHtml(m.email || '')}</small></td>
        <td>${escapeHtml(m.allergie || m.intolleranze_alimentari || 'Nessuna')}</td>
        <td>
          <button class="btn btn-sm btn-danger" onclick="rimuoviMembroDaLista(${l.id}, '${m.codice_fiscale}')">Rimuovi</button>
        </td>
      </tr>
    `).join('');

    document.getElementById('cardDettaglioLista').scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    console.error('Errore apertura lista:', err);
  }
}

function openModalNuovaLista() {
  document.getElementById('listaNome').value = '';
  document.getElementById('listaDescrizione').value = '';
  document.getElementById('listaColore').value = '#8B1E1E';
  openModal('modalNuovaLista');
}

async function handleSalvaNuovaLista(e) {
  e.preventDefault();
  const nome = document.getElementById('listaNome').value.trim();
  const desc = document.getElementById('listaDescrizione').value.trim();
  const colore = document.getElementById('listaColore').value;

  try {
    const res = await fetch('/api/liste', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, descrizione: desc, colore })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalNuovaLista');
    await loadSegreteriaListe();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalModificaLista(id) {
  let l = (cacheListe || []).find(x => x.id === id);
  if (!l) {
    try {
      const res = await fetch(`/api/liste/${id}`);
      const data = await res.json();
      l = data.lista;
    } catch (e) { console.error(e); }
  }
  if (!l) return;

  document.getElementById('modListaId').value = l.id;
  document.getElementById('modListaNome').value = l.nome || '';
  document.getElementById('modListaDescrizione').value = l.descrizione || '';
  document.getElementById('modListaColore').value = l.colore || '#8B1E1E';
  openModal('modalModificaLista');
}

async function handleSalvaModificaLista(e) {
  e.preventDefault();
  const id = document.getElementById('modListaId').value;
  const nome = document.getElementById('modListaNome').value.trim();
  const desc = document.getElementById('modListaDescrizione').value.trim();
  const colore = document.getElementById('modListaColore').value;

  try {
    const res = await fetch(`/api/liste/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, descrizione: desc, colore })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message || 'Lista aggiornata con successo', 'success');
    closeModal('modalModificaLista');
    await loadSegreteriaListe();
    if (selectedListaId == id) {
      await selezionaLista(id);
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaLista(id) {
  if (!id) return;
  const l = (cacheListe || []).find(x => x.id === id);
  const nome = l ? l.nome : 'questa lista';
  if (!confirm(`Sei sicuro di voler eliminare definitivamente la lista "${nome}"?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/liste/${id}`, { method: 'DELETE' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message || 'Lista eliminata con successo', 'success');
    document.getElementById('cardDettaglioLista').style.display = 'none';
    selectedListaId = null;
    await loadSegreteriaListe();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalGeneraListaAttivita() {
  const res = await fetch('/api/attivita?include_bozze=true');
  const d = await res.json();
  const select = document.getElementById('selectAttivitaPerLista');
  select.innerHTML = (d.attivita || []).map(a => `
    <option value="${a.id}">${escapeHtml(a.titolo)} (${a.numero_iscritti} iscritti)</option>
  `).join('');
  document.getElementById('inputNomeListaGenerata').value = '';
  openModal('modalGeneraListaAttivita');
}

async function handleSalvaGeneraListaDaAttivita(e) {
  e.preventDefault();
  const attivitaId = document.getElementById('selectAttivitaPerLista').value;
  const nome = document.getElementById('inputNomeListaGenerata').value.trim();

  try {
    const res = await fetch('/api/liste/genera-da-attivita', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attivita_id: attivitaId, nome_lista: nome })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalGeneraListaAttivita');
    await loadSegreteriaListe();
    if (d.lista) selezionaLista(d.lista.id);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalAggiungiMembroLista(listaId, listaNome) {
  document.getElementById('aggiungiMembroListaId').value = listaId;
  document.getElementById('aggiungiMembroListaNome').textContent = `Aggiungi a: ${listaNome}`;

  const res = await fetch('/api/persone');
  const d = await res.json();
  const select = document.getElementById('selectPersonaPerLista');
  select.innerHTML = (d.persone || []).map(p => `
    <option value="${p.codice_fiscale}">${escapeHtml(p.nominativo)} (${p.codice_fiscale})</option>
  `).join('');

  openModal('modalAggiungiMembroLista');
}

async function handleSalvaMembroInLista(e) {
  e.preventDefault();
  const listaId = document.getElementById('aggiungiMembroListaId').value;
  const cf = document.getElementById('selectPersonaPerLista').value;

  try {
    const res = await fetch(`/api/liste/${listaId}/membri`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    closeModal('modalAggiungiMembroLista');
    await selezionaLista(listaId);
    await loadSegreteriaListe();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rimuoviMembroDaLista(listaId, cf) {
  if (!confirm('Rimuovere questa persona dalla lista?')) return;
  try {
    const res = await fetch(`/api/liste/${listaId}/membri/${cf}`, { method: 'DELETE' });
    const d = await res.json();
    showToast(d.message, 'success');
    await selezionaLista(listaId);
    await loadSegreteriaListe();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------------- HOMEPAGE CUSTOMIZER (Requirement 7) ----------------
async function loadImpostazioniHomepage() {
  try {
    const res = await fetch('/api/impostazioni/homepage');
    const d = await res.json();
    const imp = d.impostazioni || {};

    document.getElementById('toggleMesse').checked = imp.mostra_orari_messe;
    document.getElementById('toggleAttivita').checked = imp.mostra_attivita;
    document.getElementById('toggleAvvisi').checked = imp.mostra_avvisi;
    document.getElementById('toggleContatti').checked = imp.mostra_contatti;
    document.getElementById('toggleBanner').checked = imp.mostra_banner;
    document.getElementById('inputBannerTesto').value = imp.testo_banner || '';
    document.getElementById('inputHeroTitolo').value = imp.titolo_hero || '';
    document.getElementById('inputHeroSottotitolo').value = imp.sottotitolo_hero || '';
    document.getElementById('inputHeroDescrizione').value = imp.testo_benvenuto || '';

    // Campi Segreteria & Recapiti (Personalizzabili)
    if (document.getElementById('inputSegreteriaTitolo')) {
      document.getElementById('inputSegreteriaTitolo').value = imp.segreteria_titolo || 'Segreteria & Recapiti';
      document.getElementById('inputSegreteriaSottotitolo').value = imp.segreteria_sottotitolo || 'Siamo a tua disposizione per informazioni su catechesi, certificati e attività parrocchiali';
      document.getElementById('inputSegreteriaIndirizzo').value = imp.segreteria_indirizzo || 'Parrocchia Sacro Cuore di Gesù\nVia Pier Santi Mattarella 2, 14100 Asti (AT)';
      document.getElementById('inputSegreteriaTelefono').value = imp.segreteria_telefono || '0141 355150';
      document.getElementById('inputSegreteriaEmail').value = imp.segreteria_email || 'sacrocuoreasti@gmail.com';
      document.getElementById('inputSegreteriaOrari').value = imp.segreteria_orari || 'Martedì e Giovedì: 16:00 - 18:30\nSabato mattina: 09:30 - 11:30\nDomenica: dopo le Sante Messe';
    }

    // Campi Coordinate Offerte & Donazioni (IBAN e Satispay)
    if (document.getElementById('inputOfferteIban')) {
      document.getElementById('inputOfferteIban').value = imp.iban || 'IT60X0542811101000000123456';
      document.getElementById('inputOfferteSatispay').value = imp.satispay_url || 'https://tag.satispay.com/sacrocuoreasti';
      document.getElementById('inputOfferteIntestatario').value = imp.intestatario_offerte || 'Parrocchia Sacro Cuore di Gesù - Asti';
      document.getElementById('inputOfferteCausale').value = imp.causale_predefinita_offerte || 'Offerta liberale per le attività parrocchiali';
    }

    // Carica calendari Google della segreteria
    await loadSegreteriaCalendari();
  } catch (err) {
    console.error('Errore caricamento impostazioni:', err);
  }
}

async function salvaImpostazioniHomepage() {
  const payload = {
    mostra_orari_messe: document.getElementById('toggleMesse').checked,
    mostra_attivita: document.getElementById('toggleAttivita').checked,
    mostra_avvisi: document.getElementById('toggleAvvisi').checked,
    mostra_contatti: document.getElementById('toggleContatti').checked,
    mostra_banner: document.getElementById('toggleBanner').checked,
    testo_banner: document.getElementById('inputBannerTesto').value.trim(),
    titolo_hero: document.getElementById('inputHeroTitolo').value.trim(),
    sottotitolo_hero: document.getElementById('inputHeroSottotitolo').value.trim(),
    testo_benvenuto: document.getElementById('inputHeroDescrizione').value.trim()
  };

  if (document.getElementById('inputSegreteriaTitolo')) {
    payload.segreteria_titolo = document.getElementById('inputSegreteriaTitolo').value.trim();
    payload.segreteria_sottotitolo = document.getElementById('inputSegreteriaSottotitolo').value.trim();
    payload.segreteria_indirizzo = document.getElementById('inputSegreteriaIndirizzo').value.trim();
    payload.segreteria_telefono = document.getElementById('inputSegreteriaTelefono').value.trim();
    payload.segreteria_email = document.getElementById('inputSegreteriaEmail').value.trim();
    payload.segreteria_orari = document.getElementById('inputSegreteriaOrari').value.trim();
  }

  if (document.getElementById('inputOfferteIban')) {
    payload.iban = document.getElementById('inputOfferteIban').value.trim();
    payload.satispay_url = document.getElementById('inputOfferteSatispay').value.trim();
    payload.intestatario_offerte = document.getElementById('inputOfferteIntestatario').value.trim();
    payload.causale_predefinita_offerte = document.getElementById('inputOfferteCausale').value.trim();
  }

  try {
    const res = await fetch('/api/impostazioni/homepage', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------------- GESTIONE EVENTI & AVVISI (PUBBLICATI VS BOZZE) ----------------
let cacheEventiSegreteria = [];

async function loadSegreteriaEventi() {
  try {
    const res = await fetch('/api/impostazioni/eventi');
    const data = await res.json();
    cacheEventiSegreteria = data.eventi || [];
    const tbody = document.querySelector('#tableSegreteriaEventi tbody');

    if (!tbody) return;

    if (!cacheEventiSegreteria.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--ink-500);">Nessun evento o avviso parrocchiale presente. Clicca "+ Nuovo Evento / Avviso" per crearne uno.</td></tr>`;
      return;
    }

    tbody.innerHTML = cacheEventiSegreteria.map(ev => `
      <tr>
        <td>
          <span class="badge ${ev.is_pubblicato ? 'badge-published' : 'badge-draft'}">
            ${ev.is_pubblicato ? 'PUBBLICATO' : 'IN BOZZA'}
          </span>
        </td>
        <td><strong>${escapeHtml(ev.titolo)}</strong></td>
        <td><span class="badge badge-info">${escapeHtml((ev.categoria || 'evento').toUpperCase())}</span></td>
        <td>${ev.data_evento || '<span style="color:var(--ink-500);">Non specificata</span>'}</td>
        <td style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--ink-700);" title="${escapeHtml(ev.contenuto)}">
          ${escapeHtml(ev.contenuto)}
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-sm ${ev.is_pubblicato ? 'btn-secondary' : 'btn-success'}" onclick="togglePubblicazioneEvento(${ev.id})">
              ${ev.is_pubblicato ? 'Metti in Bozza' : 'Pubblica'}
            </button>
            <button class="btn btn-sm btn-danger" onclick="eliminaEvento(${ev.id})">
              Elimina
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Errore caricamento eventi segreteria:', err);
  }
}

function openModalNuovoEvento() {
  document.getElementById('eventoTitolo').value = '';
  document.getElementById('eventoCategoria').value = 'evento';
  document.getElementById('eventoData').value = '';
  document.getElementById('eventoContenuto').value = '';
  document.getElementById('eventoIsPubblicato').checked = true;
  openModal('modalNuovoEvento');
}

async function handleSalvaNuovoEvento(e) {
  e.preventDefault();
  const titolo = document.getElementById('eventoTitolo').value.trim();
  const categoria = document.getElementById('eventoCategoria').value;
  const data_evento = document.getElementById('eventoData').value || null;
  const contenuto = document.getElementById('eventoContenuto').value.trim();
  const is_pubblicato = document.getElementById('eventoIsPubblicato').checked;

  try {
    const res = await fetch('/api/impostazioni/eventi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titolo, categoria, data_evento, contenuto, is_pubblicato })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore salvataggio evento');

    showToast(d.message, 'success');
    closeModal('modalNuovoEvento');
    await loadSegreteriaEventi();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function togglePubblicazioneEvento(id) {
  try {
    const res = await fetch(`/api/impostazioni/eventi/${id}/toggle-pubblicazione`, { method: 'PUT' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    showToast(d.message, 'success');
    await loadSegreteriaEventi();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaEvento(id) {
  if (!confirm('Sei sicuro di voler eliminare questo evento/avviso?')) return;
  try {
    const res = await fetch(`/api/impostazioni/eventi/${id}`, { method: 'DELETE' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore eliminazione');

    showToast(d.message, 'success');
    await loadSegreteriaEventi();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= VIEW 7: ANAGRAFICA (FILTRI & AZIONI DI MASSA) =================
let selectedAnagraficaCFs = new Set();
let cacheAnagraficaPersone = [];
let cacheAnagraficaFiltrate = [];
let cacheFamiglieList = [];
let currentViewingPersonaCF = null;
let expandedFamiglieIds = new Set();

async function loadAnagrafica(q = '') {
  try {
    const urlP = q ? `/api/persone?q=${encodeURIComponent(q)}` : '/api/persone';
    const [resP, resL, resF] = await Promise.all([
      fetch(urlP),
      fetch('/api/liste'),
      fetch('/api/famiglie')
    ]);
    const dataP = await resP.json();
    const dataL = await resL.json();
    const dataF = await resF.json();

    cacheAnagraficaPersone = dataP.persone || [];
    cacheFamiglieList = dataF.famiglie || [];

    // Popola select liste per azioni di massa
    const selectListe = document.getElementById('bulkAnagraficaListaSelect');
    if (selectListe) {
      selectListe.innerHTML = '<option value="">-- Assegna a Lista --</option>' + 
        (dataL.liste || []).map(l => `<option value="${l.id}">${escapeHtml(l.nome)}</option>`).join('');
    }

    filtraAnagraficaLocale();
  } catch (err) {
    console.error('Errore anagrafica:', err);
  }
}

function filtraAnagraficaLocale() {
  const sesso = document.getElementById('filterAnagraficaSesso')?.value || '';
  const fasciaEta = document.getElementById('filterAnagraficaEta')?.value || '';
  const allergie = document.getElementById('filterAnagraficaAllergie')?.value || '';

  cacheAnagraficaFiltrate = cacheAnagraficaPersone.filter(p => {
    const matchSesso = !sesso || p.sesso === sesso;
    
    let matchEta = true;
    if (fasciaEta) {
      const eta = p.eta;
      if (eta === null) {
        matchEta = false;
      } else if (fasciaEta === 'bambini') {
        matchEta = eta >= 0 && eta <= 10;
      } else if (fasciaEta === 'ragazzi') {
        matchEta = eta >= 11 && eta <= 17;
      } else if (fasciaEta === 'giovani') {
        matchEta = eta >= 18 && eta <= 29;
      } else if (fasciaEta === 'adulti') {
        matchEta = eta >= 30 && eta <= 64;
      } else if (fasciaEta === 'anziani') {
        matchEta = eta >= 65;
      }
    }

    let matchAllergie = true;
    if (allergie === 'allergie') {
      matchAllergie = !!(p.allergie || p.intolleranze_alimentari);
    }

    return matchSesso && matchEta && matchAllergie;
  });

  const badge = document.getElementById('anagraficaCountBadge');
  if (badge) {
    badge.textContent = `${cacheAnagraficaFiltrate.length} di ${cacheAnagraficaPersone.length} parrocchiani`;
  }

  renderFamiglieAnagraficaTree(cacheAnagraficaFiltrate);
}

function renderFamiglieAnagraficaTree(items) {
  const container = document.getElementById('anagraficaFamiglieTreeContainer');
  if (!container) return;

  if (!items.length) {
    container.innerHTML = `
      <div style="padding: 40px; text-align: center; color: var(--ink-500); background: #fff; border-radius: var(--radius-lg); border: 1px solid var(--border-light);">
        Nessun parrocchiano trovato con i filtri correnti.
      </div>
    `;
    aggiornaBulkAnagraficaBar();
    return;
  }

  // Costruisci mappa dei nuclei familiari
  const famiglieMap = new Map();
  const senzaFamiglia = [];

  (cacheFamiglieList || []).forEach(f => {
    famiglieMap.set(f.id, {
      id: f.id,
      nome_famiglia: f.nome_famiglia,
      indirizzo: f.indirizzo,
      citta: f.citta,
      telefono_principale: f.telefono_principale,
      codice_fiscale_capofamiglia: f.codice_fiscale_capofamiglia,
      membri: []
    });
  });

  items.forEach(p => {
    if (p.nucleo_id && famiglieMap.has(p.nucleo_id)) {
      famiglieMap.get(p.nucleo_id).membri.push(p);
    } else if (p.nome_famiglia) {
      let found = null;
      for (let f of famiglieMap.values()) {
        if (f.nome_famiglia === p.nome_famiglia) {
          found = f;
          break;
        }
      }
      if (!found) {
        const fakeId = 'fam_' + p.nome_famiglia;
        found = {
          id: fakeId,
          nome_famiglia: p.nome_famiglia,
          indirizzo: p.indirizzo_residenza || '',
          citta: p.comune_residenza || 'Asti',
          telefono_principale: p.telefono || '',
          codice_fiscale_capofamiglia: p.cf_capofamiglia || '',
          membri: []
        };
        famiglieMap.set(fakeId, found);
      }
      found.membri.push(p);
    } else {
      senzaFamiglia.push(p);
    }
  });

  const famiglieAttive = Array.from(famiglieMap.values()).filter(f => f.membri.length > 0);

  const summaryEl = document.getElementById('anagraficaTreeSummary');
  if (summaryEl) {
    const totalFam = famiglieAttive.length + (senzaFamiglia.length ? 1 : 0);
    summaryEl.textContent = `${items.length} fedeli in ${totalFam} nuclei`;
  }

  let html = '';

  famiglieAttive.forEach(f => {
    const isCollapsed = !expandedFamiglieIds.has(String(f.id));
    const capofamiglia = f.membri.find(m => m.ruolo_famiglia === 'Capofamiglia' || (f.codice_fiscale_capofamiglia && m.codice_fiscale === f.codice_fiscale_capofamiglia));
    const capofamigliaNome = capofamiglia ? capofamiglia.nominativo : (f.codice_fiscale_capofamiglia || '');

    html += `
      <div class="famiglia-accordion-card" id="famiglia-card-${f.id}">
        <div class="famiglia-accordion-header" onclick="toggleFamigliaAccordion('${f.id}')">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="famiglia-chevron ${isCollapsed ? 'rotated' : ''}" id="famiglia-chevron-${f.id}">▼</span>
            <span style="font-size: 20px;">👨‍👩‍👧</span>
            <div>
              <strong style="font-size: 15.5px; color: var(--ink-900);">${escapeHtml(f.nome_famiglia)}</strong>
              <div style="font-size: 12px; color: var(--ink-500); margin-top: 2px;">
                ${f.indirizzo ? `📍 ${escapeHtml(f.indirizzo)}${f.citta ? `, ${escapeHtml(f.citta)}` : ''}` : '📍 Asti'}
                ${f.telefono_principale ? ` · 📞 ${escapeHtml(f.telefono_principale)}` : ''}
                ${capofamigliaNome ? ` · Capofamiglia: <strong>${escapeHtml(capofamigliaNome)}</strong>` : ''}
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge badge-info" style="font-size: 12px;">${f.membri.length} ${f.membri.length === 1 ? 'membro' : 'membri'}</span>
            <button type="button" class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); openModalNuovoMembroInFamiglia('${f.id}', '${escapeHtml(f.nome_famiglia)}')" title="Aggiungi nuovo membro a questa famiglia" style="font-size: 11.5px; padding: 3px 8px;">
              + Membro
            </button>
          </div>
        </div>

        <div class="famiglia-accordion-body ${isCollapsed ? 'collapsed' : ''}" id="famiglia-body-${f.id}">
          <div class="table-responsive">
            <table class="custom-table table-anagrafica-submenu">
              <thead>
                <tr>
                  <th style="width: 36px; text-align: center;"></th>
                  <th style="width: 170px;">Codice Fiscale</th>
                  <th>Nome</th>
                  <th>Cognome</th>
                  <th>Famiglia / Ruolo</th>
                  <th>Età / Sesso</th>
                  <th>Note Sanitarie</th>
                  <th style="text-align: right; width: 140px;">Scheda</th>
                </tr>
              </thead>
              <tbody>
                ${f.membri.map(p => renderMembroRow(p, f.nome_famiglia)).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  });

  if (senzaFamiglia.length) {
    const isCollapsed = !expandedFamiglieIds.has('senza_famiglia');
    html += `
      <div class="famiglia-accordion-card" id="famiglia-card-senza_famiglia">
        <div class="famiglia-accordion-header" onclick="toggleFamigliaAccordion('senza_famiglia')">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span class="famiglia-chevron ${isCollapsed ? 'rotated' : ''}" id="famiglia-chevron-senza_famiglia">▼</span>
            <span style="font-size: 20px;">👤</span>
            <div>
              <strong style="font-size: 15.5px; color: var(--ink-800);">Parrocchiani Singoli / Senza Nucleo Familiare</strong>
              <div style="font-size: 12px; color: var(--ink-500); margin-top: 2px;">
                Fedeli censiti non ancora associati ad un nucleo familiare
              </div>
            </div>
          </div>
          <span class="badge badge-neutral" style="font-size: 12px;">${senzaFamiglia.length} ${senzaFamiglia.length === 1 ? 'persona' : 'persone'}</span>
        </div>

        <div class="famiglia-accordion-body ${isCollapsed ? 'collapsed' : ''}" id="famiglia-body-senza_famiglia">
          <div class="table-responsive">
            <table class="custom-table table-anagrafica-submenu">
              <thead>
                <tr>
                  <th style="width: 36px; text-align: center;"></th>
                  <th style="width: 170px;">Codice Fiscale</th>
                  <th>Nome</th>
                  <th>Cognome</th>
                  <th>Famiglia / Ruolo</th>
                  <th>Età / Sesso</th>
                  <th>Note Sanitarie</th>
                  <th style="text-align: right; width: 140px;">Scheda</th>
                </tr>
              </thead>
              <tbody>
                ${senzaFamiglia.map(p => renderMembroRow(p, 'Senza Nucleo')).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }

  container.innerHTML = html;

  const masterCb = document.getElementById('selectAllAnagraficaCheckbox');
  if (masterCb) {
    masterCb.checked = items.length > 0 && items.every(p => selectedAnagraficaCFs.has(p.codice_fiscale));
    masterCb.indeterminate = items.some(p => selectedAnagraficaCFs.has(p.codice_fiscale)) && !masterCb.checked;
  }

  aggiornaBulkAnagraficaBar();
}

function renderMembroRow(p, fallbackFamiglia) {
  const isSelected = selectedAnagraficaCFs.has(p.codice_fiscale);
  const haSanitarie = !!(p.allergie || p.intolleranze_alimentari);
  const ruoloBadge = p.ruolo_famiglia || 'Componente';

  return `
    <tr style="${isSelected ? 'background-color: #fefce8;' : ''}">
      <td style="text-align: center;">
        <input type="checkbox" class="anagrafica-select-cb" value="${p.codice_fiscale}" ${isSelected ? 'checked' : ''} onchange="onAnagraficaSelectChange('${p.codice_fiscale}', this.checked)" title="Seleziona ${escapeHtml(p.nominativo)}">
      </td>
      <td style="font-family: monospace; font-weight: 700; color: var(--primary);">
        ${escapeHtml(p.codice_fiscale)}
      </td>
      <td>
        <span class="person-name-link" onclick="apriSchedaVisualizzazionePersona('${p.codice_fiscale}')" title="Clicca per visualizzare l'intera scheda anagrafica">
          ${escapeHtml(p.nome)} 🔍
        </span>
      </td>
      <td>
        <strong>${escapeHtml(p.cognome)}</strong>
      </td>
      <td>
        <span class="badge badge-neutral" style="font-size: 11px;">${escapeHtml(ruoloBadge)}</span>
        <small style="color: var(--ink-500); display: block; font-size: 10.5px;">${escapeHtml(p.nome_famiglia || fallbackFamiglia)}</small>
      </td>
      <td>
        ${p.sesso === 'M' ? '♂ M' : '♀ F'}, ${p.eta !== null ? `<strong>${p.eta}</strong>a` : '-'}
      </td>
      <td>
        ${haSanitarie ? `
          <span class="allergy-tag peanut" title="${escapeHtml(p.allergie || p.intolleranze_alimentari)}" style="cursor: pointer;" onclick="apriSchedaVisualizzazionePersona('${p.codice_fiscale}')">
            ⚠️ Sanitaria
          </span>
        ` : `<span style="color:#16a34a; font-size: 11px;">✓ Ordinario</span>`}
      </td>
      <td style="text-align: right;">
        <button class="btn btn-sm btn-secondary" onclick="apriSchedaVisualizzazionePersona('${p.codice_fiscale}')" title="Apri scheda persona">
          👁️ Scheda
        </button>
      </td>
    </tr>
  `;
}

let currentViewingPersonaId = null;

async function apriSchedaVisualizzazionePersona(cf) {
  try {
    const res = await fetch(`/api/persone/${cf}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore nel caricamento della persona');
    const p = data.persona;
    if (!p) return;

    currentViewingPersonaCF = p.codice_fiscale;
    currentViewingPersonaId = p.id;

    document.getElementById('viewSchedaNominativo').textContent = p.nominativo;
    document.getElementById('viewSchedaCF').textContent = p.codice_fiscale;
    document.getElementById('viewSchedaSessoEta').textContent = `${p.sesso === 'M' ? 'Maschio' : 'Femmina'} · ${p.eta !== null ? `${p.eta} anni` : 'Età N/D'}`;
    document.getElementById('viewSchedaFamigliaBadge').textContent = p.nome_famiglia ? `👨‍👩‍👧 ${p.nome_famiglia} (${p.ruolo_famiglia || 'Membro'})` : '👤 Senza Nucleo';

    const avatar = document.getElementById('viewSchedaAvatar');
    if (avatar) avatar.textContent = (p.nome ? p.nome[0] : 'P').toUpperCase();

    const alertBox = document.getElementById('viewSchedaAllergieAlert');
    const alertDetails = document.getElementById('viewSchedaAllergieDetails');
    if (p.allergie || p.intolleranze_alimentari || p.note_mediche) {
      alertBox.style.display = 'block';
      let msgs = [];
      if (p.allergie) msgs.push(`Allergie: <strong>${escapeHtml(p.allergie)}</strong>`);
      if (p.intolleranze_alimentari) msgs.push(`Intolleranze: <strong>${escapeHtml(p.intolleranze_alimentari)}</strong>`);
      if (p.note_mediche) msgs.push(`Note mediche/farmaci: <strong>${escapeHtml(p.note_mediche)}</strong>`);
      alertDetails.innerHTML = msgs.join(' · ');
    } else {
      alertBox.style.display = 'none';
    }

    document.getElementById('viewSchedaNome').textContent = p.nome || '-';
    document.getElementById('viewSchedaCognome').textContent = p.cognome || '-';
    document.getElementById('viewSchedaSesso').textContent = p.sesso === 'M' ? 'Maschile (M)' : 'Femminile (F)';
    document.getElementById('viewSchedaDataNascita').textContent = p.data_nascita_it || p.data_nascita || '-';
    document.getElementById('viewSchedaEta').textContent = p.eta !== null ? `${p.eta} anni` : '-';
    document.getElementById('viewSchedaComuneNascita').textContent = p.comune_nascita || '-';

    document.getElementById('viewSchedaFamigliaNome').textContent = p.nome_famiglia || 'Non assegnato';
    document.getElementById('viewSchedaRuoloFamiglia').textContent = p.ruolo_famiglia || 'Non specificato';
    document.getElementById('viewSchedaCapofamigliaCF').textContent = p.cf_capofamiglia || '-';
    document.getElementById('viewSchedaHasAccount').textContent = p.has_account ? '✓ Account attivo associato' : 'Nessun account collegato';

    document.getElementById('viewSchedaIndirizzo').textContent = p.indirizzo_residenza || '-';
    document.getElementById('viewSchedaComuneResidenza').textContent = p.comune_residenza || 'Asti';
    document.getElementById('viewSchedaTelefono').textContent = p.telefono || '-';
    document.getElementById('viewSchedaCellulare').textContent = p.cellulare || p.telefono || '-';
    document.getElementById('viewSchedaEmail').textContent = p.email || '-';

    const battEl = document.getElementById('viewSchedaBattesimo');
    if (p.certificato_battesimo_url) {
      battEl.innerHTML = `<a href="${p.certificato_battesimo_url}" target="_blank" style="color:var(--primary); font-weight:700;">📄 Visualizza / Scarica Certificato</a>`;
    } else {
      battEl.textContent = 'Non registrato o assente';
    }

    const listeBox = document.getElementById('viewSchedaListePills');
    const badges = p.badges || p.liste || [];
    if (badges.length) {
      listeBox.innerHTML = badges.map(l => `
        <span class="badge" style="background:${l.colore || '#8B1E1E'}; color:#fff; font-size:12px; padding:4px 8px; display:inline-flex; align-items:center; gap:4px;" title="${escapeHtml(l.descrizione || '')}">
          <span>${l.icona || '🏅'}</span> <strong>${escapeHtml(l.nome)}</strong>
        </span>
      `).join('');
    } else {
      listeBox.innerHTML = '<span style="color:var(--ink-500); font-size:12px;">Nessun badge assegnato</span>';
    }

    const noteEl = document.getElementById('viewSchedaNoteGenerali');
    if (noteEl) {
      noteEl.textContent = p.note_generali || 'Nessuna annotazione registrata.';
    }

    openModal('modalSchedaPersonaVisualizzazione');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function eseguiAzioneSchedaModifica() {
  if (!currentViewingPersonaCF) return;
  const cf = currentViewingPersonaCF;
  closeModal('modalSchedaPersonaVisualizzazione');
  openModalModificaPersona(cf);
}

function eseguiAzioneSchedaIscrivi() {
  if (!currentViewingPersonaCF) return;
  const cf = currentViewingPersonaCF;
  closeModal('modalSchedaPersonaVisualizzazione');
  openModalNuovaIscrizione(null, cf);
}

function eseguiAzioneSchedaElimina() {
  if (!currentViewingPersonaCF) return;
  const cf = currentViewingPersonaCF;
  closeModal('modalSchedaPersonaVisualizzazione');
  eliminaSingolaPersona(cf);
}

function toggleFamigliaAccordion(id) {
  const body = document.getElementById(`famiglia-body-${id}`);
  const chevron = document.getElementById(`famiglia-chevron-${id}`);
  if (!body) return;

  const strId = String(id);
  if (body.classList.contains('collapsed')) {
    body.classList.remove('collapsed');
    if (chevron) chevron.classList.remove('rotated');
    expandedFamiglieIds.add(strId);
  } else {
    body.classList.add('collapsed');
    if (chevron) chevron.classList.add('rotated');
    expandedFamiglieIds.delete(strId);
  }
}

function espandiTutteFamiglie() {
  document.querySelectorAll('.famiglia-accordion-body').forEach(b => {
    b.classList.remove('collapsed');
    const id = b.id.replace('famiglia-body-', '');
    expandedFamiglieIds.add(id);
  });
  document.querySelectorAll('.famiglia-chevron').forEach(c => c.classList.remove('rotated'));
}

function comprimiTutteFamiglie() {
  expandedFamiglieIds.clear();
  document.querySelectorAll('.famiglia-accordion-body').forEach(b => b.classList.add('collapsed'));
  document.querySelectorAll('.famiglia-chevron').forEach(c => c.classList.add('rotated'));
}

function openModalNuovoMembroInFamiglia(nucleoId, nomeFamiglia) {
  openModalNuovaPersona();
  const selNucleo = document.getElementById('personaNucleoSelect');
  if (selNucleo && nucleoId && !isNaN(nucleoId)) {
    selNucleo.value = nucleoId;
  }
}

function toggleSelectAllAnagrafica(masterCb) {
  if (masterCb.checked) {
    cacheAnagraficaFiltrate.forEach(p => selectedAnagraficaCFs.add(p.codice_fiscale));
  } else {
    cacheAnagraficaFiltrate.forEach(p => selectedAnagraficaCFs.delete(p.codice_fiscale));
  }
  renderFamiglieAnagraficaTree(cacheAnagraficaFiltrate);
}

function onAnagraficaSelectChange(cf, isChecked) {
  if (isChecked) {
    selectedAnagraficaCFs.add(cf);
  } else {
    selectedAnagraficaCFs.delete(cf);
  }
  renderFamiglieAnagraficaTree(cacheAnagraficaFiltrate);
}

function deselezionaTuttePersone() {
  selectedAnagraficaCFs.clear();
  renderFamiglieAnagraficaTree(cacheAnagraficaFiltrate);
}

function resetFiltriAnagrafica() {
  const q = document.getElementById('searchAnagraficaInput');
  const s = document.getElementById('filterAnagraficaSesso');
  const e = document.getElementById('filterAnagraficaEta');
  const a = document.getElementById('filterAnagraficaAllergie');
  if (q) q.value = '';
  if (s) s.value = '';
  if (e) e.value = '';
  if (a) a.value = '';
  loadAnagrafica();
}

function aggiornaBulkAnagraficaBar() {
  const bar = document.getElementById('bulkAnagraficaBar');
  const countText = document.getElementById('bulkAnagraficaCountText');
  if (!bar) return;

  if (selectedAnagraficaCFs.size > 0) {
    bar.style.display = 'flex';
    if (countText) {
      countText.textContent = `${selectedAnagraficaCFs.size} ${selectedAnagraficaCFs.size === 1 ? 'persona selezionata' : 'persone selezionate'}`;
    }
  } else {
    bar.style.display = 'none';
  }
}

async function eseguiBulkExportExcelPersone() {
  if (selectedAnagraficaCFs.size === 0) return;
  const cfList = Array.from(selectedAnagraficaCFs).join(',');
  window.location.href = `/api/excel/export-anagrafica?cfs=${encodeURIComponent(cfList)}`;
}

async function eseguiBulkAggiungiPersoneALista() {
  if (selectedAnagraficaCFs.size === 0) return;
  const select = document.getElementById('bulkAnagraficaListaSelect');
  const listaId = select ? select.value : '';
  if (!listaId) {
    showToast('Seleziona una lista parrocchiale dal menu', 'error');
    if (select) select.focus();
    return;
  }

  try {
    const res = await fetch('/api/persone/bulk-aggiungi-lista', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cfs: Array.from(selectedAnagraficaCFs),
        lista_id: parseInt(listaId)
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore associazione a lista');

    showToast(data.message, 'success');
    selectedAnagraficaCFs.clear();
    await loadAnagrafica();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eseguiBulkDeletePersone() {
  if (selectedAnagraficaCFs.size === 0) return;
  if (!confirm(`⚠️ ATTENZIONE: Sei sicuro di voler eliminare definitivamente le ${selectedAnagraficaCFs.size} persone selezionate dall'anagrafica parrocchiale?\nQuesta operazione non può essere annullata.`)) {
    return;
  }

  try {
    const res = await fetch('/api/persone/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cfs: Array.from(selectedAnagraficaCFs)
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione schede anagrafiche');

    showToast(data.message, 'success');
    selectedAnagraficaCFs.clear();
    await loadAnagrafica();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaSingolaPersona(cf) {
  const p = (cacheAnagraficaPersone || []).find(x => x.codice_fiscale === cf);
  const nome = p ? p.nominativo : cf;
  if (!confirm(`Sei sicuro di voler eliminare definitivamente la scheda di "${nome}" (${cf})?`)) return;

  try {
    const res = await fetch(`/api/persone/${encodeURIComponent(cf)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione persona');

    showToast(data.message || 'Persona eliminata con successo', 'success');
    selectedAnagraficaCFs.delete(cf);
    await loadAnagrafica();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function debounceSearchAnagrafica(val) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    loadAnagrafica(val);
  }, 250);
}

// ================= VIEW 9: UTENTI & RUOLI (ADMIN PANEL: FILTRI & AZIONI DI MASSA) =================
let selectedUtentiIds = new Set();
let cacheUtentiFiltrati = [];
let allRegisteredUsers = [];

async function loadUtenti() {
  try {
    const res = await fetch('/api/utenti');
    const data = await res.json();
    allRegisteredUsers = data.utenti || [];

    // Mostra SOLO gli utenti che possiedono privilegi/ruoli speciali (Admin, Segreteria, Parroco, Catechista, Oratorio)
    const staffRoles = ['admin', 'segreteria', 'parroco', 'catechista', 'oratorio'];
    cacheUtenti = allRegisteredUsers.filter(u => {
      const roles = u.tutti_i_ruoli || [u.ruolo];
      return roles.some(r => staffRoles.includes(r));
    });

    filtraUtenti();
  } catch (err) {
    console.error('Errore utenti:', err);
  }
}

function filtraUtenti() {
  const query = (document.getElementById('searchUtentiInput')?.value || '').toLowerCase().trim();
  const filtroRuolo = document.getElementById('filterUtentiRuolo')?.value || '';
  const filtroStato = document.getElementById('filterUtentiStato')?.value || '';

  cacheUtentiFiltrati = cacheUtenti.filter(u => {
    const matchText = !query || (
      (u.email && u.email.toLowerCase().includes(query)) ||
      (u.nominativo && u.nominativo.toLowerCase().includes(query)) ||
      (u.codice_fiscale && u.codice_fiscale.toLowerCase().includes(query))
    );
    const matchRuolo = !filtroRuolo || (
      u.ruolo === filtroRuolo || (u.tutti_i_ruoli || []).includes(filtroRuolo)
    );
    const matchStato = !filtroStato || (
      filtroStato === 'attivo' ? u.is_attivo : !u.is_attivo
    );
    return matchText && matchRuolo && matchStato;
  });

  const badge = document.getElementById('utentiCountBadge');
  if (badge) {
    badge.textContent = `${cacheUtentiFiltrati.length} autorizzati`;
  }

  renderTableUtenti(cacheUtentiFiltrati);
}

async function openModalAssegnaPermessiUtente(preselectedUserId = null) {
  try {
    if (!allRegisteredUsers.length) {
      const res = await fetch('/api/utenti');
      const data = await res.json();
      allRegisteredUsers = data.utenti || [];
    }

    const select = document.getElementById('assegnaPermessoSelectUtente');
    if (!select) return;

    select.innerHTML = '<option value="">-- Seleziona un utente / fedele registrato --</option>' +
      allRegisteredUsers.map(u => `
        <option value="${u.id}" ${preselectedUserId && parseInt(preselectedUserId) === u.id ? 'selected' : ''}>
          ${escapeHtml(u.email)} ${u.nominativo ? `(${escapeHtml(u.nominativo)})` : ''} - [Ruolo attuale: ${u.ruolo}]
        </option>
      `).join('');

    if (preselectedUserId) {
      onSelectUtenteForPermessi(preselectedUserId);
    } else {
      const detailsBox = document.getElementById('assegnaPermessoUserDetails');
      if (detailsBox) detailsBox.style.display = 'none';
      document.querySelectorAll('.chk-extra-perm').forEach(c => c.checked = false);
      const primSelect = document.getElementById('assegnaPermessoRuoloPrimario');
      if (primSelect) primSelect.value = 'catechista';
    }

    openModal('modalAssegnaPermessiUtente');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function onSelectUtenteForPermessi(userId) {
  const detailsBox = document.getElementById('assegnaPermessoUserDetails');
  if (!userId) {
    if (detailsBox) detailsBox.style.display = 'none';
    return;
  }
  const u = allRegisteredUsers.find(x => x.id === parseInt(userId));
  if (!u) return;

  if (detailsBox) {
    detailsBox.style.display = 'block';
    document.getElementById('assegnaPermessoUserEmail').textContent = `Account: ${u.email} (ID #${u.id})`;
    document.getElementById('assegnaPermessoUserExtra').textContent = `Nominativo: ${u.nominativo || 'N/D'} · CF: ${u.codice_fiscale || 'N/D'} · Ruoli attuali: ${(u.tutti_i_ruoli || [u.ruolo]).join(', ')}`;
  }

  const primarioSelect = document.getElementById('assegnaPermessoRuoloPrimario');
  if (['admin', 'segreteria', 'parroco', 'catechista', 'oratorio'].includes(u.ruolo)) {
    if (primarioSelect) primarioSelect.value = u.ruolo;
  } else {
    if (primarioSelect) primarioSelect.value = 'catechista';
  }

  const userRoles = new Set(u.tutti_i_ruoli || [u.ruolo]);
  document.querySelectorAll('.chk-extra-perm').forEach(chk => {
    chk.checked = userRoles.has(chk.value);
  });
}

async function handleSalvaAssegnaPermessiUtente(e) {
  e.preventDefault();
  const select = document.getElementById('assegnaPermessoSelectUtente');
  const userId = select.value;
  if (!userId) {
    showToast('Seleziona un utente prima di continuare', 'error');
    return;
  }

  const ruoloPrimario = document.getElementById('assegnaPermessoRuoloPrimario').value;
  const extraChks = document.querySelectorAll('.chk-extra-perm:checked');
  const privilegi = Array.from(extraChks).map(c => c.value);
  if (!privilegi.includes(ruoloPrimario)) {
    privilegi.push(ruoloPrimario);
  }

  try {
    const res = await fetch(`/api/utenti/${userId}/ruoli`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ruolo: ruoloPrimario,
        privilegi: privilegi
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio permessi');

    showToast(data.message || 'Permessi assegnati con successo!', 'success');
    closeModal('modalAssegnaPermessiUtente');
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderTableUtenti(items) {
  const tbody = document.querySelector('#tableUtentiRuoli tbody');
  if (!tbody) return;

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--ink-500);">Nessun utente corrisponde ai filtri impostati.</td></tr>`;
    aggiornaBulkUtentiBar();
    return;
  }

  tbody.innerHTML = items.map(u => {
    const isSelected = selectedUtentiIds.has(u.id);
    const isSelf = currentUser && currentUser.id === u.id;
    return `
      <tr style="${isSelected ? 'background-color: #f0f7ff;' : ''}">
        <td style="text-align: center;">
          <input type="checkbox" class="utente-select-cb" value="${u.id}" ${isSelected ? 'checked' : ''} onchange="onUtenteSelectChange(${u.id}, this.checked)" title="Seleziona utente ${escapeHtml(u.email)}">
        </td>
        <td><strong>${escapeHtml(u.email)}</strong> ${isSelf ? '<span class="badge badge-info" style="font-size:10px; margin-left:4px;">TU</span>' : ''}</td>
        <td>${escapeHtml(u.nominativo)}</td>
        <td style="font-family:monospace; font-size:12px;">${escapeHtml(u.codice_fiscale || '-')}</td>
        <td><span class="badge badge-info">${escapeHtml(u.ruolo.toUpperCase())}</span></td>
        <td>
          ${(u.tutti_i_ruoli || []).map(r => `<span class="badge badge-neutral" style="margin:1px;">${escapeHtml(r)}</span>`).join('')}
        </td>
        <td><span class="badge ${u.is_attivo ? 'badge-success' : 'badge-danger'}">${u.is_attivo ? 'Attivo' : 'Disattivato'}</span></td>
        <td>
          <div style="display:flex; gap:6px; flex-wrap:wrap;">
            <button class="btn btn-sm btn-secondary" onclick="openModalModificaRuoli(${u.id})" title="Modifica ruoli e privilegi">
              ⚙ Privilegi
            </button>
            <button class="btn btn-sm btn-secondary" title="Reimposta password account" onclick="openModalAdminResetPassword(${u.id})">
              🔑 Reset PW
            </button>
            <button class="btn btn-sm ${u.is_attivo ? 'btn-danger' : 'btn-success'}" onclick="toggleStatoUtente(${u.id})" title="${u.is_attivo ? 'Disattiva account' : 'Attiva account'}">
              ${u.is_attivo ? 'Disattiva' : 'Attiva'}
            </button>
            ${!isSelf ? `
              <button class="btn btn-sm btn-danger" onclick="eliminaSingoloUtente(${u.id})" title="Elimina definitivamente utente">
                🗑️
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Sincronizza master checkbox
  const masterCb = document.getElementById('selectAllUtentiCheckbox');
  if (masterCb) {
    masterCb.checked = items.length > 0 && items.every(u => selectedUtentiIds.has(u.id));
    masterCb.indeterminate = items.some(u => selectedUtentiIds.has(u.id)) && !masterCb.checked;
  }

  aggiornaBulkUtentiBar();
}

function toggleSelectAllUtenti(masterCb) {
  if (masterCb.checked) {
    cacheUtentiFiltrati.forEach(u => selectedUtentiIds.add(u.id));
  } else {
    cacheUtentiFiltrati.forEach(u => selectedUtentiIds.delete(u.id));
  }
  renderTableUtenti(cacheUtentiFiltrati);
}

function onUtenteSelectChange(id, isChecked) {
  if (isChecked) {
    selectedUtentiIds.add(id);
  } else {
    selectedUtentiIds.delete(id);
  }
  renderTableUtenti(cacheUtentiFiltrati);
}

function deselezionaTuttiUtenti() {
  selectedUtentiIds.clear();
  renderTableUtenti(cacheUtentiFiltrati);
}

function resetFiltriUtenti() {
  const q = document.getElementById('searchUtentiInput');
  const r = document.getElementById('filterUtentiRuolo');
  const s = document.getElementById('filterUtentiStato');
  if (q) q.value = '';
  if (r) r.value = '';
  if (s) s.value = '';
  filtraUtenti();
}

function aggiornaBulkUtentiBar() {
  const bar = document.getElementById('bulkUtentiBar');
  const countText = document.getElementById('bulkUtentiCountText');
  if (!bar) return;

  if (selectedUtentiIds.size > 0) {
    bar.style.display = 'flex';
    if (countText) {
      countText.textContent = `${selectedUtentiIds.size} ${selectedUtentiIds.size === 1 ? 'utente selezionato' : 'utenti selezionati'}`;
    }
  } else {
    bar.style.display = 'none';
  }
}

// ================= AZIONI DI MASSA (BULK ACTIONS) UTENTI =================
async function eseguiBulkStatoUtenti(nuovoStato) {
  if (selectedUtentiIds.size === 0) return;
  const azioneStr = nuovoStato ? 'attivare' : 'disattivare';
  if (!confirm(`Sei sicuro di voler ${azioneStr} ${selectedUtentiIds.size} utenti selezionati?`)) return;

  try {
    const res = await fetch('/api/utenti/bulk-stato', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids: Array.from(selectedUtentiIds),
        is_attivo: nuovoStato
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica di massa stato');

    showToast(data.message, 'success');
    selectedUtentiIds.clear();
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eseguiBulkPrivilegiUtenti(azione) {
  if (selectedUtentiIds.size === 0) return;
  const select = document.getElementById('bulkRuoloSelect');
  const ruolo = select ? select.value : '';
  if (!ruolo) {
    showToast('Seleziona un ruolo dal menu a tendina prima di confermare', 'error');
    if (select) select.focus();
    return;
  }

  const msgAzione = azione === 'aggiungi' ? `assegnare il privilegio "${ruolo}" a` : `rimuovere il privilegio "${ruolo}" da`;
  if (!confirm(`Sei sicuro di voler ${msgAzione} ${selectedUtentiIds.size} utenti selezionati?`)) return;

  try {
    const res = await fetch('/api/utenti/bulk-privilegi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids: Array.from(selectedUtentiIds),
        azione,
        ruolo
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore aggiornamento privilegi di massa');

    showToast(data.message, 'success');
    selectedUtentiIds.clear();
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eseguiBulkDeleteUtenti() {
  if (selectedUtentiIds.size === 0) return;
  if (!confirm(`⚠️ ATTENZIONE: Sei sicuro di voler eliminare definitivamente i ${selectedUtentiIds.size} utenti selezionati?\nI loro account e credenziali di accesso verranno eliminati. Questa operazione non può essere annullata.`)) {
    return;
  }

  try {
    const res = await fetch('/api/utenti/bulk-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids: Array.from(selectedUtentiIds)
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione utenti');

    showToast(data.message, 'success');
    selectedUtentiIds.clear();
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaSingoloUtente(id) {
  if (currentUser && currentUser.id === id) {
    showToast('Non puoi eliminare il tuo account mentre sei connesso', 'error');
    return;
  }
  const u = (cacheUtenti || []).find(x => x.id === id);
  const email = u ? u.email : `ID ${id}`;
  if (!confirm(`Sei sicuro di voler eliminare definitivamente l'account "${email}"?`)) return;

  try {
    const res = await fetch(`/api/utenti/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione utente');

    showToast(data.message, 'success');
    selectedUtentiIds.delete(id);
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openModalNuovoUtente() {
  document.getElementById('nuovoUtenteNome').value = '';
  document.getElementById('nuovoUtenteCognome').value = '';
  document.getElementById('nuovoUtenteCF').value = '';
  document.getElementById('nuovoUtenteEmail').value = '';
  generaPasswordCasuale('nuovoUtentePassword');
  document.getElementById('nuovoUtenteRuolo').value = 'utente';
  sincronizzaPrivilegiDaRuolo('utente');
  openModal('modalNuovoUtente');
}

function generaPasswordCasuale(targetId) {
  const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%';
  let pw = 'SC-';
  for (let i = 0; i < 6; i++) {
    pw += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  const el = document.getElementById(targetId);
  if (el) el.value = pw;
}

function sincronizzaPrivilegiDaRuolo(ruolo) {
  const allPrivs = ['utente', 'catechista', 'oratorio', 'segreteria', 'parroco', 'admin'];
  allPrivs.forEach(p => {
    const el = document.getElementById(`priv_${p}`);
    if (el) el.checked = false;
  });

  const baseEl = document.getElementById('priv_utente');
  if (baseEl) baseEl.checked = true;

  const targetEl = document.getElementById(`priv_${ruolo}`);
  if (targetEl) targetEl.checked = true;

  if (ruolo === 'admin') {
    allPrivs.forEach(p => {
      const el = document.getElementById(`priv_${p}`);
      if (el) el.checked = true;
    });
  }
}

async function handleSalvaNuovoUtente(e) {
  e.preventDefault();
  const nome = document.getElementById('nuovoUtenteNome').value.trim();
  const cognome = document.getElementById('nuovoUtenteCognome').value.trim();
  const cf = document.getElementById('nuovoUtenteCF').value.trim().toUpperCase();
  const email = document.getElementById('nuovoUtenteEmail').value.trim();
  const password = document.getElementById('nuovoUtentePassword').value.trim();
  const ruolo = document.getElementById('nuovoUtenteRuolo').value;

  const allPrivs = ['utente', 'catechista', 'oratorio', 'segreteria', 'parroco', 'admin'];
  const privilegi = allPrivs.filter(p => {
    const el = document.getElementById(`priv_${p}`);
    return el && el.checked;
  });
  if (!privilegi.includes(ruolo)) privilegi.push(ruolo);

  try {
    const res = await fetch('/api/utenti', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, cognome, codice_fiscale: cf, email, password, ruolo, privilegi })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore creazione utente');

    showToast(data.message, 'success');
    closeModal('modalNuovoUtente');
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openModalAdminResetPassword(userId, email) {
  if (!email) {
    const u = (cacheUtenti || []).find(x => x.id === userId);
    email = u ? u.email : '';
  }
  document.getElementById('resetPwUserId').value = userId;
  document.getElementById('resetPwUserEmail').textContent = email;
  document.getElementById('resetPwNuovaPassword').value = '';
  generaPasswordCasuale('resetPwNuovaPassword');
  openModal('modalAdminResetPassword');
}

async function handleConfermaResetPasswordAdmin(e) {
  e.preventDefault();
  const userId = document.getElementById('resetPwUserId').value;
  const nuovaPw = document.getElementById('resetPwNuovaPassword').value.trim();
  const inviaEmail = document.getElementById('resetPwInviaEmail').checked;

  try {
    const res = await fetch(`/api/utenti/${userId}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nuova_password: nuovaPw, invia_email: inviaEmail })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore reimpostazione password');

    showToast(data.message, 'success');
    closeModal('modalAdminResetPassword');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function toggleStatoUtente(id) {
  try {
    const res = await fetch(`/api/utenti/${id}/stato`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore cambio stato');
    showToast(data.message, 'success');
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= MODALS & ACTIONS (AGE CHECKS) =================
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('active');
  else console.warn('Modal not found:', id);
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('active');
  else console.warn('Modal not found:', id);
}

async function openModalAggiungiFiglio() {
  document.getElementById('membroNome').value = '';
  document.getElementById('membroCognome').value = currentUser && currentUser.persona ? currentUser.persona.cognome : '';
  document.getElementById('membroCF').value = '';
  document.getElementById('membroCFFeedback').textContent = '';
  if (document.getElementById('membroLuogoNascita')) document.getElementById('membroLuogoNascita').value = '';
  if (document.getElementById('membroIndirizzo')) document.getElementById('membroIndirizzo').value = '';
  document.getElementById('membroIntolleranze').value = '';
  document.getElementById('membroAllergie').value = '';
  await loadAllergieSuggerite();
  renderAllergyPills('membroAllergiePills', 'membroIntolleranze', 'membroAllergie');
  openModal('modalAggiungiFiglio');
}

async function handleSalvaNuovoMembro(e) {
  e.preventDefault();
  const nome = document.getElementById('membroNome').value.trim();
  const cognome = document.getElementById('membroCognome').value.trim();
  const cf = document.getElementById('membroCF').value.toUpperCase().trim();
  const sesso = document.getElementById('membroSesso').value;
  const dataNascita = document.getElementById('membroDataNascita').value;
  const luogoNascita = document.getElementById('membroLuogoNascita') ? document.getElementById('membroLuogoNascita').value.trim() : '';
  const indirizzo = document.getElementById('membroIndirizzo') ? document.getElementById('membroIndirizzo').value.trim() : '';
  const ruolo = document.getElementById('membroRuolo').value;
  const intolleranze = document.getElementById('membroIntolleranze').value.trim();
  const allergie = document.getElementById('membroAllergie').value.trim();

  const nucleoId = currentUser.nucleo_id || (currentUser.persona ? currentUser.persona.nucleo_id : null);
  if (!nucleoId) {
    showToast('Errore: nucleo familiare non identificato', 'error');
    return;
  }

  try {
    const res = await fetch(`/api/famiglie/${nucleoId}/membri`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome, cognome, codice_fiscale: cf, sesso, data_nascita: dataNascita,
        luogo_nascita: luogoNascita, indirizzo_residenza: indirizzo,
        ruolo_famiglia: ruolo, intolleranze_alimentari: intolleranze, allergie
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio membro');

    showToast(data.message, 'success');
    closeModal('modalAggiungiFiglio');
    await loadFamiglia();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------------- NUOVA ISCRIZIONE CON CONTROLLO RIGIDO ETÀ E CLAUSOLE ----------------
async function openModalNuovaIscrizione(defaultAttivitaId = null, defaultCF = null) {
  // Carica attività
  const isStaff = currentUser && (currentUser.tutti_i_ruoli || []).some(r => ['admin', 'segreteria', 'parroco'].includes(r));
  const resAtt = await fetch(isStaff ? '/api/attivita?include_bozze=true' : '/api/attivita');
  const dataAtt = await resAtt.json();
  cacheAttivita = dataAtt.attivita || [];

  const attSelect = document.getElementById('iscrizioneAttivitaSelect');
  attSelect.innerHTML = cacheAttivita.map(a => `
    <option value="${a.id}" data-quota="${a.quota_iscrizione}" data-min="${a.eta_min}" data-max="${a.eta_max}" ${defaultAttivitaId == a.id ? 'selected' : ''}>
      ${escapeHtml(a.titolo)} (Età: ${a.eta_min}-${a.eta_max} anni · € ${a.quota_iscrizione.toFixed(2)})
    </option>
  `).join('');

  // Carica partecipanti
  const partSelect = document.getElementById('iscrizionePartecipanteSelect');
  if (cacheMembriFamiglia.length) {
    partSelect.innerHTML = cacheMembriFamiglia.map(m => `
      <option value="${m.codice_fiscale}" data-eta="${m.eta !== null ? m.eta : ''}" data-nome="${escapeHtml(m.nominativo)}" ${defaultCF == m.codice_fiscale ? 'selected' : ''}>
        ${escapeHtml(m.nominativo)} (${m.eta !== null ? `${m.eta} anni` : 'Età N/D'} - ${m.codice_fiscale})
      </option>
    `).join('');
  } else {
    const resP = await fetch('/api/persone');
    const dataP = await resP.json();
    cacheTuttePersone = dataP.persone || [];
    partSelect.innerHTML = cacheTuttePersone.map(p => `
      <option value="${p.codice_fiscale}" data-eta="${p.eta !== null ? p.eta : ''}" data-nome="${escapeHtml(p.nominativo)}" ${defaultCF == p.codice_fiscale ? 'selected' : ''}>
        ${escapeHtml(p.nominativo)} (${p.eta !== null ? `${p.eta} anni` : 'Età N/D'} - ${p.codice_fiscale})
      </option>
    `).join('');
  }

  // Carica clausole dinamiche da Segreteria
  try {
    const resC = await fetch('/api/configurazioni/clausole');
    const dataC = await resC.json();
    const clausole = dataC.clausole || [];
    const container = document.getElementById('iscrizioneClausoleContainer');
    if (container) {
      if (!clausole.length) {
        container.innerHTML = '<span style="font-size:12px; color:var(--ink-500);">Nessuna clausola specifica configurata dalla segreteria.</span>';
      } else {
        container.innerHTML = clausole.map(c => `
          <label class="clause-card ${c.obbligatoria ? 'mandatory' : ''}">
            <input type="checkbox" class="clause-checkbox" data-id="${c.id}" data-req="${c.obbligatoria}" data-titolo="${escapeHtml(c.titolo)}" ${c.obbligatoria ? 'checked required' : ''}>
            <div style="flex: 1;">
              <div class="clause-meta">
                <strong>${escapeHtml(c.titolo)}</strong>
                ${c.obbligatoria ? '<span class="badge-clause-req">Obbligatoria</span>' : '<span class="badge-clause-opt">Facoltativa</span>'}
              </div>
              <p style="margin: 0; font-size: 12.5px; color: var(--ink-700);">${escapeHtml(c.testo)}</p>
            </div>
          </label>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Errore caricamento clausole iscrizione:', err);
  }

  onIscrizioneFormChange();
  openModal('modalNuovaIscrizione');
}

function onIscrizioneFormChange() {
  const attSelect = document.getElementById('iscrizioneAttivitaSelect');
  const partSelect = document.getElementById('iscrizionePartecipanteSelect');
  const warningEl = document.getElementById('iscrizioneAgeWarning');
  const btnSubmit = document.getElementById('btnConfermaIscrizione');

  const selectedAttOpt = attSelect.options[attSelect.selectedIndex];
  const selectedPartOpt = partSelect.options[partSelect.selectedIndex];

  if (!selectedAttOpt || !selectedPartOpt) return;

  const quota = parseFloat(selectedAttOpt.getAttribute('data-quota') || '0');
  const etaMin = parseInt(selectedAttOpt.getAttribute('data-min') || '0');
  const etaMax = parseInt(selectedAttOpt.getAttribute('data-max') || '99');

  document.getElementById('previewQuotaAttivita').textContent = `€ ${quota.toFixed(2)}`;
  document.getElementById('previewEtaAttivita').textContent = `${etaMin} - ${etaMax} anni`;

  // Render dinamico campi richiesti per questa specifica attività/evento
  const selAttId = parseInt(selectedAttOpt.value);
  const attObj = (cacheAttivita || []).find(a => a.id === selAttId);
  const campiSec = document.getElementById('iscrizioneCampiEventoSection');
  const campiCont = document.getElementById('iscrizioneCampiEventoContainer');

  if (campiSec && campiCont) {
    let campiList = attObj ? attObj.campi_personalizzati : [];
    if (typeof campiList === 'string') {
      try { campiList = JSON.parse(campiList); } catch(e) { campiList = []; }
    }
    if (Array.isArray(campiList) && campiList.length > 0) {
      campiSec.style.display = 'block';
      campiCont.innerHTML = campiList.map(c => {
        const reqAttr = c.obbligatorio ? 'required' : '';
        const reqStar = c.obbligatorio ? '<span style="color:var(--crimson-600); font-weight:bold;">*</span>' : '';
        const fieldKey = c.chiave || c.nome.toLowerCase().replace(/[^a-z0-9_]/g, '_');
        let inputHtml = '';

        if (c.tipo === 'checkbox') {
          inputHtml = `
            <label style="display:inline-flex; align-items:center; gap:8px; cursor:pointer; font-size:13px; font-weight:600;">
              <input type="checkbox" class="campo-evento-input" data-key="${fieldKey}" data-label="${escapeHtml(c.nome)}" data-req="${c.obbligatorio ? 'true' : 'false'}">
              <span>${escapeHtml(c.nome)} ${reqStar}</span>
            </label>
          `;
        } else if (c.tipo === 'select') {
          const optItems = (c.opzioni || '').split(',').map(x => x.trim()).filter(Boolean);
          inputHtml = `
            <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">${escapeHtml(c.nome)} ${reqStar}</label>
            <select class="form-control form-control-sm campo-evento-input" data-key="${fieldKey}" data-label="${escapeHtml(c.nome)}" data-req="${c.obbligatorio ? 'true' : 'false'}" ${reqAttr}>
              <option value="">-- Seleziona un'opzione --</option>
              ${optItems.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('')}
            </select>
          `;
        } else if (c.tipo === 'numero') {
          inputHtml = `
            <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">${escapeHtml(c.nome)} ${reqStar}</label>
            <input type="number" class="form-control form-control-sm campo-evento-input" data-key="${fieldKey}" data-label="${escapeHtml(c.nome)}" data-req="${c.obbligatorio ? 'true' : 'false'}" placeholder="${escapeHtml(c.nome)}" ${reqAttr}>
          `;
        } else if (c.tipo === 'data') {
          inputHtml = `
            <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">${escapeHtml(c.nome)} ${reqStar}</label>
            <input type="date" class="form-control form-control-sm campo-evento-input" data-key="${fieldKey}" data-label="${escapeHtml(c.nome)}" data-req="${c.obbligatorio ? 'true' : 'false'}" ${reqAttr}>
          `;
        } else {
          inputHtml = `
            <label style="font-size:12px; font-weight:600; display:block; margin-bottom:4px;">${escapeHtml(c.nome)} ${reqStar}</label>
            <input type="text" class="form-control form-control-sm campo-evento-input" data-key="${fieldKey}" data-label="${escapeHtml(c.nome)}" data-req="${c.obbligatorio ? 'true' : 'false'}" placeholder="${escapeHtml(c.nome)}" ${reqAttr}>
          `;
        }

        return `<div class="form-group" style="margin-bottom:8px;">${inputHtml}</div>`;
      }).join('');
    } else {
      campiSec.style.display = 'none';
      campiCont.innerHTML = '';
    }
  }

  const partEtaRaw = selectedPartOpt.getAttribute('data-eta');
  const partNome = selectedPartOpt.getAttribute('data-nome');

  if (partEtaRaw !== '' && !isNaN(parseInt(partEtaRaw))) {
    const eta = parseInt(partEtaRaw);
    if (eta < etaMin) {
      warningEl.style.display = 'flex';
      warningEl.innerHTML = `⚠️ <strong>Età non idonea:</strong> ${partNome} ha <strong>${eta} anni</strong>, ma questa attività richiede un'età minima di <strong>${etaMin} anni</strong>. Iscrizione non consentita.`;
      btnSubmit.disabled = true;
      btnSubmit.style.opacity = '0.5';
      return;
    } else if (eta > etaMax) {
      warningEl.style.display = 'flex';
      warningEl.innerHTML = `⚠️ <strong>Età non idonea:</strong> ${partNome} ha <strong>${eta} anni</strong>, ma questa attività è riservata fino a <strong>${etaMax} anni</strong> (es. bambini/ragazzi). Iscrizione non consentita.`;
      btnSubmit.disabled = true;
      btnSubmit.style.opacity = '0.5';
      return;
    }
  }

  // Idoneo
  warningEl.style.display = 'none';
  btnSubmit.disabled = false;
  btnSubmit.style.opacity = '1';
}

async function handleSalvaIscrizione(e) {
  e.preventDefault();
  const attivitaId = parseInt(document.getElementById('iscrizioneAttivitaSelect').value);
  const cf = document.getElementById('iscrizionePartecipanteSelect').value;
  const note = document.getElementById('iscrizioneNote').value.trim();

  // Validazione clausole
  const clauseCheckboxes = document.querySelectorAll('#iscrizioneClausoleContainer .clause-checkbox');
  const clausoleAccettate = {};
  for (const chk of clauseCheckboxes) {
    const id = chk.getAttribute('data-id');
    const isReq = chk.getAttribute('data-req') === 'true';
    const titolo = chk.getAttribute('data-titolo') || 'Clausola';
    if (isReq && !chk.checked) {
      showToast(`Attenzione: devi accettare la clausola obbligatoria: "${titolo}"`, 'error');
      return;
    }
    clausoleAccettate[id] = chk.checked;
  }

  // Raccogli e valida campi personalizzati specifici per questa attività
  const campiEventoInputs = document.querySelectorAll('#iscrizioneCampiEventoContainer .campo-evento-input');
  const campiPersonalizzatiValori = {};
  for (const input of campiEventoInputs) {
    const key = input.getAttribute('data-key');
    const label = input.getAttribute('data-label') || key;
    const isReq = input.getAttribute('data-req') === 'true';
    let val = '';
    if (input.type === 'checkbox') {
      val = input.checked;
      if (isReq && !val) {
        showToast(`Attenzione: devi compilare o accettare il campo: "${label}"`, 'error');
        return;
      }
    } else {
      val = input.value.trim();
      if (isReq && !val) {
        showToast(`Attenzione: il campo "${label}" è obbligatorio`, 'error');
        return;
      }
    }
    campiPersonalizzatiValori[key] = val;
  }

  try {
    const res = await fetch('/api/iscrizioni', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        attivita_id: attivitaId,
        codice_fiscale_partecipante: cf,
        note_iscrizione: note,
        clausole_accettate: clausoleAccettate,
        campi_personalizzati: campiPersonalizzatiValori,
        consenso_privacy: true
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio iscrizione');

    showToast(data.message, 'success');
    closeModal('modalNuovaIscrizione');

    if (currentView === 'famiglia') await loadFamiglia();
    if (currentView === 'segreteria') await loadSegreteriaIscrizioni();
    if (currentView === 'dashboard') await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ---------------- GESTIONE CAMPI PERSONALIZZATI PER ATTIVITÀ/EVENTO ----------------
let campiPersonalizzatiNuovaAttivita = [];
let campiPersonalizzatiModAttivita = [];

function renderCampiPersonalizzatiNuovaAttivita() {
  const container = document.getElementById('nuovaAttCampiPersonalizzatiList');
  if (!container) return;
  if (!campiPersonalizzatiNuovaAttivita.length) {
    container.innerHTML = '<span style="font-size: 12px; color: var(--ink-500); font-style: italic;">Nessun campo aggiuntivo richiesto configurato per questo evento.</span>';
    return;
  }
  container.innerHTML = campiPersonalizzatiNuovaAttivita.map((c, idx) => `
    <div style="display: flex; justify-content: space-between; align-items: center; background: #fff; border: 1px solid var(--border-light); padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;">
      <div>
        <strong>${escapeHtml(c.nome)}</strong> 
        <span class="badge badge-info" style="font-size: 11px; margin-left: 6px;">${escapeHtml(c.tipo)}</span>
        ${c.obbligatorio ? '<span class="badge badge-published" style="font-size: 10px; margin-left: 4px;">OBBLIGATORIO</span>' : '<span style="font-size: 11px; color: var(--ink-500); margin-left: 4px;">(Opzionale)</span>'}
        ${c.opzioni ? `<div style="font-size: 11.5px; color: var(--ink-600); margin-top: 2px;">Opzioni: <em>${escapeHtml(c.opzioni)}</em></div>` : ''}
      </div>
      <button type="button" class="btn btn-sm btn-secondary" style="color: #dc2626; font-size: 12px; padding: 2px 8px;" onclick="rimuoviCampoPersonalizzatoNuovaAttivita(${idx})">Elimina</button>
    </div>
  `).join('');
}

function aggiungiCampoPersonalizzatoNuovaAttivita() {
  const nome = (document.getElementById('nuovaAttCampoNome')?.value || '').trim();
  const tipo = document.getElementById('nuovaAttCampoTipo')?.value || 'testo';
  const obbligatorio = document.getElementById('nuovaAttCampoObbligatorio')?.value === 'true';
  const opzioni = (document.getElementById('nuovaAttCampoOpzioni')?.value || '').trim();

  if (!nome) {
    showToast('Inserisci un nome per il campo richiesto', 'warning');
    return;
  }

  const chiave = nome.toLowerCase().replace(/[^a-z0-9_]/g, '_');
  campiPersonalizzatiNuovaAttivita.push({
    id: Date.now(),
    nome: nome,
    chiave: chiave,
    tipo: tipo,
    obbligatorio: obbligatorio,
    opzioni: opzioni
  });

  document.getElementById('nuovaAttCampoNome').value = '';
  document.getElementById('nuovaAttCampoOpzioni').value = '';
  renderCampiPersonalizzatiNuovaAttivita();
}

function rimuoviCampoPersonalizzatoNuovaAttivita(idx) {
  campiPersonalizzatiNuovaAttivita.splice(idx, 1);
  renderCampiPersonalizzatiNuovaAttivita();
}

function renderCampiPersonalizzatiModAttivita() {
  const container = document.getElementById('modAttCampiPersonalizzatiList');
  if (!container) return;
  if (!campiPersonalizzatiModAttivita.length) {
    container.innerHTML = '<span style="font-size: 12px; color: var(--ink-500); font-style: italic;">Nessun campo aggiuntivo richiesto configurato per questo evento.</span>';
    return;
  }
  container.innerHTML = campiPersonalizzatiModAttivita.map((c, idx) => `
    <div style="display: flex; justify-content: space-between; align-items: center; background: #fff; border: 1px solid var(--border-light); padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;">
      <div>
        <strong>${escapeHtml(c.nome)}</strong> 
        <span class="badge badge-info" style="font-size: 11px; margin-left: 6px;">${escapeHtml(c.tipo)}</span>
        ${c.obbligatorio ? '<span class="badge badge-published" style="font-size: 10px; margin-left: 4px;">OBBLIGATORIO</span>' : '<span style="font-size: 11px; color: var(--ink-500); margin-left: 4px;">(Opzionale)</span>'}
        ${c.opzioni ? `<div style="font-size: 11.5px; color: var(--ink-600); margin-top: 2px;">Opzioni: <em>${escapeHtml(c.opzioni)}</em></div>` : ''}
      </div>
      <button type="button" class="btn btn-sm btn-secondary" style="color: #dc2626; font-size: 12px; padding: 2px 8px;" onclick="rimuoviCampoPersonalizzatoModAttivita(${idx})">Elimina</button>
    </div>
  `).join('');
}

function aggiungiCampoPersonalizzatoModAttivita() {
  const nome = (document.getElementById('modAttCampoNome')?.value || '').trim();
  const tipo = document.getElementById('modAttCampoTipo')?.value || 'testo';
  const obbligatorio = document.getElementById('modAttCampoObbligatorio')?.value === 'true';
  const opzioni = (document.getElementById('modAttCampoOpzioni')?.value || '').trim();

  if (!nome) {
    showToast('Inserisci un nome per il campo richiesto', 'warning');
    return;
  }

  const chiave = nome.toLowerCase().replace(/[^a-z0-9_]/g, '_');
  campiPersonalizzatiModAttivita.push({
    id: Date.now(),
    nome: nome,
    chiave: chiave,
    tipo: tipo,
    obbligatorio: obbligatorio,
    opzioni: opzioni
  });

  document.getElementById('modAttCampoNome').value = '';
  document.getElementById('modAttCampoOpzioni').value = '';
  renderCampiPersonalizzatiModAttivita();
}

function rimuoviCampoPersonalizzatoModAttivita(idx) {
  campiPersonalizzatiModAttivita.splice(idx, 1);
  renderCampiPersonalizzatiModAttivita();
}

// ---------------- CREA ATTIVITÀ ----------------
async function openModalNuovaAttivita() {
  document.getElementById('attTitolo').value = '';
  await populateCategoriaSelects();
  document.getElementById('attPubblicato').value = 'true';
  document.getElementById('attEtaMin').value = '6';
  document.getElementById('attEtaMax').value = '14';
  document.getElementById('attQuota').value = '0.0';
  document.getElementById('attPosti').value = '';
  document.getElementById('attDataInizio').value = '';
  document.getElementById('attDataFine').value = '';
  document.getElementById('attDescrizione').value = '';
  const locInput = document.getElementById('attLocandinaInput');
  if (locInput) locInput.value = '';

  campiPersonalizzatiNuovaAttivita = [];
  renderCampiPersonalizzatiNuovaAttivita();

  openModal('modalNuovaAttivita');
}

async function handleSalvaNuovaAttivita(e) {
  e.preventDefault();
  const titolo = document.getElementById('attTitolo').value.trim();
  const categoria = document.getElementById('attCategoria').value;
  const isPubblicato = document.getElementById('attPubblicato').value === 'true';
  const etaMin = parseInt(document.getElementById('attEtaMin').value);
  const etaMax = parseInt(document.getElementById('attEtaMax').value);
  const quota = parseFloat(document.getElementById('attQuota').value || '0');
  const posti = document.getElementById('attPosti').value ? parseInt(document.getElementById('attPosti').value) : null;
  const inizio = document.getElementById('attDataInizio').value;
  const fine = document.getElementById('attDataFine').value;
  const desc = document.getElementById('attDescrizione').value.trim();

  try {
    const res = await fetch('/api/attivita', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        titolo, categoria, is_pubblicato: isPubblicato, eta_min: etaMin, eta_max: etaMax,
        quota_iscrizione: quota, posti_massimi: posti, data_inizio: inizio, data_fine: fine,
        descrizione: desc,
        campi_personalizzati: campiPersonalizzatiNuovaAttivita
      })
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore');

    // Se è stata caricata la locandina, inviala subito
    const locInput = document.getElementById('attLocandinaInput');
    if (locInput && locInput.files && locInput.files[0] && d.attivita && d.attivita.id) {
      const fd = new FormData();
      fd.append('locandina', locInput.files[0]);
      await fetch(`/api/attivita/${d.attivita.id}/locandina`, {
        method: 'POST',
        body: fd
      });
    }

    showToast(d.message, 'success');
    closeModal('modalNuovaAttivita');
    await loadAttivita();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openModalRegistraPagamento(iscrizioneId, dovuta, pagata, nome) {
  if (dovuta === undefined || pagata === undefined || !nome) {
    const isc = (cacheIscrizioni || []).find(x => x.id === iscrizioneId);
    if (isc) {
      dovuta = isc.importo_dovuto || 0;
      pagata = isc.importo_pagato || 0;
      nome = isc.partecipante_nome || '';
    } else {
      dovuta = 0; pagata = 0; nome = '';
    }
  }
  document.getElementById('pagamentoIscrizioneId').value = iscrizioneId;
  document.getElementById('pagamentoDescText').textContent = `Registrazione quota per: ${nome} (Quota dovuta: € ${Number(dovuta).toFixed(2)})`;
  document.getElementById('pagamentoImporto').value = pagata > 0 ? pagata : dovuta;
  document.getElementById('pagamentoStatoSelect').value = pagata >= dovuta && dovuta > 0 ? 'saldato' : 'acconto';
  openModal('modalPagamentoQuota');
}

async function handleSalvaPagamento(e) {
  e.preventDefault();
  const id = document.getElementById('pagamentoIscrizioneId').value;
  const importo = parseFloat(document.getElementById('pagamentoImporto').value);
  const stato = document.getElementById('pagamentoStatoSelect').value;

  try {
    const res = await fetch(`/api/iscrizioni/${id}/pagamento`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ importo_pagato: importo, stato_pagamento: stato })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio');

    showToast(data.message, 'success');
    closeModal('modalPagamentoQuota');
    await loadSegreteriaIscrizioni();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openModalModificaRuoli(userId) {
  openModalAssegnaPermessiUtente(userId);
}

async function handleSalvaRuoliUtente(e) {
  e.preventDefault();
  const id = document.getElementById('ruoliUtenteId').value;
  const ruoloPrimario = document.getElementById('ruoloPrimarioSelect').value;
  const checkedPrivs = Array.from(document.querySelectorAll('input[name="privilegiCheck"]:checked')).map(cb => cb.value);

  try {
    const res = await fetch(`/api/utenti/${id}/ruoli`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ruolo: ruoloPrimario, privilegi: checkedPrivs })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore aggiornamento privilegi');

    showToast(data.message, 'success');
    closeModal('modalModificaRuoli');
    await loadUtenti();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function apriRicevutaIscrizione(iscrizioneId) {
  const isc = cacheIscrizioni.find(i => i.id === iscrizioneId) || {};
  const contentEl = document.getElementById('printableModuloContent');

  contentEl.innerHTML = `
    <div class="printable-card" style="padding: 24px; border: 1px solid var(--border-light); border-radius: var(--radius-md);">
      <div style="display: flex; justify-content: space-between; border-bottom: 2px solid var(--primary); padding-bottom: 12px; margin-bottom: 20px;">
        <div>
          <h2 style="font-family: var(--font-serif); font-size: 22px; color: var(--primary); margin-bottom: 2px;">Parrocchia Sacro Cuore di Gesù</h2>
          <span style="font-size: 12px; color: var(--ink-700);">Diocesi di Asti · Via Pier Santi Mattarella 2, 14100 Asti</span>
        </div>
        <div style="text-align: right; font-size: 12px; color: var(--ink-700);">
          <strong>MODULO ISCRIZIONE & RICEVUTA</strong><br>
          Protocollo: SC-${isc.id || '2026'}<br>
          Data: ${isc.data_iscrizione || new Date().toLocaleDateString('it-IT')}
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; font-size: 13px;">
        <div>
          <strong style="color: var(--ink-900); display: block; margin-bottom: 4px;">Dati Partecipante:</strong>
          Nome e Cognome: <strong>${escapeHtml(isc.partecipante_nome || '-')}</strong><br>
          Codice Fiscale: <strong style="font-family: monospace;">${escapeHtml(isc.codice_fiscale_partecipante || '-')}</strong><br>
          Età: ${isc.partecipante_eta || '-'} anni · Sesso: ${isc.partecipante_sesso || '-'}
        </div>
        <div>
          <strong style="color: var(--ink-900); display: block; margin-bottom: 4px;">Attività Parrocchiale:</strong>
          Attività: <strong>${escapeHtml(isc.attivita_titolo || '-')}</strong><br>
          Famiglia: ${escapeHtml(isc.nome_famiglia || '-')}<br>
          Recapito Telefonico: ${escapeHtml(isc.telefono_contatto || '-')}
        </div>
      </div>

      <div style="background: var(--bg-subtle); padding: 14px; border-radius: var(--radius-md); margin-bottom: 20px; font-size: 13px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
          <span>Quota Totale Iscrizione:</span>
          <strong>€ ${(isc.importo_dovuto || 0).toFixed(2)}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
          <span>Importo Versato:</span>
          <strong style="color: #15803d;">€ ${(isc.importo_pagato || 0).toFixed(2)}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border-light); padding-top: 6px;">
          <span>Stato Pagamento:</span>
          <strong style="text-transform: uppercase;">${escapeHtml(isc.stato_pagamento || 'Saldato')}</strong>
        </div>
      </div>

      ${(isc.allergie || isc.intolleranze_alimentari) ? `
        <div style="background: #fff5f5; border: 1px solid #fed7d7; padding: 10px; border-radius: var(--radius-sm); font-size: 12px; margin-bottom: 20px; color: #991b1b;">
          <strong>Segnalazioni Sanitarie / Intolleranze:</strong><br>
          ${escapeHtml(isc.intolleranze_alimentari ? `Intolleranze: ${isc.intolleranze_alimentari}` : '')}
          ${escapeHtml(isc.allergie ? ` · Allergie: ${isc.allergie}` : '')}
        </div>
      ` : ''}

      <div style="font-size: 11px; color: var(--ink-500); line-height: 1.5; margin-bottom: 30px;">
        Consensi registrati: Trattamento dati GDPR (Sì), Foto e video parrocchiali (${isc.consenso_foto ? 'Sì' : 'No'}), Uscite e gite (${isc.consenso_uscite ? 'Sì' : 'No'}).
      </div>

      <div style="display: flex; justify-content: space-between; margin-top: 40px; font-size: 12px;">
        <div style="border-top: 1px solid #333; width: 200px; text-align: center; padding-top: 6px;">
          Firma del Genitore / Tutore
        </div>
        <div style="border-top: 1px solid #333; width: 200px; text-align: center; padding-top: 6px;">
          Timbro e Firma Parrocchia
        </div>
      </div>
    </div>
  `;

  openModal('modalStampaRicevuta');
}

async function openModalNuovaPersona() {
  document.getElementById('personaNome').value = '';
  document.getElementById('personaCognome').value = '';
  document.getElementById('personaCF').value = '';
  document.getElementById('personaCFFeedback').textContent = '';
  if (document.getElementById('personaLuogoNascita')) document.getElementById('personaLuogoNascita').value = '';
  document.getElementById('personaTelefono').value = '';
  document.getElementById('personaEmail').value = '';
  document.getElementById('personaIndirizzo').value = '';
  document.getElementById('personaIntolleranze').value = '';
  document.getElementById('personaAllergie').value = '';
  await loadAllergieSuggerite();
  renderAllergyPills('personaAllergiePills', 'personaIntolleranze', 'personaAllergie');
  openModal('modalNuovaPersona');
}

async function handleSalvaNuovaPersona(e) {
  e.preventDefault();
  const nome = document.getElementById('personaNome').value.trim();
  const cognome = document.getElementById('personaCognome').value.trim();
  const cf = document.getElementById('personaCF').value.toUpperCase().trim();
  const sesso = document.getElementById('personaSesso').value;
  const dataNascita = document.getElementById('personaDataNascita').value;
  const luogoNascita = document.getElementById('personaLuogoNascita') ? document.getElementById('personaLuogoNascita').value.trim() : '';
  const telefono = document.getElementById('personaTelefono').value.trim();
  const email = document.getElementById('personaEmail').value.trim();
  const indirizzo = document.getElementById('personaIndirizzo').value.trim();
  const comune = document.getElementById('personaComune').value.trim();
  const intolleranze = document.getElementById('personaIntolleranze').value.trim();
  const allergie = document.getElementById('personaAllergie').value.trim();

  try {
    const res = await fetch('/api/persone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome, cognome, codice_fiscale: cf, sesso, data_nascita: dataNascita,
        luogo_nascita: luogoNascita,
        telefono, email, indirizzo_residenza: indirizzo, comune_residenza: comune,
        intolleranze_alimentari: intolleranze, allergie
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore inserimento anagrafica');

    showToast(data.message, 'success');
    closeModal('modalNuovaPersona');
    await loadAnagrafica();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= EXCEL DRAG & DROP & UPLOAD =================
function setupDropzone() {
  const dropzone = document.getElementById('excelDropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length) uploadExcelFile(files[0]);
  }, false);
}

function handleExcelFileSelected(e) {
  const files = e.target.files;
  if (files.length) uploadExcelFile(files[0]);
}

async function uploadExcelFile(file) {
  const progressBox = document.getElementById('fileUploadProgress');
  const fileNameDisplay = document.getElementById('fileNameDisplay');
  const statusDisplay = document.getElementById('fileUploadStatus');
  const reportBox = document.getElementById('importReportBox');
  const reportDetails = document.getElementById('importReportDetails');

  progressBox.style.display = 'block';
  fileNameDisplay.textContent = file.name;
  statusDisplay.textContent = 'Elaborazione e validazione Codici Fiscali in corso...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/excel/import', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore importazione file');

    statusDisplay.textContent = '✓ Completato con successo!';
    showToast(data.message, 'success');

    const d = data.dettagli;
    reportBox.style.display = 'block';
    reportDetails.innerHTML = `
      <div>Righe analizzate: <strong>${d.totale_righe}</strong></div>
      <div>Persone create: <strong>${d.persone_create}</strong> · Aggiornate: <strong>${d.persone_aggiornate}</strong></div>
      <div>Nuclei familiari collegati: <strong>${d.nuclei_creati}</strong></div>
      <div>Iscrizioni registrate: <strong>${d.iscrizioni_create}</strong></div>
      ${d.errori.length ? `<div style="color:#b91c1c; margin-top:6px;">Avvisi: ${d.errori.join('<br>')}</div>` : ''}
    `;
  } catch (err) {
    statusDisplay.textContent = '✗ Errore';
    showToast(err.message, 'error');
  }
}

function exportExcelAnagrafica() {
  window.location.href = '/api/excel/export-anagrafica';
}

function exportExcelOratorio() {
  const oratorioAtt = cacheAttivita.find(a => a.categoria === 'oratorio');
  const id = oratorioAtt ? oratorioAtt.id : 1;
  window.location.href = `/api/excel/export-attivita/${id}`;
}

// ================= TOASTS & UTILITIES =================
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : (type === 'error' ? '✗' : 'ℹ')}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ================= PARISH FEATURES: ALLERGIE PILLS & HELPERS =================
let cacheAllergieSuggerite = [];

async function loadAllergieSuggerite() {
  try {
    const res = await fetch('/api/configurazioni/allergie');
    const data = await res.json();
    cacheAllergieSuggerite = data.allergie || [];
  } catch (err) {
    console.error('Errore caricamento allergie suggerite:', err);
  }
}

function renderAllergyPills(containerId, inputIntollId, inputAllergieId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const inputAll = document.getElementById(inputAllergieId);
  const inputInt = document.getElementById(inputIntollId);
  
  const currentVal = ((inputAll ? inputAll.value : '') + ' ' + (inputInt ? inputInt.value : '')).toLowerCase();

  container.innerHTML = cacheAllergieSuggerite.map(a => {
    const isSelected = currentVal.includes(a.nome.toLowerCase());
    return `
      <span class="allergy-chip ${isSelected ? 'active' : ''}" data-nome="${escapeHtml(a.nome)}" onclick="toggleAllergyChip(this, '${inputAllergieId}')">
        + ${escapeHtml(a.nome)}
      </span>
    `;
  }).join('');
}

function toggleAllergyChip(el, inputTargetId, rawNome) {
  el.classList.toggle('active');
  const nome = rawNome || el.getAttribute('data-nome') || el.textContent.replace(/^\+\s*/, '').trim();
  const input = document.getElementById(inputTargetId);
  if (!input || !nome) return;
  let items = input.value.split(',').map(s => s.trim()).filter(Boolean);
  if (el.classList.contains('active')) {
    if (!items.some(x => x.toLowerCase() === nome.toLowerCase())) {
      items.push(nome);
    }
  } else {
    items = items.filter(x => x.toLowerCase() !== nome.toLowerCase());
  }
  input.value = items.join(', ');
}

// ================= PARISH FEATURES: POPULATE CATEGORIA SELECTS =================
async function populateCategoriaSelects() {
  try {
    const res = await fetch('/api/configurazioni/categorie');
    const data = await res.json();
    const cats = data.categorie || [];
    const attCatSelect = document.getElementById('attCategoria');
    const modCatSelect = document.getElementById('modAttCategoria');

    const opts = cats.map(c => `
      <option value="${escapeHtml(c.codice)}">${escapeHtml(c.icona || '📌')} ${escapeHtml(c.nome)}</option>
    `).join('');

    if (attCatSelect && opts) attCatSelect.innerHTML = opts;
    if (modCatSelect && opts) modCatSelect.innerHTML = opts;
  } catch (err) {
    console.error('Errore popolamento categorie:', err);
  }
}

// ================= MODIFICA ATTIVITÀ & LOCANDINA =================
async function openModalModificaAttivita(id) {
  let a = cacheAttivita.find(x => x.id === id);
  if (!a) {
    const res = await fetch(`/api/attivita/${id}`);
    const data = await res.json();
    a = data.attivita;
  }
  if (!a) return;

  document.getElementById('modAttId').value = a.id;
  document.getElementById('modAttTitolo').value = a.titolo || '';

  await populateCategoriaSelects();
  document.getElementById('modAttCategoria').value = a.categoria || 'oratorio';
  document.getElementById('modAttPubblicato').value = a.is_pubblicato ? 'true' : 'false';
  document.getElementById('modAttEtaMin').value = a.eta_min;
  document.getElementById('modAttEtaMax').value = a.eta_max;
  document.getElementById('modAttQuota').value = a.quota_iscrizione;
  document.getElementById('modAttPosti').value = a.posti_massimi !== null ? a.posti_massimi : '';
  document.getElementById('modAttDataInizio').value = a.data_inizio || '';
  document.getElementById('modAttDataFine').value = a.data_fine || '';
  document.getElementById('modAttDescrizione').value = a.descrizione || '';
  document.getElementById('modAttLocandinaInput').value = '';

  const locBox = document.getElementById('modAttLocandinaCurrentBox');
  const locText = document.getElementById('modAttLocandinaText');
  const locDel = document.getElementById('modAttLocandinaDeleteBtn');
  if (a.locandina_url) {
    locBox.style.display = 'flex';
    locText.innerHTML = `Locandina attuale presente: <a href="${a.locandina_url}" target="_blank" style="margin-left:8px; font-weight:700;">Apri locandina</a>`;
    locDel.style.display = 'inline-block';
  } else {
    locBox.style.display = 'none';
    locDel.style.display = 'none';
  }

  // Popola campi personalizzati specifici per questo evento
  let cPers = a.campi_personalizzati;
  if (typeof cPers === 'string') {
    try { cPers = JSON.parse(cPers); } catch(e) { cPers = []; }
  }
  campiPersonalizzatiModAttivita = Array.isArray(cPers) ? JSON.parse(JSON.stringify(cPers)) : [];
  renderCampiPersonalizzatiModAttivita();

  openModal('modalModificaAttivita');
}

async function handleSalvaModificaAttivita(e) {
  e.preventDefault();
  const id = document.getElementById('modAttId').value;
  const titolo = document.getElementById('modAttTitolo').value.trim();
  const categoria = document.getElementById('modAttCategoria').value;
  const isPubblicato = document.getElementById('modAttPubblicato').value === 'true';
  const etaMin = parseInt(document.getElementById('modAttEtaMin').value);
  const etaMax = parseInt(document.getElementById('modAttEtaMax').value);
  const quota = parseFloat(document.getElementById('modAttQuota').value || '0');
  const posti = document.getElementById('modAttPosti').value ? parseInt(document.getElementById('modAttPosti').value) : null;
  const dataInizio = document.getElementById('modAttDataInizio').value || null;
  const dataFine = document.getElementById('modAttDataFine').value || null;
  const descrizione = document.getElementById('modAttDescrizione').value.trim();

  try {
    const res = await fetch(`/api/attivita/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        titolo, categoria, is_pubblicato: isPubblicato,
        eta_min: etaMin, eta_max: etaMax, quota_iscrizione: quota,
        posti_massimi: posti, data_inizio: dataInizio, data_fine: dataFine,
        descrizione,
        campi_personalizzati: campiPersonalizzatiModAttivita
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica attività');

    // Se è stato selezionato un file per la locandina, caricalo
    const fileInput = document.getElementById('modAttLocandinaInput');
    if (fileInput.files && fileInput.files[0]) {
      const fd = new FormData();
      fd.append('locandina', fileInput.files[0]);
      await fetch(`/api/attivita/${id}/locandina`, {
        method: 'POST',
        body: fd
      });
    }

    showToast('Attività aggiornata con successo', 'success');
    closeModal('modalModificaAttivita');
    await loadAttivita();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rimuoviLocandinaAttivita() {
  const id = document.getElementById('modAttId').value;
  if (!confirm('Vuoi rimuovere la locandina allegata a questa attività?')) return;
  try {
    const res = await fetch(`/api/attivita/${id}/locandina`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore rimozione locandina');
    showToast('Locandina rimossa', 'success');
    document.getElementById('modAttLocandinaCurrentBox').style.display = 'none';
    await loadAttivita();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaAttivita(id) {
  if (!id) return;
  const att = (cacheAttivita || []).find(a => a.id === id);
  const titolo = att ? att.titolo : 'questa attività';
  if (!confirm(`Sei sicuro di voler eliminare definitivamente l'attività "${titolo}"?\nTutte le iscrizioni, presenze e riferimenti collegati verranno eliminati.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/attivita/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore durante l\'eliminazione');
    showToast(data.message || 'Attività eliminata con successo', 'success');
    closeModal('modalModificaAttivita');
    await loadAttivita();
    await loadPublicHomepage();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaAttivitaCorrente() {
  const id = parseInt(document.getElementById('modAttId').value);
  if (id) {
    await eliminaAttivita(id);
  }
}

// ================= MODIFICA PERSONA & CERTIFICATO BATTESIMO =================
async function openModalModificaPersona(cf) {
  try {
    const res = await fetch(`/api/persone/${cf}`);
    const data = await res.json();
    const p = data.persona;
    if (!p) throw new Error('Persona non trovata');

    document.getElementById('modPersonaCF').value = p.codice_fiscale;
    document.getElementById('modPersonaCFDisplay').textContent = p.codice_fiscale;
    document.getElementById('modPersonaNome').value = p.nome || '';
    document.getElementById('modPersonaCognome').value = p.cognome || '';
    document.getElementById('modPersonaSesso').value = p.sesso || 'M';
    document.getElementById('modPersonaDataNascita').value = p.data_nascita || '';
    document.getElementById('modPersonaLuogoNascita').value = p.luogo_nascita || '';
    document.getElementById('modPersonaIndirizzo').value = p.indirizzo_residenza || '';
    document.getElementById('modPersonaComune').value = p.comune_residenza || p.comune || 'Asti';
    document.getElementById('modPersonaTelefono').value = p.telefono || '';
    if (document.getElementById('modPersonaCellulare')) {
      document.getElementById('modPersonaCellulare').value = p.cellulare || p.telefono || '';
    }
    if (document.getElementById('modPersonaRuoloFamiglia')) {
      document.getElementById('modPersonaRuoloFamiglia').value = p.ruolo_famiglia || 'Figlio/a';
    }
    document.getElementById('modPersonaEmail').value = p.email || '';
    document.getElementById('modPersonaIntolleranze').value = p.intolleranze_alimentari || '';
    document.getElementById('modPersonaAllergie').value = p.allergie || '';
    if (document.getElementById('modPersonaNoteGenerali')) {
      document.getElementById('modPersonaNoteGenerali').value = p.note_generali || '';
    }
    document.getElementById('modPersonaBattesimoInput').value = '';

    await loadAllergieSuggerite();
    renderAllergyPills('modPersonaAllergiePills', 'modPersonaIntolleranze', 'modPersonaAllergie');

    const badge = document.getElementById('modPersonaBattesimoBadge');
    const link = document.getElementById('modPersonaBattesimoLink');
    const delBtn = document.getElementById('modPersonaBattesimoDelBtn');
    if (p.certificato_battesimo_url) {
      badge.className = 'certificato-badge presente';
      badge.textContent = 'Certificato di Battesimo presente';
      link.href = p.certificato_battesimo_url;
      link.style.display = 'inline';
      delBtn.style.display = 'inline-block';
    } else {
      badge.className = 'certificato-badge mancante';
      badge.textContent = 'Nessun certificato caricato';
      link.style.display = 'none';
      delBtn.style.display = 'none';
    }

    openModal('modalModificaPersona');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSalvaModificaPersona(e) {
  e.preventDefault();
  const cf = document.getElementById('modPersonaCF').value;
  const nome = document.getElementById('modPersonaNome').value.trim();
  const cognome = document.getElementById('modPersonaCognome').value.trim();
  const sesso = document.getElementById('modPersonaSesso').value;
  const dataNascita = document.getElementById('modPersonaDataNascita').value;
  const luogoNascita = document.getElementById('modPersonaLuogoNascita').value.trim();
  const indirizzo = document.getElementById('modPersonaIndirizzo').value.trim();
  const comune = document.getElementById('modPersonaComune').value.trim();
  const telefono = document.getElementById('modPersonaTelefono').value.trim();
  const cellulare = document.getElementById('modPersonaCellulare')?.value.trim() || '';
  const ruoloFamiglia = document.getElementById('modPersonaRuoloFamiglia')?.value || 'Figlio/a';
  const email = document.getElementById('modPersonaEmail').value.trim();
  const intolleranze = document.getElementById('modPersonaIntolleranze').value.trim();
  const allergie = document.getElementById('modPersonaAllergie').value.trim();
  const noteGenerali = document.getElementById('modPersonaNoteGenerali')?.value.trim() || '';

  try {
    const res = await fetch(`/api/persone/${cf}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nome, cognome, sesso, data_nascita: dataNascita,
        luogo_nascita: luogoNascita, indirizzo_residenza: indirizzo,
        comune_residenza: comune, telefono: cellulare || telefono, email,
        intolleranze_alimentari: intolleranze, allergie,
        ruolo_famiglia: ruoloFamiglia,
        note_generali: noteGenerali
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica anagrafica');

    // Carica certificato battesimo se selezionato
    const fileInput = document.getElementById('modPersonaBattesimoInput');
    if (fileInput.files && fileInput.files[0]) {
      const fd = new FormData();
      fd.append('certificato', fileInput.files[0]);
      await fetch(`/api/persone/${cf}/certificato-battesimo`, {
        method: 'POST',
        body: fd
      });
    }

    showToast('Scheda anagrafica aggiornata con successo', 'success');
    closeModal('modalModificaPersona');

    if (currentView === 'anagrafica') await loadAnagrafica();
    if (currentView === 'famiglia') await loadFamiglia();
    if (currentView === 'oratorio') await loadOratorio();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function rimuoviCertificatoBattesimoPersona() {
  const cf = document.getElementById('modPersonaCF').value;
  if (!confirm('Vuoi rimuovere il certificato di battesimo allegato?')) return;
  try {
    const res = await fetch(`/api/persone/${cf}/certificato-battesimo`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione certificato');
    showToast('Certificato di battesimo rimosso', 'success');
    document.getElementById('modPersonaBattesimoBadge').className = 'certificato-badge mancante';
    document.getElementById('modPersonaBattesimoBadge').textContent = 'Nessun certificato caricato';
    document.getElementById('modPersonaBattesimoLink').style.display = 'none';
    document.getElementById('modPersonaBattesimoDelBtn').style.display = 'none';
    if (currentView === 'anagrafica') await loadAnagrafica();
    if (currentView === 'famiglia') await loadFamiglia();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= CONFIGURAZIONI SEGRETERIA (CATEGORIE, ALLERGIE, CLAUSOLE, CAMPI) =================
async function loadConfigurazioniSegreteria() {
  await Promise.all([
    loadCategorieConfig(),
    loadAllergieConfig(),
    loadClausoleConfig()
  ]);
}

let cacheCategorieConfig = [];
let cacheClausoleConfig = [];

async function loadCategorieConfig() {
  try {
    const res = await fetch('/api/configurazioni/categorie');
    const data = await res.json();
    cacheCategorieConfig = data.categorie || [];
    const tbody = document.querySelector('#tableSegCategorie tbody');
    if (tbody) {
      if (!cacheCategorieConfig.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--ink-500);">Nessuna categoria configurata.</td></tr>';
      } else {
        tbody.innerHTML = cacheCategorieConfig.map(c => `
          <tr>
            <td><code>${escapeHtml(c.codice)}</code></td>
            <td><strong>${escapeHtml(c.icona || '📌')} ${escapeHtml(c.nome)}</strong></td>
            <td>
              <span class="badge ${c.is_attiva ? 'badge-success' : 'badge-danger'}">${c.is_attiva ? 'Attiva' : 'Disattivata'}</span>
            </td>
            <td>
              <div style="display:flex; gap:6px;">
                <button class="btn btn-sm btn-secondary" onclick="openModalModificaCategoria(${c.id})">✏️ Modifica</button>
                <button class="btn btn-sm btn-danger" onclick="eliminaCategoria(${c.id})">Elimina</button>
              </div>
            </td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Errore categorie:', err);
  }
}

function openModalModificaCategoria(id) {
  const cat = cacheCategorieConfig.find(c => c.id === id);
  if (!cat) return;
  document.getElementById('modCatId').value = cat.id;
  document.getElementById('modCatCodice').value = cat.codice;
  document.getElementById('modCatNome').value = cat.nome;
  document.getElementById('modCatIcona').value = cat.icona || '';
  document.getElementById('modCatAttiva').value = cat.is_attiva !== false ? 'true' : 'false';
  openModal('modalModificaCategoria');
}

async function handleSalvaModificaCategoria(e) {
  e.preventDefault();
  const id = document.getElementById('modCatId').value;
  const nome = document.getElementById('modCatNome').value.trim();
  const icona = document.getElementById('modCatIcona').value.trim();
  const is_attiva = document.getElementById('modCatAttiva').value === 'true';

  try {
    const res = await fetch(`/api/configurazioni/categorie/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, icona, is_attiva })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica categoria');

    showToast(data.message, 'success');
    closeModal('modalModificaCategoria');
    await loadCategorieConfig();
    await populateCategoriaSelects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSalvaNuovaCategoria(e) {
  e.preventDefault();
  const codice = document.getElementById('nuovaCatCodice').value.trim();
  const nome = document.getElementById('nuovaCatNome').value.trim();
  const icona = document.getElementById('nuovaCatIcona').value.trim();
  const descrizione = document.getElementById('nuovaCatDescrizione').value.trim();

  try {
    const res = await fetch('/api/configurazioni/categorie', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice, nome, icona, descrizione })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio categoria');
    showToast(data.message, 'success');
    document.getElementById('nuovaCatCodice').value = '';
    document.getElementById('nuovaCatNome').value = '';
    document.getElementById('nuovaCatDescrizione').value = '';
    await loadCategorieConfig();
    await populateCategoriaSelects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaCategoria(id) {
  if (!confirm(`Sei sicuro di voler eliminare questa categoria?`)) return;
  try {
    const res = await fetch(`/api/configurazioni/categorie/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione categoria');
    showToast(data.message, 'success');
    await loadCategorieConfig();
    await populateCategoriaSelects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadAllergieConfig() {
  try {
    const res = await fetch('/api/configurazioni/allergie');
    const data = await res.json();
    cacheAllergieSuggerite = data.allergie || [];
    const container = document.getElementById('segAllergiePillsGrid');
    if (container) {
      if (!cacheAllergieSuggerite.length) {
        container.innerHTML = '<span style="font-size:12px; color:var(--ink-500);">Nessuna allergia configurata.</span>';
      } else {
        container.innerHTML = cacheAllergieSuggerite.map(a => `
          <div class="allergy-chip active" style="gap:8px;">
            <span>${escapeHtml(a.nome)}</span>
            <span style="cursor:pointer; font-weight:800; opacity:0.8;" onclick="eliminaAllergia(${a.id})" title="Elimina voce">×</span>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Errore allergie config:', err);
  }
}

async function handleSalvaNuovaAllergia(e) {
  e.preventDefault();
  const nome = document.getElementById('nuovaAllergiaNome').value.trim();
  try {
    const res = await fetch('/api/configurazioni/allergie', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio allergia');
    showToast(data.message, 'success');
    document.getElementById('nuovaAllergiaNome').value = '';
    await loadAllergieConfig();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaAllergia(id) {
  try {
    const res = await fetch(`/api/configurazioni/allergie/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione allergia');
    showToast(data.message, 'success');
    await loadAllergieConfig();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadClausoleConfig() {
  try {
    const res = await fetch('/api/configurazioni/clausole');
    const data = await res.json();
    cacheClausoleConfig = data.clausole || [];
    const tbody = document.querySelector('#tableSegClausole tbody');
    if (tbody) {
      if (!cacheClausoleConfig.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--ink-500);">Nessuna clausola configurata.</td></tr>';
      } else {
        tbody.innerHTML = cacheClausoleConfig.map(c => `
          <tr>
            <td><strong>${escapeHtml(c.titolo)}</strong></td>
            <td>
              ${(c.is_obbligatoria || c.obbligatoria) ? '<span class="badge badge-published">OBBLIGATORIA</span>' : '<span class="badge badge-neutral">FACOLTATIVA</span>'}
            </td>
            <td>
              <span class="badge ${c.is_attiva !== false ? 'badge-success' : 'badge-danger'}">${c.is_attiva !== false ? 'Attiva' : 'Disattivata'}</span>
            </td>
            <td style="font-size:12px; color:var(--ink-700); max-width:300px;">${escapeHtml(c.testo)}</td>
            <td>
              <div style="display:flex; gap:6px;">
                <button class="btn btn-sm btn-secondary" onclick="openModalModificaClausola(${c.id})">✏️ Modifica</button>
                <button class="btn btn-sm btn-danger" onclick="eliminaClausola(${c.id})">Elimina</button>
              </div>
            </td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Errore clausole:', err);
  }
}

function openModalModificaClausola(id) {
  const cl = cacheClausoleConfig.find(c => c.id === id);
  if (!cl) return;
  document.getElementById('modClausolaId').value = cl.id;
  document.getElementById('modClausolaTitolo').value = cl.titolo;
  document.getElementById('modClausolaObbligatoria').value = (cl.is_obbligatoria || cl.obbligatoria) ? 'true' : 'false';
  document.getElementById('modClausolaTesto').value = cl.testo;
  document.getElementById('modClausolaAttiva').value = cl.is_attiva !== false ? 'true' : 'false';
  openModal('modalModificaClausola');
}

async function handleSalvaModificaClausola(e) {
  e.preventDefault();
  const id = document.getElementById('modClausolaId').value;
  const titolo = document.getElementById('modClausolaTitolo').value.trim();
  const is_obbligatoria = document.getElementById('modClausolaObbligatoria').value === 'true';
  const testo = document.getElementById('modClausolaTesto').value.trim();
  const is_attiva = document.getElementById('modClausolaAttiva').value === 'true';

  try {
    const res = await fetch(`/api/configurazioni/clausole/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titolo, is_obbligatoria, testo, is_attiva })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore modifica clausola');

    showToast(data.message, 'success');
    closeModal('modalModificaClausola');
    await loadClausoleConfig();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleSalvaNuovaClausola(e) {
  e.preventDefault();
  const titolo = document.getElementById('nuovaClausolaTitolo').value.trim();
  const obbligatoria = document.getElementById('nuovaClausolaObbligatoria').value === 'true';
  const testo = document.getElementById('nuovaClausolaTesto').value.trim();

  try {
    const res = await fetch('/api/configurazioni/clausole', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titolo, obbligatoria, testo })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio clausola');
    showToast(data.message, 'success');
    document.getElementById('nuovaClausolaTitolo').value = '';
    document.getElementById('nuovaClausolaTesto').value = '';
    await loadClausoleConfig();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaClausola(id) {
  if (!confirm('Eliminare questa clausola dalle iscrizioni?')) return;
  try {
    const res = await fetch(`/api/configurazioni/clausole/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione clausola');
    showToast(data.message, 'success');
    await loadClausoleConfig();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadCampiAccountSegreteria() {
  try {
    const res = await fetch('/api/configurazioni/campi-account');
    const data = await res.json();
    const campi = data.campi || [];
    const tbody = document.querySelector('#tableSegCampiAccount tbody');
    if (tbody) {
      if (!campi.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--ink-500);">Nessun campo personalizzato account configurato.</td></tr>';
      } else {
        tbody.innerHTML = campi.map(c => `
          <tr>
            <td><strong>${escapeHtml(c.nome)}</strong></td>
            <td><code>${escapeHtml(c.chiave)}</code></td>
            <td><span class="badge badge-info">${escapeHtml(c.tipo)}</span></td>
            <td>${c.obbligatorio ? '<span class="badge badge-published">SÌ</span>' : 'No'}</td>
            <td style="font-size:12px;">${escapeHtml(c.opzioni || '-')}</td>
            <td>
              <button class="btn btn-sm btn-secondary" style="color:#dc2626;" onclick="eliminaCampoAccount(${c.id})">Elimina</button>
            </td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Errore campi account:', err);
  }
}

async function handleSalvaNuovoCampoAccount(e) {
  e.preventDefault();
  const nome = document.getElementById('nuovoCampoNome').value.trim();
  const chiave = document.getElementById('nuovoCampoChiave').value.trim();
  const tipo = document.getElementById('nuovoCampoTipo').value;
  const obbligatorio = document.getElementById('nuovoCampoObbligatorio').value === 'true';
  const opzioni = document.getElementById('nuovoCampoOpzioni').value.trim();

  try {
    const res = await fetch('/api/configurazioni/campi-account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, chiave, tipo, obbligatorio, opzioni })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio campo');
    showToast(data.message, 'success');
    document.getElementById('nuovoCampoNome').value = '';
    document.getElementById('nuovoCampoChiave').value = '';
    document.getElementById('nuovoCampoOpzioni').value = '';
    await loadCampiAccountSegreteria();
    await renderCustomRegistrationFields();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaCampoAccount(id) {
  if (!confirm('Eliminare questo campo personalizzato?')) return;
  try {
    const res = await fetch(`/api/configurazioni/campi-account/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione campo');
    showToast(data.message, 'success');
    await loadCampiAccountSegreteria();
    await renderCustomRegistrationFields();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= RECUPERO PASSWORD UTENTE =================
function openModalRecuperaPassword() {
  document.getElementById('recuperoStep1').style.display = 'block';
  document.getElementById('recuperoStep2').style.display = 'none';
  document.getElementById('recuperoEmailInput').value = '';
  document.getElementById('recuperoCodiceInput').value = '';
  document.getElementById('recuperoNuovaPwInput').value = '';
  document.getElementById('recuperoConfermaPwInput').value = '';
  openModal('modalRecuperaPassword');
}

function tornaAStep1Recupero() {
  document.getElementById('recuperoStep1').style.display = 'block';
  document.getElementById('recuperoStep2').style.display = 'none';
}

async function handleInviaCodiceRecupero() {
  const email = document.getElementById('recuperoEmailInput').value.trim();
  if (!email) {
    showToast('Inserisci il tuo indirizzo email', 'warning');
    return;
  }

  const btn = document.getElementById('btnInviaCodiceRecupero');
  btn.disabled = true;
  btn.textContent = 'Invio codice in corso...';

  try {
    const res = await fetch('/api/auth/recupera-password/richiedi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore invio codice');

    showToast(data.message, 'success');
    document.getElementById('recuperoEmailTarget').textContent = email;
    document.getElementById('recuperoStep1').style.display = 'none';
    document.getElementById('recuperoStep2').style.display = 'block';
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Invia Codice di Sicurezza →';
  }
}

async function handleConfermaNuovaPassword() {
  const email = document.getElementById('recuperoEmailTarget').textContent.trim();
  const codice = document.getElementById('recuperoCodiceInput').value.trim();
  const nuovaPw = document.getElementById('recuperoNuovaPwInput').value;
  const confermaPw = document.getElementById('recuperoConfermaPwInput').value;

  if (!codice || codice.length !== 6) {
    showToast('Inserisci il codice di sicurezza a 6 cifre ricevuto via email', 'warning');
    return;
  }
  if (!nuovaPw || nuovaPw.length < 6) {
    showToast('La nuova password deve contenere almeno 6 caratteri', 'warning');
    return;
  }
  if (nuovaPw !== confermaPw) {
    showToast('Le due password inserite non coincidono', 'warning');
    return;
  }

  const btn = document.getElementById('btnConfermaRecupero');
  btn.disabled = true;
  btn.textContent = 'Salvataggio in corso...';

  try {
    const res = await fetch('/api/auth/recupera-password/conferma', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, codice, nuova_password: nuovaPw })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore reimpostazione password');

    showToast(data.message, 'success');
    closeModal('modalRecuperaPassword');

    // Pre-compila credenziali nel form di login
    const loginEmail = document.getElementById('inputLoginEmail');
    if (loginEmail) loginEmail.value = email;
    const loginPw = document.getElementById('inputLoginPassword');
    if (loginPw) loginPw.value = nuovaPw;
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Conferma e Salva Nuova Password';
  }
}

// ================= CELEBRAZIONI (MESSE, LITURGIA, AVVENIMENTI) =================
let cacheCelebrazioni = [];
let cacheCelebrazioniPubbliche = [];
let currentCelebrazioniTab = 'messe';

async function loadCelebrazioniPubbliche() {
  try {
    const res = await fetch('/api/celebrazioni');
    const data = await res.json();
    cacheCelebrazioniPubbliche = data.celebrazioni || [];
    cambiaTabCelebrazioniPubbliche(currentCelebrazioniTab);
  } catch (err) {
    console.error('Errore caricamento celebrazioni pubbliche:', err);
  }
}

function cambiaTabCelebrazioniPubbliche(sezione) {
  currentCelebrazioniTab = sezione;

  const btnMesse = document.getElementById('pillMesseBtn');
  const btnLiturgia = document.getElementById('pillLiturgiaBtn');
  const btnAvvenimenti = document.getElementById('pillAvvenimentiBtn');

  if (btnMesse) btnMesse.className = `btn btn-sm pill-celebrazione-btn ${sezione === 'messe' ? 'btn-primary active' : 'btn-secondary'}`;
  if (btnLiturgia) btnLiturgia.className = `btn btn-sm pill-celebrazione-btn ${sezione === 'liturgia' ? 'btn-primary active' : 'btn-secondary'}`;
  if (btnAvvenimenti) btnAvvenimenti.className = `btn btn-sm pill-celebrazione-btn ${sezione === 'avvenimenti' ? 'btn-primary active' : 'btn-secondary'}`;

  const titleEl = document.getElementById('publicCelebrazioniTitle');
  if (titleEl) {
    if (sezione === 'messe') titleEl.textContent = 'Orari Sante Messe Parrocchiali';
    if (sezione === 'liturgia') titleEl.textContent = 'Liturgia, Preghiera & Confessioni';
    if (sezione === 'avvenimenti') titleEl.textContent = 'Avvenimenti Speciali, Feste & Ricorrenze';
  }

  const listContainer = document.getElementById('publicCelebrazioniList');
  if (!listContainer) return;

  const items = cacheCelebrazioniPubbliche.filter(c => c.sezione === sezione && c.is_attivo);

  if (!items.length) {
    listContainer.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--ink-500); font-size: 13.5px;">
        Nessuna celebrazione registrata in questa sezione al momento.
      </div>
    `;
    return;
  }

  listContainer.innerHTML = items.map(c => `
    <div class="mass-row">
      <div class="mass-time-badge">${escapeHtml(c.orario)}</div>
      <div class="mass-details">
        <strong>${escapeHtml(c.titolo)}</strong>
        <span>📅 ${escapeHtml(c.giorno)} · 📍 ${escapeHtml(c.luogo || 'Chiesa Parrocchiale')}</span>
        ${c.descrizione ? `<p style="margin: 4px 0 0 0; font-size: 12px; color: var(--ink-700);">${escapeHtml(c.descrizione)}</p>` : ''}
      </div>
    </div>
  `).join('');
}

async function loadSegreteriaCelebrazioni() {
  try {
    const res = await fetch('/api/celebrazioni');
    const data = await res.json();
    cacheCelebrazioni = data.celebrazioni || [];
    const filterSelect = document.getElementById('filterSegCelebrazioneSezione');
    const sezione = filterSelect ? filterSelect.value : '';
    filtraTabellaCelebrazioni(sezione);
  } catch (err) {
    console.error('Errore caricamento celebrazioni segreteria:', err);
  }
}

function filtraTabellaCelebrazioni(sezione) {
  const tbody = document.querySelector('#tableSegCelebrazioni tbody');
  if (!tbody) return;

  let items = cacheCelebrazioni;
  if (sezione) {
    items = items.filter(c => c.sezione === sezione);
  }

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--ink-500);">Nessuna celebrazione registrata per questa sezione.</td></tr>`;
    return;
  }

  const sezioneLabels = {
    'messe': { label: '⛪ Messa', badge: 'badge-info' },
    'liturgia': { label: '🕊️ Liturgia', badge: 'badge-success' },
    'avvenimenti': { label: '🔔 Avvenimento', badge: 'badge-warning' }
  };

  tbody.innerHTML = items.map(c => {
    const conf = sezioneLabels[c.sezione] || { label: c.sezione, badge: 'badge-neutral' };
    return `
      <tr>
        <td><span class="badge ${conf.badge}">${conf.label}</span></td>
        <td>
          <strong style="color:var(--ink-900); font-size:13.5px;">${escapeHtml(c.titolo)}</strong>
          ${c.descrizione ? `<small style="display:block; color:var(--ink-500);">${escapeHtml(c.descrizione)}</small>` : ''}
        </td>
        <td>${escapeHtml(c.giorno)}</td>
        <td><strong style="color:var(--primary);">${escapeHtml(c.orario)}</strong></td>
        <td>${escapeHtml(c.luogo || 'Chiesa')}</td>
        <td>${c.ordine}</td>
        <td>
          <span class="badge ${c.is_attivo ? 'badge-success' : 'badge-neutral'}">
            ${c.is_attivo ? 'VISIBILE' : 'NASCOSTO'}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-sm btn-secondary" onclick="openModalModificaCelebrazione(${c.id})">✏ Modifica</button>
            <button class="btn btn-sm btn-danger" onclick="eliminaCelebrazione(${c.id})">🗑️</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function impostaPresetGiorniMesse(preset) {
  const chks = document.querySelectorAll('input[name="celGiornoCheckbox"]');
  const warn = document.getElementById('celGiorniWarning');
  if (warn) warn.style.display = 'none';

  if (preset === 'feriali') {
    chks.forEach(c => {
      c.checked = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì'].includes(c.value);
    });
  } else if (preset === 'festivi') {
    chks.forEach(c => {
      c.checked = ['Sabato (Prefestivo)', 'Domenica', 'Giorni Festivi'].includes(c.value);
    });
  } else if (preset === 'tutti') {
    chks.forEach(c => c.checked = true);
  } else if (preset === 'reset') {
    chks.forEach(c => c.checked = false);
  }
}

function openModalNuovaCelebrazione() {
  document.getElementById('modalCelebrazioneTitle').textContent = 'Nuova Celebrazione / Orario';
  document.getElementById('celId').value = '';
  document.getElementById('celSezione').value = 'messe';
  document.getElementById('celOrdine').value = '1';
  document.getElementById('celTitolo').value = '';
  
  // Resetta checkboxes giorni
  document.querySelectorAll('input[name="celGiornoCheckbox"]').forEach(c => c.checked = false);
  const warn = document.getElementById('celGiorniWarning');
  if (warn) warn.style.display = 'none';

  // Orario Time Picker
  document.getElementById('celOrarioInizio').value = '18:00';
  document.getElementById('celOrarioFine').value = '';
  document.getElementById('celLuogo').value = 'Chiesa Parrocchiale';
  document.getElementById('celDescrizione').value = '';
  document.getElementById('celAttivo').checked = true;
  openModal('modalCelebrazione');
}

function openModalModificaCelebrazione(id) {
  const c = cacheCelebrazioni.find(x => x.id === id);
  if (!c) return;

  document.getElementById('modalCelebrazioneTitle').textContent = 'Modifica Celebrazione';
  document.getElementById('celId').value = c.id;
  document.getElementById('celSezione').value = c.sezione;
  document.getElementById('celOrdine').value = c.ordine || 1;
  document.getElementById('celTitolo').value = c.titolo || '';

  // Popola checkbox giorni in base al testo memorizzato
  const giornoStr = (c.giorno || '').toLowerCase();
  document.querySelectorAll('input[name="celGiornoCheckbox"]').forEach(cb => {
    const v = cb.value.toLowerCase();
    if (v.includes('lunedì') && giornoStr.includes('lun')) cb.checked = true;
    else if (v.includes('martedì') && giornoStr.includes('mar')) cb.checked = true;
    else if (v.includes('mercoledì') && giornoStr.includes('mer')) cb.checked = true;
    else if (v.includes('giovedì') && giornoStr.includes('gio')) cb.checked = true;
    else if (v.includes('venerdì') && giornoStr.includes('ven')) cb.checked = true;
    else if (v.includes('sabato') && giornoStr.includes('sab')) cb.checked = true;
    else if (v.includes('domenica') && giornoStr.includes('dom')) cb.checked = true;
    else if (v.includes('festivi') && giornoStr.includes('fest')) cb.checked = true;
    else if (giornoStr.includes('tutti')) cb.checked = true;
    else cb.checked = false;
  });
  const warn = document.getElementById('celGiorniWarning');
  if (warn) warn.style.display = 'none';

  // Estrai orario da stringa es. "ore 18:00", "18:00", "17:00 - 18:00"
  const orarioRaw = c.orario || '';
  const timesFound = orarioRaw.match(/\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b/g);
  if (timesFound && timesFound.length > 0) {
    const pad = t => t.length === 4 ? '0' + t : t;
    document.getElementById('celOrarioInizio').value = pad(timesFound[0]);
    document.getElementById('celOrarioFine').value = timesFound[1] ? pad(timesFound[1]) : '';
  } else {
    document.getElementById('celOrarioInizio').value = '18:00';
    document.getElementById('celOrarioFine').value = '';
  }

  document.getElementById('celLuogo').value = c.luogo || 'Chiesa Parrocchiale';
  document.getElementById('celDescrizione').value = c.descrizione || '';
  document.getElementById('celAttivo').checked = !!c.is_attivo;
  openModal('modalCelebrazione');
}

async function handleSalvaCelebrazione(e) {
  e.preventDefault();
  const id = document.getElementById('celId').value;
  const sezione = document.getElementById('celSezione').value;
  const ordine = parseInt(document.getElementById('celOrdine').value) || 0;
  const titolo = document.getElementById('celTitolo').value.trim();

  // Raccogli giorni selezionati dalle checkbox
  const chks = Array.from(document.querySelectorAll('input[name="celGiornoCheckbox"]:checked')).map(cb => cb.value);
  const warn = document.getElementById('celGiorniWarning');
  if (!chks.length) {
    if (warn) warn.style.display = 'block';
    showToast('Seleziona almeno un giorno di celebrazione', 'error');
    return;
  }
  if (warn) warn.style.display = 'none';
  const giorno = chks.join(', ');

  // Formatta orario dal time picker
  const orarioInizio = document.getElementById('celOrarioInizio').value;
  if (!orarioInizio) {
    showToast('Seleziona l\'orario di inizio della celebrazione', 'error');
    return;
  }
  const orarioFine = document.getElementById('celOrarioFine').value;
  const orario = orarioFine ? `${orarioInizio} - ${orarioFine}` : orarioInizio;

  const luogo = document.getElementById('celLuogo').value.trim();
  const descrizione = document.getElementById('celDescrizione').value.trim();
  const isAttivo = document.getElementById('celAttivo').checked;

  const url = id ? `/api/celebrazioni/${id}` : '/api/celebrazioni';
  const method = id ? 'PUT' : 'POST';

  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sezione, ordine, titolo, giorno, orario, luogo, descrizione, is_attivo: isAttivo
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore salvataggio celebrazione');

    showToast(data.message || 'Celebrazione salvata con successo', 'success');
    closeModal('modalCelebrazione');
    await loadSegreteriaCelebrazioni();
    await loadCelebrazioniPubbliche();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaCelebrazione(id) {
  if (!confirm('Vuoi davvero eliminare questa celebrazione/orario?')) return;
  try {
    const res = await fetch(`/api/celebrazioni/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore eliminazione celebrazione');

    showToast(data.message || 'Celebrazione eliminata', 'success');
    await loadSegreteriaCelebrazioni();
    await loadCelebrazioniPubbliche();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= ANTEPRIMA INGRANDITA LOCANDINA =================
function openPreviewLocandina(url, idOrTitle) {
  const modal = document.getElementById('modalAnteprimaLocandina');
  if (!modal) return;
  let titolo = 'Locandina Evento';
  if (typeof idOrTitle === 'number') {
    const att = (cacheAttivita || []).find(x => x.id === idOrTitle);
    const ev = (window.cacheEventiPubblici || []).find(x => x.id === idOrTitle);
    titolo = att ? att.titolo : (ev ? ev.titolo : 'Locandina');
  } else if (typeof idOrTitle === 'string') {
    titolo = idOrTitle;
  }
  document.getElementById('anteprimaLocandinaTitolo').textContent = titolo || 'Locandina Evento';
  const img = document.getElementById('anteprimaLocandinaImg');
  if (img) img.src = url;
  const downloadBtn = document.getElementById('anteprimaLocandinaDownloadBtn');
  if (downloadBtn) downloadBtn.href = url;
  openModal('modalAnteprimaLocandina');
}

// ================= CAMPI EXTRA DINAMICI PER ATTIVITÀ =================
function aggiungiRigaCampoExtraNuovaAttivita(chiave = '', valore = '') {
  const container = document.getElementById('nuovaAttCampiExtraContainer');
  if (container) container.appendChild(creaElementoRigaCampoExtra(chiave, valore));
}

function aggiungiRigaCampoExtraModAttivita(chiave = '', valore = '') {
  const container = document.getElementById('modAttCampiExtraContainer');
  if (container) container.appendChild(creaElementoRigaCampoExtra(chiave, valore));
}

function creaElementoRigaCampoExtra(chiave = '', valore = '') {
  const row = document.createElement('div');
  row.className = 'campo-extra-row';
  row.style.cssText = 'display: flex; gap: 8px; align-items: center; margin-bottom: 6px;';
  row.innerHTML = `
    <input type="text" class="form-control campo-extra-key" placeholder="Nome campo (es. Luogo, Referente, Cosa Portare)" value="${escapeHtml(chiave)}" style="flex: 1; font-size: 12.5px;">
    <input type="text" class="form-control campo-extra-val" placeholder="Valore (es. Salone, Don Marco)" value="${escapeHtml(valore)}" style="flex: 1.5; font-size: 12.5px;">
    <button type="button" class="btn btn-sm btn-danger" style="padding: 4px 8px; font-weight: bold;" onclick="this.parentElement.remove()" title="Rimuovi campo">×</button>
  `;
  return row;
}

function raccogliCampiExtraDaContainer(containerId) {
  const container = document.getElementById(containerId);
  const result = {};
  if (!container) return result;
  const rows = container.querySelectorAll('.campo-extra-row');
  rows.forEach(r => {
    const k = (r.querySelector('.campo-extra-key')?.value || '').trim();
    const v = (r.querySelector('.campo-extra-val')?.value || '').trim();
    if (k) {
      result[k] = v;
    }
  });
  return result;
}

// ================= AZIONI UTENTE: DISISCRIZIONE & ISCRIZIONE CATECHISMO =================
async function annullaMiaIscrizione(id, titolo) {
  if (!titolo) {
    const iscr = (cacheIscrizioni || []).find(x => x.id === id);
    titolo = iscr ? iscr.attivita_titolo : 'questa attività';
  }
  if (!confirm(`Sei sicuro di voler annullare la tua iscrizione a "${titolo}"?`)) return;
  try {
    const res = await fetch(`/api/iscrizioni/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore durante la disiscrizione');
    showToast(data.message || 'Iscrizione annullata con successo', 'success');
    await loadFamilyIscrizioni();
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalIscrizioneCatechismo(defaultCF = null) {
  let catAtt = (cacheAttivita || []).find(a => a.categoria === 'catechismo');
  if (!catAtt) {
    try {
      const res = await fetch('/api/attivita');
      const data = await res.json();
      catAtt = (data.attivita || []).find(a => a.categoria === 'catechismo');
    } catch (e) {
      console.error(e);
    }
  }

  if (catAtt) {
    openModalNuovaIscrizione(catAtt.id, defaultCF);
  } else {
    openModalNuovaIscrizione(null, defaultCF);
  }
}

// ================= ASSEGNAZIONE DI MASSA (CATECHISMO, DOPOSCUOLA, ORATORIO) =================
let cacheMassaPersone = [];
let currentMassaTipo = 'catechismo'; // 'catechismo' | 'doposcuola' | 'oratorio_estivo' | 'oratorio_invernale'
let currentMassaFiltroEta = ''; // '' | 'primaria' | 'medie' | 'superiori'
let cacheAssegnatiMassaMap = new Set();
let cacheGruppoMassaMap = new Map();

async function openModalAssegnaPersoneMassa(tipo = 'catechismo') {
  currentMassaTipo = tipo;
  currentMassaFiltroEta = '';
  const tipoInput = document.getElementById('massaTipoGruppo');
  if (tipoInput) tipoInput.value = tipo;

  const titleEl = document.getElementById('massaModalTitle');
  if (titleEl) {
    if (tipo === 'catechismo') {
      titleEl.innerHTML = '<i>👥</i> Assegnazione di Massa Ragazzi a Gruppo Catechismo';
    } else if (tipo === 'doposcuola') {
      titleEl.innerHTML = '<i>👥</i> Assegnazione di Massa Studenti a Gruppo Doposcuola';
    } else if (tipo === 'oratorio_estivo') {
      titleEl.innerHTML = '<i>☀️</i> Assegnazione di Massa Ragazzi a Oratorio Estivo';
    } else {
      titleEl.innerHTML = '<i>❄️</i> Assegnazione di Massa Ragazzi a Oratorio Invernale';
    }
  }

  // Mostra subito il modal con indicatore di caricamento per risposta immediata al click
  const tbody = document.getElementById('massaTablePersoneBody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--ink-500);"><div class="spinner" style="margin: 0 auto 10px;"></div>Caricamento anagrafica e gruppi...</td></tr>';
  }
  const selectGruppo = document.getElementById('massaSelectGruppoDestinazione');
  if (selectGruppo) {
    selectGruppo.innerHTML = '<option value="">Caricamento gruppi...</option>';
  }

  openModal('modalAssegnazioneMassa');

  // Reset controlli filtro
  const searchInput = document.getElementById('massaSearchPersone');
  if (searchInput) searchInput.value = '';
  const soloNonAss = document.getElementById('massaSoloNonAssegnati');
  if (soloNonAss) soloNonAss.checked = false;
  const selectAll = document.getElementById('massaSelectAll');
  if (selectAll) selectAll.checked = false;

  document.querySelectorAll('.massa-eta-btn').forEach(btn => {
    btn.className = 'btn btn-sm btn-secondary massa-eta-btn';
  });
  const defaultEtaBtn = document.querySelector('.massa-eta-btn');
  if (defaultEtaBtn) defaultEtaBtn.className = 'btn btn-sm btn-primary massa-eta-btn active';

  cacheAssegnatiMassaMap = new Set();
  cacheGruppoMassaMap = new Map();

  try {
    let gruppiUrl = '/api/catechismo/gruppi';
    if (tipo === 'doposcuola') gruppiUrl = '/api/doposcuola/gruppi';
    else if (tipo.startsWith('oratorio')) gruppiUrl = '/api/oratorio/gruppi';

    const [resG, resP] = await Promise.all([
      fetch(gruppiUrl),
      fetch('/api/persone')
    ]);

    const dataG = await resG.json();
    const dataP = await resP.json();

    cacheMassaPersone = dataP.persone || [];

    if (selectGruppo) {
      selectGruppo.innerHTML = '<option value="">-- Seleziona il gruppo di destinazione --</option>';
    }

    if (tipo === 'catechismo') {
      cacheGruppiCatechismo = dataG.gruppi || [];
      if (selectGruppo) {
        cacheGruppiCatechismo.forEach(g => {
          selectGruppo.innerHTML += `<option value="${g.id}">${escapeHtml(g.nome)} (${escapeHtml(g.anno_pastorale || '2026/2027')}) - ${escapeHtml(g.catechista_nome || 'Da assegnare')}</option>`;
          (g.ragazzi || []).forEach(r => {
            cacheAssegnatiMassaMap.add(r.codice_fiscale);
            cacheGruppoMassaMap.set(r.codice_fiscale, g.nome);
          });
        });
      }
    } else if (tipo === 'doposcuola') {
      cacheGruppiDoposcuola = dataG.gruppi || [];
      if (selectGruppo) {
        cacheGruppiDoposcuola.forEach(g => {
          selectGruppo.innerHTML += `<option value="${g.id}">${escapeHtml(g.nome)} (${escapeHtml(g.anno_scolastico || '2026/2027')}) - ${escapeHtml(g.educatore_nome || 'Da assegnare')}</option>`;
          (g.studenti || []).forEach(s => {
            cacheAssegnatiMassaMap.add(s.codice_fiscale);
            cacheGruppoMassaMap.set(s.codice_fiscale, g.nome);
          });
        });
      }
    } else {
      let gruppiOratorio = dataG.gruppi || [];
      if (tipo === 'oratorio_estivo') {
        const estivi = gruppiOratorio.filter(g => (g.tipo_oratorio || 'estivo').toLowerCase() === 'estivo');
        if (estivi.length > 0) gruppiOratorio = estivi;
      } else if (tipo === 'oratorio_invernale') {
        const invernali = gruppiOratorio.filter(g => (g.tipo_oratorio || '').toLowerCase() === 'invernale');
        if (invernali.length > 0) gruppiOratorio = invernali;
      }
      if (selectGruppo) {
        gruppiOratorio.forEach(g => {
          const isEst = (g.tipo_oratorio || 'estivo').toLowerCase() === 'estivo';
          const icon = isEst ? '☀️ [Estivo]' : '❄️ [Invernale]';
          selectGruppo.innerHTML += `<option value="${g.id}">${icon} ${escapeHtml(g.nome)} (${escapeHtml(g.anno_pastorale || '2026/2027')}) - Animatori: ${escapeHtml(g.animatori_nomi || 'In definizione')}</option>`;
          (g.ragazzi || []).forEach(r => {
            cacheAssegnatiMassaMap.add(r.codice_fiscale);
            cacheGruppoMassaMap.set(r.codice_fiscale, `${g.nome} (${isEst ? 'Estivo' : 'Invernale'})`);
          });
        });
      }
    }

    filtraPersoneMassa();
  } catch (err) {
    console.error('Errore assegnazione massa:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 20px;">Errore caricamento dati: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function selezionaFiltroEtaMassa(filtro) {
  currentMassaFiltroEta = filtro;
  document.querySelectorAll('.massa-eta-btn').forEach(btn => {
    const t = btn.textContent.toLowerCase();
    if ((!filtro && t === 'tutti') ||
        (filtro === 'primaria' && t.includes('primaria')) ||
        (filtro === 'medie' && t.includes('medie')) ||
        (filtro === 'superiori' && t.includes('15+'))) {
      btn.className = 'btn btn-sm btn-primary massa-eta-btn active';
    } else {
      btn.className = 'btn btn-sm btn-secondary massa-eta-btn';
    }
  });
  filtraPersoneMassa();
}

function filtraPersoneMassa() {
  const q = (document.getElementById('massaSearchPersone')?.value || '').toLowerCase().trim();
  const soloNonAss = document.getElementById('massaSoloNonAssegnati')?.checked || false;

  const filtrati = cacheMassaPersone.filter(p => {
    // Ricerca testo
    if (q) {
      const match = (p.nominativo || '').toLowerCase().includes(q) ||
                    (p.codice_fiscale || '').toLowerCase().includes(q) ||
                    (p.nome_famiglia || '').toLowerCase().includes(q);
      if (!match) return false;
    }

    // Filtro Età
    const eta = p.eta;
    if (currentMassaFiltroEta === 'primaria') {
      if (eta === null || eta < 6 || eta > 10) return false;
    } else if (currentMassaFiltroEta === 'medie') {
      if (eta === null || eta < 11 || eta > 14) return false;
    } else if (currentMassaFiltroEta === 'superiori') {
      if (eta === null || eta < 15) return false;
    }

    // Filtro solo non ancora assegnati
    if (soloNonAss) {
      if (cacheAssegnatiMassaMap.has(p.codice_fiscale)) return false;
    }

    return true;
  });

  const tbody = document.getElementById('massaTablePersoneBody');
  if (!tbody) return;

  if (!filtrati.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--ink-500);">Nessuna persona corrispondente ai filtri impostati.</td></tr>';
    aggiornaContatoreMassa();
    return;
  }

  tbody.innerHTML = filtrati.map(p => {
    const cf = p.codice_fiscale;
    const gruppoAttuale = cacheGruppoMassaMap.get(cf) || null;
    return `
      <tr>
        <td style="text-align: center;">
          <input type="checkbox" class="massa-persona-chk" value="${cf}" onchange="aggiornaContatoreMassa()">
        </td>
        <td><strong>${escapeHtml(p.nominativo)}</strong></td>
        <td><code>${escapeHtml(cf)}</code></td>
        <td>${p.eta !== null ? `<strong>${p.eta} anni</strong>` : '<span style="color:var(--ink-500);">N/D</span>'}</td>
        <td>${escapeHtml(p.nome_famiglia || '-')}</td>
        <td>
          ${gruppoAttuale 
            ? `<span class="badge badge-info" style="font-size: 11px;">${escapeHtml(gruppoAttuale)}</span>` 
            : '<span style="color:var(--ink-500); font-size:12px;">Non assegnato</span>'}
        </td>
      </tr>
    `;
  }).join('');

  aggiornaContatoreMassa();
}

function toggleSelectAllMassa(masterCheckbox) {
  const chks = document.querySelectorAll('.massa-persona-chk');
  chks.forEach(c => c.checked = masterCheckbox.checked);
  aggiornaContatoreMassa();
}

function aggiornaContatoreMassa() {
  const chks = document.querySelectorAll('.massa-persona-chk:checked');
  const count = chks.length;
  const counterEl = document.getElementById('massaSelezionatiCounter');
  if (counterEl) {
    counterEl.textContent = `${count} ${count === 1 ? 'selezionato' : 'selezionati'}`;
  }
}

async function handleSalvaAssegnazioneMassa(e) {
  e.preventDefault();
  const destId = document.getElementById('massaSelectGruppoDestinazione').value;
  if (!destId) {
    showToast('Seleziona il gruppo di destinazione', 'warning');
    return;
  }

  const chks = document.querySelectorAll('.massa-persona-chk:checked');
  const cfs = Array.from(chks).map(c => c.value);
  if (!cfs.length) {
    showToast('Seleziona almeno una persona da assegnare', 'warning');
    return;
  }

  const tipo = document.getElementById('massaTipoGruppo').value;
  let url = `/api/catechismo/gruppi/${destId}/ragazzi/batch`;
  if (tipo === 'doposcuola') {
    url = `/api/doposcuola/gruppi/${destId}/studenti/batch`;
  } else if (tipo.startsWith('oratorio')) {
    url = `/api/oratorio/gruppi/${destId}/ragazzi/batch`;
  }

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codici_fiscali: cfs })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore durante l\'assegnazione');

    showToast(data.message || `${cfs.length} persone assegnate con successo!`, 'success');
    closeModal('modalAssegnazioneMassa');

    if (tipo === 'catechismo') {
      await loadCatechismo();
    } else if (tipo === 'doposcuola') {
      await loadDoposcuola();
    } else {
      await loadOratorio();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= ISCRIZIONE FIGLIO A CATECHISMO & DOPOSCUOLA (GENITORE) =================
let cacheGruppiIscrizioneFiglioCat = [];
let cacheGruppiIscrizioneFiglioDop = [];

async function openModalIscriviFiglioCatechismo(cf, nominativo) {
  document.getElementById('iscriviFiglioCatCF').value = cf;
  document.getElementById('iscriviFiglioCatNominativo').textContent = nominativo;

  const sel = document.getElementById('iscriviFiglioCatGruppoSelect');
  sel.innerHTML = '<option value="">Caricamento gruppi...</option>';
  const preview = document.getElementById('iscriviFiglioCatPreviewInfo');
  preview.innerHTML = '';

  try {
    const res = await fetch('/api/catechismo/miei-figli');
    const data = await res.json();
    cacheGruppiIscrizioneFiglioCat = data.gruppi_disponibili || [];

    if (!cacheGruppiIscrizioneFiglioCat.length) {
      sel.innerHTML = '<option value="">Nessun gruppo di catechismo disponibile</option>';
      return;
    }

    sel.innerHTML = '<option value="">-- Scegli il gruppo di catechismo --</option>' +
      cacheGruppiIscrizioneFiglioCat.map(g => `
        <option value="${g.id}">
          ${escapeHtml(g.nome)} (${escapeHtml(g.anno_pastorale)}) · Catechista: ${escapeHtml(g.catechista_nome)}
        </option>
      `).join('');

    sel.onchange = function() {
      const gId = parseInt(this.value);
      const g = cacheGruppiIscrizioneFiglioCat.find(x => x.id === gId);
      if (g) {
        preview.innerHTML = `
          <strong>Orario incontri:</strong> ${escapeHtml(g.orario_incontri || 'In definizione')}<br>
          <strong>Aula / Luogo:</strong> ${escapeHtml(g.aula || 'Chiesa / Oratorio')}<br>
          <strong>Catechista:</strong> ${escapeHtml(g.catechista_nome)}
        `;
      } else {
        preview.innerHTML = '';
      }
    };
  } catch (err) {
    console.error('Errore caricamento gruppi catechismo:', err);
  }

  openModal('modalIscriviFiglioCatechismo');
}

async function handleSalvaIscrizioneFiglioCatechismo(e) {
  e.preventDefault();
  const cf = document.getElementById('iscriviFiglioCatCF').value;
  const gruppoId = parseInt(document.getElementById('iscriviFiglioCatGruppoSelect').value);

  if (!gruppoId) {
    showToast('Seleziona un gruppo di catechismo', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/catechismo/iscrivi-figlio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf, gruppo_id: gruppoId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore iscrizione');

    showToast(data.message, 'success');
    closeModal('modalIscriviFiglioCatechismo');
    await loadCatechismoParentView();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalIscriviFiglioDoposcuola(cf, nominativo) {
  document.getElementById('iscriviFiglioDopCF').value = cf;
  document.getElementById('iscriviFiglioDopNominativo').textContent = nominativo;

  const sel = document.getElementById('iscriviFiglioDopGruppoSelect');
  sel.innerHTML = '<option value="">Caricamento gruppi...</option>';
  const preview = document.getElementById('iscriviFiglioDopPreviewInfo');
  preview.innerHTML = '';

  try {
    const res = await fetch('/api/doposcuola/miei-figli');
    const data = await res.json();
    cacheGruppiIscrizioneFiglioDop = data.gruppi_disponibili || [];

    if (!cacheGruppiIscrizioneFiglioDop.length) {
      sel.innerHTML = '<option value="">Nessun gruppo doposcuola disponibile</option>';
      return;
    }

    sel.innerHTML = '<option value="">-- Scegli il gruppo doposcuola --</option>' +
      cacheGruppiIscrizioneFiglioDop.map(g => `
        <option value="${g.id}">
          ${escapeHtml(g.nome)} (${escapeHtml(g.anno_scolastico)}) · Educatore: ${escapeHtml(g.educatore_nome)}
        </option>
      `).join('');

    sel.onchange = function() {
      const gId = parseInt(this.value);
      const g = cacheGruppiIscrizioneFiglioDop.find(x => x.id === gId);
      if (g) {
        preview.innerHTML = `
          <strong>Fascia d'età:</strong> ${escapeHtml(g.fascia_eta || 'Tutti')}<br>
          <strong>Orario & Giorni:</strong> ${escapeHtml(g.giorni_orari || 'Pomeriggio')}<br>
          <strong>Aula:</strong> ${escapeHtml(g.aula || 'Salone')}<br>
          <strong>Educatore:</strong> ${escapeHtml(g.educatore_nome)}
        `;
      } else {
        preview.innerHTML = '';
      }
    };
  } catch (err) {
    console.error('Errore caricamento gruppi doposcuola:', err);
  }

  openModal('modalIscriviFiglioDoposcuola');
}

async function handleSalvaIscrizioneFiglioDoposcuola(e) {
  e.preventDefault();
  const cf = document.getElementById('iscriviFiglioDopCF').value;
  const gruppoId = parseInt(document.getElementById('iscriviFiglioDopGruppoSelect').value);

  if (!gruppoId) {
    showToast('Seleziona un gruppo di doposcuola', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/doposcuola/iscrivi-figlio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codice_fiscale: cf, gruppo_id: gruppoId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore iscrizione');

    showToast(data.message, 'success');
    closeModal('modalIscriviFiglioDoposcuola');
    await loadDoposcuolaParentView();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= GESTIONE BADGE & LISTE (INDIVIDUALE E DI MASSA) =================
let currentGestisciBadgePersonaId = null;

async function openModalGestisciBadgePersona(personaId) {
  currentGestisciBadgePersonaId = personaId;
  document.getElementById('gestisciBadgePersonaId').value = personaId;

  const container = document.getElementById('gestisciBadgeCheckboxList');
  container.innerHTML = '<div style="padding:16px; text-align:center;">Caricamento badge...</div>';
  openModal('modalGestisciBadgePersona');

  try {
    const [listeRes, persRes] = await Promise.all([
      fetch('/api/liste'),
      fetch(`/api/persone/${personaId}`)
    ]);

    const listeData = await listeRes.json();
    const persData = await persRes.json();

    const liste = listeData.liste || [];
    const persona = persData.persona || {};

    const nameEl = document.getElementById('gestisciBadgePersonaNome');
    if (nameEl) nameEl.textContent = `Persona: ${persona.nominativo || ''} (${persona.codice_fiscale || ''})`;

    const assignedIds = new Set((persona.badges || persona.liste || []).map(l => l.id));

    if (!liste.length) {
      container.innerHTML = '<div style="color:var(--ink-500); padding:10px;">Nessun badge o lista parrocchiale configurata. Creane uno nella sezione Segreteria > Liste.</div>';
      return;
    }

    container.innerHTML = liste.map(l => `
      <label style="display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer; padding:6px; border-radius:4px; background:#f8fafc; border:1px solid var(--border-light);">
        <input type="checkbox" class="badge-persona-chk" value="${l.id}" ${assignedIds.has(l.id) ? 'checked' : ''}>
        <span style="font-size:16px;">${l.icona || '🏅'}</span>
        <div style="flex:1;">
          <strong style="color:${l.colore || 'var(--ink-900)'};">${escapeHtml(l.nome)}</strong>
          ${l.descrizione ? `<small style="display:block; color:var(--ink-500); font-size:11px;">${escapeHtml(l.descrizione)}</small>` : ''}
        </div>
      </label>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div style="color:var(--danger); padding:10px;">Errore: ${escapeHtml(err.message)}</div>`;
  }
}

async function handleSalvaBadgePersona(e) {
  e.preventDefault();
  const personaId = currentGestisciBadgePersonaId;
  if (!personaId) return;

  const chks = document.querySelectorAll('.badge-persona-chk');
  
  try {
    // Sincronizza lo stato delle liste per questa persona
    for (const chk of chks) {
      const listaId = chk.value;
      const isChecked = chk.checked;
      
      if (isChecked) {
        await fetch(`/api/liste/${listaId}/membri`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ persona_id: personaId })
        });
      } else {
        await fetch(`/api/liste/${listaId}/membri/${personaId}`, {
          method: 'DELETE'
        });
      }
    }

    showToast('Badge aggiornati con successo!', 'success');
    closeModal('modalGestisciBadgePersona');
    
    // Ricarica la scheda persona se aperta
    if (currentViewingPersonaCF) {
      await apriSchedaVisualizzazionePersona(currentViewingPersonaCF);
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalAssegnaBadgeMassa() {
  const selectedCfs = Array.from(selectedPersoneAnagrafica || []);
  if (!selectedCfs.length) {
    showToast('Seleziona prima almeno una persona dall\'anagrafica', 'warning');
    return;
  }

  document.getElementById('massaBadgeCountLabel').textContent = `${selectedCfs.length} ${selectedCfs.length === 1 ? 'persona selezionata' : 'persone selezionate'}`;

  const sel = document.getElementById('selectMassaBadgeDestinazione');
  sel.innerHTML = '<option value="">Caricamento badge e liste...</option>';
  openModal('modalAssegnaBadgeMassa');

  try {
    const res = await fetch('/api/liste');
    const data = await res.json();
    const liste = data.liste || [];

    if (!liste.length) {
      sel.innerHTML = '<option value="">Nessun badge configurato</option>';
      return;
    }

    sel.innerHTML = '<option value="">-- Seleziona Badge / Lista --</option>' +
      liste.map(l => `
        <option value="${l.id}">${l.icona || '🏅'} ${escapeHtml(l.nome)} (${l.num_membri || 0} assegnati)</option>
      `).join('');
  } catch (err) {
    console.error('Errore badge:', err);
  }
}

async function handleSalvaAssegnaBadgeMassa(e) {
  e.preventDefault();
  const listaId = document.getElementById('selectMassaBadgeDestinazione').value;
  if (!listaId) {
    showToast('Seleziona il badge di destinazione', 'warning');
    return;
  }

  const selectedCfs = Array.from(selectedPersoneAnagrafica || []);
  if (!selectedCfs.length) {
    showToast('Nessuna persona selezionata', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/liste/assegna-massa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lista_id: parseInt(listaId),
        codici_fiscali: selectedCfs
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore assegnazione badge');

    showToast(data.message || 'Badge assegnato con successo!', 'success');
    closeModal('modalAssegnaBadgeMassa');
    deselezionaTuttePersone();
    await loadSegreteria();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function openModalGeneraBadgeAutomatica() {
  const optgroup = document.getElementById('optgroupBadgeAttivita');
  if (optgroup) {
    optgroup.innerHTML = '<option value="">Caricamento attività...</option>';
  }

  openModal('modalGeneraBadgeAutomatica');

  try {
    const res = await fetch('/api/attivita');
    const data = await res.json();
    const atts = data.attivita || [];

    if (optgroup) {
      if (!atts.length) {
        optgroup.innerHTML = '<option disabled>Nessuna attività registrata</option>';
      } else {
        optgroup.innerHTML = atts.map(a => `
          <option value="attivita_${a.id}">🎯 ${escapeHtml(a.titolo)} (${escapeHtml(a.categoria)})</option>
        `).join('');
      }
    }

    aggiornaAnteprimaNomeBadge();
  } catch (err) {
    console.error('Errore caricamento attività per badge:', err);
  }
}

function aggiornaAnteprimaNomeBadge() {
  const sel = document.getElementById('selectFonteBadgeAutomatica');
  const nomeInput = document.getElementById('inputNomeBadgeGenerato');
  const descInput = document.getElementById('inputDescBadgeGenerato');
  const iconaInput = document.getElementById('inputIconaBadgeGenerato');
  if (!sel || !nomeInput) return;

  const val = sel.value;
  if (val === 'oratorio_estivo') {
    nomeInput.value = 'Iscritti Oratorio Estivo 2026/2027';
    descInput.value = 'Partecipanti all\'Estate Ragazzi e Oratorio Estivo Sacro Cuore';
    iconaInput.value = '☀️';
  } else if (val === 'oratorio_invernale') {
    nomeInput.value = 'Iscritti Oratorio Invernale 2026/2027';
    descInput.value = 'Partecipanti alle attività del sabato e domenicali dell\'Oratorio Invernale';
    iconaInput.value = '❄️';
  } else if (val === 'catechismo') {
    nomeInput.value = 'Iscritti Catechismo 2026/2027';
    descInput.value = 'Bambini e ragazzi iscritti ai cammini di catechismo parrocchiale';
    iconaInput.value = '📖';
  } else if (val === 'doposcuola') {
    nomeInput.value = 'Iscritti Doposcuola 2026/2027';
    descInput.value = 'Studenti iscritti alle attività di studio pomeridiano e doposcuola';
    iconaInput.value = '📚';
  } else if (val.startsWith('attivita_')) {
    const text = sel.selectedOptions[0]?.text || 'Attività';
    nomeInput.value = `Partecipanti ${text.replace('🎯', '').trim()}`;
    descInput.value = `Badge guadagnato per la partecipazione all'attività ${text.replace('🎯', '').trim()}`;
    iconaInput.value = '🏅';
  }
}

async function handleSalvaGeneraBadgeAutomatica(e) {
  e.preventDefault();
  const fonte = document.getElementById('selectFonteBadgeAutomatica').value;
  const nome = document.getElementById('inputNomeBadgeGenerato').value.trim();
  const icona = document.getElementById('inputIconaBadgeGenerato').value;
  const colore = document.getElementById('inputColoreBadgeGenerato').value;
  const descrizione = document.getElementById('inputDescBadgeGenerato').value.trim();

  let fonte_tipo = 'oratorio_estivo';
  let attivita_id = null;

  if (fonte.startsWith('attivita_')) {
    fonte_tipo = 'attivita';
    attivita_id = parseInt(fonte.replace('attivita_', ''));
  } else {
    fonte_tipo = fonte;
  }

  const payload = {
    nome,
    icona,
    colore,
    descrizione,
    fonte_tipo,
    attivita_id
  };

  try {
    const res = await fetch('/api/liste/genera-automatica', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Errore generazione badge');

    showToast(data.message || 'Badge generato con successo!', 'success');
    closeModal('modalGeneraBadgeAutomatica');
    await loadSegreteria();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= OFFERTE & DONAZIONI (SATISPAY, IBAN, QUADRO FAMIGLIA) =================
let cacheInfoOfferte = null;

async function caricaTotaleOfferteCard() {
  try {
    const res = await fetch('/api/famiglie/offerte');
    const data = await res.json();
    cacheInfoOfferte = data;
    const kpiEl = document.getElementById('kpiMioTotOfferto');
    if (kpiEl) {
      kpiEl.textContent = `€ ${(data.totale_offerto || 0).toFixed(2)}`;
    }
  } catch (err) {
    console.error('Errore caricamento totale offerte:', err);
  }
}

async function openModalOfferteDonazioni() {
  openModal('modalOfferteDonazioni');
  const tbody = document.getElementById('storicoOfferteBody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--ink-500); padding: 18px;"><div class="spinner" style="margin: 0 auto 8px;"></div>Caricamento quadro offerte e donazioni...</td></tr>';
  }

  try {
    const res = await fetch('/api/famiglie/offerte');
    const data = await res.json();
    cacheInfoOfferte = data;

    const info = data.info_pagamento || {};
    const satispayLink = document.getElementById('offerteSatispayLink');
    if (satispayLink) {
      satispayLink.href = info.satispay_url || 'https://tag.satispay.com/sacrocuoreasti';
    }

    const ibanText = document.getElementById('offerteIbanText');
    if (ibanText) {
      ibanText.textContent = info.iban || 'IT60X0542811101000000123456';
    }

    const intestatarioEl = document.getElementById('offerteIntestatario');
    if (intestatarioEl) {
      intestatarioEl.textContent = info.intestatario || 'Parrocchia Sacro Cuore di Gesù - Asti';
    }

    const causaleEl = document.getElementById('offerteCausale');
    if (causaleEl) {
      causaleEl.textContent = info.causale_predefinita || 'Offerta liberale per le attività parrocchiali';
    }

    const totEl = document.getElementById('offerteTotaleVersato');
    if (totEl) {
      totEl.textContent = `€ ${(data.totale_offerto || 0).toFixed(2)}`;
    }

    const kpiEl = document.getElementById('kpiMioTotOfferto');
    if (kpiEl) {
      kpiEl.textContent = `€ ${(data.totale_offerto || 0).toFixed(2)}`;
    }

    const storico = data.storico_versamenti || [];
    if (!tbody) return;

    if (!storico.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; padding: 22px; color: var(--ink-500); font-style: italic;">
            Nessuna quota o offerta registrata al momento. Le quote e donazioni compariranno qui una volta registrate.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = storico.map(item => `
      <tr>
        <td style="white-space: nowrap; font-weight: 600; color: var(--ink-700);">${escapeHtml(item.data || '-')}</td>
        <td>
          <div style="font-weight: 700; color: var(--ink-900);">${escapeHtml(item.descrizione)}</div>
          <small style="color: var(--ink-500);">${escapeHtml(item.tipo)}</small>
        </td>
        <td><span class="badge badge-neutral" style="font-size: 11px;">${escapeHtml(item.metodo || 'Satispay/Bonifico')}</span></td>
        <td style="text-align: right; font-weight: 700; color: #166534; font-size: 13.5px; white-space: nowrap;">
          + € ${(item.importo || 0).toFixed(2)}
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Errore quadro offerte:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 18px;">Errore caricamento dati: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function copiaIbanOfferte() {
  const ibanText = document.getElementById('offerteIbanText')?.textContent || '';
  if (!ibanText) return;

  navigator.clipboard.writeText(ibanText.replace(/\s+/g, '')).then(() => {
    showToast('IBAN copiato negli appunti! 📋', 'success');
  }).catch(() => {
    // Fallback
    const input = document.createElement('input');
    input.value = ibanText.replace(/\s+/g, '');
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    showToast('IBAN copiato negli appunti! 📋', 'success');
  });
}

// ================= GESTIONE CALENDARI GOOGLE COMUNITARI =================
let cacheSegreteriaCalendari = [];

async function loadPublicCalendari() {
  const grid = document.getElementById('publicCalendariGrid');
  if (!grid) return;
  try {
    const res = await fetch('/api/impostazioni/calendari?solo_pubblici=true');
    const data = await res.json();
    const calendari = data.calendari || [];
    if (!calendari.length) {
      grid.innerHTML = `
        <div style="grid-column: 1/-1; padding: 24px; text-align: center; color: var(--ink-500); background: #fff; border-radius: var(--radius-md); border: 1px solid var(--border-light);">
          Nessun calendario pubblico attualmente configurato.
        </div>
      `;
      return;
    }
    grid.innerHTML = calendari.map(c => `
      <div class="public-card" style="border-top: 4px solid ${escapeHtml(c.colore)}; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 24px;">${escapeHtml(c.icona || '📅')}</span>
              <h3 style="font-size: 17px; font-weight: 700; color: var(--ink-900); margin: 0;">${escapeHtml(c.titolo)}</h3>
            </div>
            <span class="badge" style="background: ${escapeHtml(c.colore)}; color: #fff; font-size: 10.5px;">${escapeHtml((c.categoria || 'parrocchia').toUpperCase())}</span>
          </div>
          ${c.descrizione ? `<p style="font-size: 13px; color: var(--ink-700); line-height: 1.5; margin-bottom: 14px;">${escapeHtml(c.descrizione)}</p>` : ''}
        </div>
        <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border-light); display: flex; gap: 8px;">
          <a href="${escapeHtml(c.google_calendar_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary" style="width: 100%; text-align: center; justify-content: center; background: ${escapeHtml(c.colore)}; border-color: ${escapeHtml(c.colore)}; font-weight: 600;">
            📅 Apri / Aggiungi a Google Calendar ↗
          </a>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Errore caricamento calendari pubblici:', err);
  }
}

async function loadUserCalendari() {
  const container = document.getElementById('dashUserCalendariGrid');
  if (!container) return;
  try {
    const res = await fetch('/api/impostazioni/calendari?solo_pubblici=true');
    const data = await res.json();
    const calendari = data.calendari || [];
    if (!calendari.length) {
      container.innerHTML = `<div style="grid-column: 1/-1; padding: 16px; color: var(--ink-500); text-align: center;">Nessun calendario parrocchiale attivo al momento.</div>`;
      return;
    }
    container.innerHTML = calendari.map(c => `
      <div style="background: #fff; border: 1.5px solid var(--border-light); border-left: 5px solid ${escapeHtml(c.colore)}; border-radius: var(--radius-md); padding: 14px 16px; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 20px;">${escapeHtml(c.icona || '📅')}</span>
              <strong style="font-size: 14.5px; color: var(--ink-900);">${escapeHtml(c.titolo)}</strong>
            </div>
            <span class="badge" style="background: ${escapeHtml(c.colore)}; color: #fff; font-size: 10px;">${escapeHtml((c.categoria || 'parrocchia').toUpperCase())}</span>
          </div>
          ${c.descrizione ? `<p style="font-size: 12px; color: var(--ink-600); margin: 0 0 10px 0; line-height: 1.4;">${escapeHtml(c.descrizione)}</p>` : ''}
        </div>
        <div style="margin-top: 10px; display: flex; gap: 8px;">
          <a href="${escapeHtml(c.google_calendar_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-xs btn-outline-primary" style="width: 100%; text-align: center; justify-content: center; font-weight: 600;">
            📅 Sincronizza con Google Calendar ↗
          </a>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Errore calendari dashboard:', err);
  }
}

async function loadSegreteriaCalendari() {
  const tbody = document.getElementById('tbodySegreteriaCalendari');
  if (!tbody) return;
  try {
    const res = await fetch('/api/impostazioni/calendari');
    const data = await res.json();
    cacheSegreteriaCalendari = data.calendari || [];
    if (!cacheSegreteriaCalendari.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--ink-500); padding: 18px;">Nessun calendario Google configurato. Clicca "+ Nuovo Calendario".</td></tr>';
      return;
    }
    tbody.innerHTML = cacheSegreteriaCalendari.map(c => `
      <tr>
        <td>
          <span style="font-size: 18px; margin-right: 6px;">${escapeHtml(c.icona || '📅')}</span>
          <strong>${escapeHtml(c.titolo)}</strong>
          ${c.descrizione ? `<br><small style="color: var(--ink-500);">${escapeHtml(c.descrizione)}</small>` : ''}
        </td>
        <td><span class="badge badge-neutral">${escapeHtml((c.categoria || 'parrocchia').toUpperCase())}</span></td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: ${escapeHtml(c.colore)};"></span>
            <code>${escapeHtml(c.colore)}</code>
          </div>
        </td>
        <td>
          <a href="${escapeHtml(c.google_calendar_url)}" target="_blank" style="color: var(--primary); text-decoration: underline; font-size: 12px; word-break: break-all;">
            Link Google Calendar ↗
          </a>
        </td>
        <td>
          ${c.is_pubblico ? '<span class="badge badge-success">Pubblico</span>' : '<span class="badge badge-warning">Nascosto</span>'}
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-xs btn-secondary" onclick="openModalModificaCalendario(${c.id})">✏️ Modifica</button>
            <button class="btn btn-xs btn-danger" onclick="eliminaCalendario(${c.id})">🗑 Elimina</button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Errore calendari segreteria:', err);
  }
}

function openModalNuovoCalendario() {
  document.getElementById('modalCalTitle').textContent = '📅 Nuovo Calendario Google Parrocchiale';
  document.getElementById('inputCalId').value = '';
  document.getElementById('inputCalTitolo').value = '';
  document.getElementById('inputCalDescrizione').value = '';
  document.getElementById('inputCalUrl').value = '';
  document.getElementById('inputCalColore').value = '#8B1E1E';
  document.getElementById('inputCalIcona').value = '📅';
  document.getElementById('inputCalCategoria').value = 'parrocchia';
  document.getElementById('inputCalOrdine').value = '0';
  document.getElementById('inputCalPubblico').checked = true;
  openModal('modalCalendarioComunita');
}

function openModalModificaCalendario(id) {
  const c = cacheSegreteriaCalendari.find(x => x.id === id);
  if (!c) return;
  document.getElementById('modalCalTitle').textContent = `✏️ Modifica Calendario: ${c.titolo}`;
  document.getElementById('inputCalId').value = c.id;
  document.getElementById('inputCalTitolo').value = c.titolo;
  document.getElementById('inputCalDescrizione').value = c.descrizione || '';
  document.getElementById('inputCalUrl').value = c.google_calendar_url;
  document.getElementById('inputCalColore').value = c.colore || '#8B1E1E';
  document.getElementById('inputCalIcona').value = c.icona || '📅';
  document.getElementById('inputCalCategoria').value = c.categoria || 'parrocchia';
  document.getElementById('inputCalOrdine').value = c.ordine || 0;
  document.getElementById('inputCalPubblico').checked = Boolean(c.is_pubblico);
  openModal('modalCalendarioComunita');
}

async function handleSalvaCalendario(e) {
  e.preventDefault();
  const id = document.getElementById('inputCalId').value;
  const payload = {
    titolo: document.getElementById('inputCalTitolo').value.trim(),
    descrizione: document.getElementById('inputCalDescrizione').value.trim(),
    google_calendar_url: document.getElementById('inputCalUrl').value.trim(),
    colore: document.getElementById('inputCalColore').value.trim(),
    icona: document.getElementById('inputCalIcona').value.trim(),
    categoria: document.getElementById('inputCalCategoria').value,
    ordine: parseInt(document.getElementById('inputCalOrdine').value || 0),
    is_pubblico: document.getElementById('inputCalPubblico').checked
  };

  try {
    const url = id ? `/api/impostazioni/calendari/${id}` : '/api/impostazioni/calendari';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore salvataggio calendario');
    showToast(d.message, 'success');
    closeModal('modalCalendarioComunita');
    await loadSegreteriaCalendari();
    await loadPublicCalendari();
    await loadUserCalendari();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function eliminaCalendario(id) {
  if (!confirm('Sei sicuro di voler eliminare questo calendario comunitario?')) return;
  try {
    const res = await fetch(`/api/impostazioni/calendari/${id}`, { method: 'DELETE' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore eliminazione calendario');
    showToast(d.message, 'info');
    await loadSegreteriaCalendari();
    await loadPublicCalendari();
    await loadUserCalendari();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= GESTIONE FOTO PROFILO (AVATAR) =================
function openModalFotoProfilo(cf, nominativo, currentUrl) {
  document.getElementById('fotoProfiloCF').value = cf;
  document.getElementById('fotoProfiloNominativo').textContent = nominativo;
  document.getElementById('fotoProfiloFileInput').value = '';

  const preview = document.getElementById('fotoProfiloPreview');
  const placeholder = document.getElementById('fotoProfiloPlaceholder');
  const btnRimuovi = document.getElementById('btnRimuoviFotoProfilo');

  if (currentUrl && currentUrl.trim() !== '') {
    preview.src = currentUrl;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
    btnRimuovi.style.display = 'inline-block';
  } else {
    preview.src = '';
    preview.style.display = 'none';
    placeholder.style.display = 'block';
    btnRimuovi.style.display = 'none';
  }

  openModal('modalFotoProfilo');
}

function previewFotoProfilo(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {
    const preview = document.getElementById('fotoProfiloPreview');
    const placeholder = document.getElementById('fotoProfiloPlaceholder');
    preview.src = e.target.result;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
  };
  reader.readAsDataURL(file);
}

async function handleSalvaFotoProfilo(e) {
  e.preventDefault();
  const cf = document.getElementById('fotoProfiloCF').value;
  const fileInput = document.getElementById('fotoProfiloFileInput');
  if (!fileInput.files || !fileInput.files[0]) {
    showToast('Seleziona un\'immagine prima di salvare', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('foto', fileInput.files[0]);

  const btn = document.getElementById('btnSalvaFotoProfilo');
  btn.disabled = true;
  btn.textContent = 'Caricamento su Drive...';

  try {
    const res = await fetch(`/api/persone/${cf}/foto-profilo`, {
      method: 'POST',
      body: formData
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore caricamento foto');

    showToast(d.message, 'success');
    closeModal('modalFotoProfilo');

    if (currentUser && currentUser.persona && currentUser.persona.codice_fiscale === cf) {
      currentUser.persona.foto_profilo_url = d.persona.foto_profilo_url;
      renderAppShell();
    }

    if (document.getElementById('viewFamiglia').style.display !== 'none') {
      await loadFamiglia();
    }
    if (document.getElementById('viewAnagrafica').style.display !== 'none') {
      await loadPersone();
    }
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Carica Foto';
  }
}

async function handleRimuoviFotoProfilo() {
  const cf = document.getElementById('fotoProfiloCF').value;
  if (!confirm('Rimuovere la foto profilo?')) return;

  try {
    const res = await fetch(`/api/persone/${cf}/foto-profilo`, { method: 'DELETE' });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Errore rimozione foto');

    showToast(d.message, 'info');
    closeModal('modalFotoProfilo');

    if (currentUser && currentUser.persona && currentUser.persona.codice_fiscale === cf) {
      currentUser.persona.foto_profilo_url = null;
      renderAppShell();
    }

    if (document.getElementById('viewFamiglia').style.display !== 'none') {
      await loadFamiglia();
    }
    if (document.getElementById('viewAnagrafica').style.display !== 'none') {
      await loadPersone();
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}




