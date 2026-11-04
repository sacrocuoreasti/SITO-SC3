/* Viste del portale: date civili italiane e dati caricati solo quando servono. */
function activityIsPast(activity) {
  const end=activity.data_fine || activity.data_inizio;
  return /^\d{4}-\d{2}-\d{2}$/.test(end || '') && end<GroupCalendar.localDate();
}
let dashboardWeekOffset=0;
let dashboardWeekData=null;
function weeklyDays(offset=0) {
  const first=new Date(GroupCalendar.localDate()+'T12:00:00');
  first.setDate(first.getDate()-((first.getDay()+6)%7)+offset*7);
  return Array.from({length:7},(_,i)=>{const d=new Date(first);d.setDate(d.getDate()+i);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;});
}
function celebrationWeekdays(text) {
  const value=(text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const names=['lunedi','martedi','mercoledi','giovedi','venerdi','sabato','domenica'];
  const found=names.map((name,i)=>({i,position:value.indexOf(name)})).filter(x=>x.position>=0).sort((a,b)=>a.position-b.position).map(x=>x.i);
  if(found.length===2 && /[-–]|\bdal\b.*\bal\b/.test(value)) {
    const result=[];let current=found[0];
    for(let i=0;i<7;i++){result.push(current);if(current===found[1])break;current=(current+1)%7;}
    return result;
  }
  if(!found.length && value.includes('ferial'))return [0,1,2,3,4,5];
  return found;
}
function celebrationWhen(celebration) {return celebration.data_specifica?new Date(celebration.data_specifica+'T12:00:00').toLocaleDateString('it-IT'):celebration.giorno||'';}
function noticeDate(notice) {const value=notice.data_evento_iso||notice.data_evento||'';if(/^\d{4}-\d{2}-\d{2}/.test(value))return value.slice(0,10);const match=value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);return match?`${match[3]}-${match[2]}-${match[1]}`:null;}
function celebrationApplies(celebration,day,index) {
  if(celebration.data_specifica)return celebration.data_specifica===day;
  if(!celebrationWeekdays(celebration.giorno).includes(index)) return false;
  const value=(celebration.giorno||'').toLowerCase();
  const date=new Date(day+'T12:00:00');
  const ordinals=[/prim[ao]/,/second[ao]/,/terz[ao]/,/quart[ao]/,/quint[ao]/];
  const ordinal=ordinals.findIndex(pattern=>pattern.test(value));
  if(ordinal>=0 && Math.floor((date.getDate()-1)/7)!==ordinal)return false;
  if(/ultim[ao]/.test(value)){const next=new Date(date);next.setDate(next.getDate()+7);if(next.getMonth()===date.getMonth())return false;}
  return true;
}
// Espande gli orari multipli senza dividere un intervallo (es. 18:00–19:00).
function celebrationSlots(celebration) {
  const text=String(celebration.orario||'').replace(/^ore\s*/i,'');
  const matches=[...text.matchAll(/\b([01]?\d|2[0-3])[:.]([0-5]\d)\b/g)];
  const minutes=match=>Number(match[1])*60+Number(match[2]);
  if(matches.length>1 && !/[-–—]|\balle\b/i.test(text))return matches.map(m=>({...celebration,orario:m[0],minute:minutes(m)}));
  return [{...celebration,orario:text,minute:matches.length?minutes(matches[0]):Infinity}];
}
function celebrationDayEntries(celebrations,day,index) {
  const entries=celebrations.filter(c=>c.is_attivo!==false && celebrationApplies(c,day,index)).flatMap(celebrationSlots);
  const hidden=new Set();
  const place=c=>String(c.luogo||'Chiesa Parrocchiale').trim().toLocaleLowerCase('it-IT');
  for(const event of entries.filter(c=>c.sezione==='avvenimenti' && c.data_specifica && Number.isFinite(c.minute))) {
    const candidates=entries.filter(c=>!c.data_specifica && c.sezione!=='avvenimenti' && !hidden.has(c) && place(c)===place(event) && Math.abs(c.minute-event.minute)<=30);
    candidates.sort((a,b)=>Math.abs(a.minute-event.minute)-Math.abs(b.minute-event.minute) || Number(b.sezione==='messe')-Number(a.sezione==='messe'));
    if(candidates[0])hidden.add(candidates[0]);
  }
  return entries.filter(c=>!hidden.has(c)).sort((a,b)=>a.minute-b.minute || String(a.titolo).localeCompare(String(b.titolo),'it'));
}

function moveDashboardWeek(delta) {
  dashboardWeekOffset=delta===0?0:dashboardWeekOffset+delta;
  if(dashboardWeekData) renderDashboardWeek(...dashboardWeekData);
}
function renderDashboardWeek(celebrations,notices,settings={}) {
  dashboardWeekData=[celebrations,notices,settings];
  const days=weeklyDays(dashboardWeekOffset);
  const masses=settings.mostra_orari_messe===false?[]:celebrations.filter(m=>m.is_attivo!==false);
  const news=settings.mostra_avvisi===false?[]:notices.filter(n=>n.is_pubblicato!==false);
  const format=day=>new Date(day+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'short'});
  document.getElementById('dashWeeklyCalendar').innerHTML=`<div class="weekly-toolbar"><strong>${format(days[0])} – ${format(days[6])}</strong><div><button class="btn btn-sm btn-secondary" type="button" aria-label="Settimana precedente" onclick="moveDashboardWeek(-1)">←</button><button class="btn btn-sm btn-secondary" type="button" onclick="moveDashboardWeek(0)">Questa settimana</button><button class="btn btn-sm btn-secondary" type="button" aria-label="Settimana successiva" onclick="moveDashboardWeek(1)">→</button></div></div>
    <div class="weekly-calendar">${days.map((day,index)=>`<section class="weekly-day ${day===GroupCalendar.localDate()?'is-today':''}"><h4>${escapeHtml(new Date(day+'T12:00:00').toLocaleDateString('it-IT',{weekday:'short',day:'numeric'}))}</h4>${celebrationDayEntries(masses,day,index).map(m=>`<article class="weekly-mass" data-section="${escapeHtml(m.sezione||'messe')}"><strong>${escapeHtml((m.orario||'').replace(/^ore\s*/i,''))}</strong><span>${escapeHtml(m.titolo||'Santa Messa')}</span><small>${escapeHtml(m.luogo||'')}</small>${m.descrizione?`<small>${escapeHtml(m.descrizione)}</small>`:''}</article>`).join('')}${news.filter(n=>noticeDate(n)===day).map(n=>`<article class="weekly-notice"><strong>${escapeHtml(n.titolo)}</strong><p>${escapeHtml(n.contenuto||'')}</p></article>`).join('')}${!masses.some(m=>celebrationApplies(m,day,index)) && !news.some(n=>noticeDate(n)===day)?'<small class="weekly-empty">Nessun appuntamento</small>':''}</section>`).join('')}</div>`;
  const extra=masses.filter(m=>!m.data_specifica && !celebrationWeekdays(m.giorno).length).map(m=>`<article class="weekly-extra"><strong>${escapeHtml(m.titolo)}</strong><p>${escapeHtml(m.giorno||'Data da definire')} · ${escapeHtml(m.orario||'')}</p></article>`).join('');
  document.getElementById('dashAvvisiContainer').innerHTML=extra+news.filter(n=>!noticeDate(n)).map(n=>`<article class="weekly-extra"><strong>${escapeHtml(n.titolo)}</strong><p>${escapeHtml(n.contenuto||'')}</p></article>`).join('');
}
async function openUserEnrollmentManagement(id) {
  try {
  const data=await apiJson('/api/iscrizioni?attivita_id='+id+'&solo_mie=true');
  await refreshEnrollmentOptions();
  const activity=cacheAttivita.find(a=>a.id===id);
  const canAdd=activity && !activityIsPast(activity) && activity.is_attiva!==false && enrollmentOptions?.attivita?.[id]?.partecipanti?.length;
  document.getElementById('partecipantiEventoTitle').textContent='Gestisci iscrizione'+(activity?' · '+activity.titolo:'');
  document.getElementById('partecipantiEventoElenco').innerHTML=(data.iscrizioni||[]).map(record=>`<div class="enrollment-management-person"><div><strong>${escapeHtml(record.partecipante_nome||record.nominativo||'Partecipante')}</strong><p>${escapeHtml(record.stato||'')}</p></div>${withdrawButton(record)}</div>`).join('')+(canAdd?`<button class="btn btn-primary" type="button" onclick="closeModal('modalPartecipantiEvento');openModalNuovaIscrizione(${id})">Iscrivi altri familiari</button>`:'');
  const modal=document.getElementById('modalPartecipantiEvento');modal.dataset.eventId=id;modal.dataset.management='family';
  openModal('modalPartecipantiEvento');
  } catch(error) {showToast(error.message,'error');}
}

const StaffGroupRegister=(()=>{
  const states={};
  const state=category=>states[category]||(states[category]={sequence:0,id:null,data:null,marks:{}});
  const endpoint=(category,id,suffix)=>`/api/calendari-gruppi/${category}/${id}/${suffix}`;
  const pane=category=>document.getElementById(category+'RegisterSection');
  const action=(category,method,args='')=>`StaffGroupRegister.${method}('${category}'${args?','+args:''})`;
  function show(category,screen) {
    document.getElementById(category+'GroupsOverview').style.display=screen==='groups'?'block':'none';
    pane(category).style.display=screen==='groups'?'none':'block';
    document.getElementById(category+'StaffHeaderActions').style.display=screen==='groups'?'flex':'none';
  }
  function reset(category) {state(category).sequence++;show(category,'groups');}
  function frame(category,title,back) {
    return `<div class="catechismo-dates-header"><h2 tabindex="-1" id="${category}RegisterTitle">${escapeHtml(title)}</h2><button class="btn btn-secondary" type="button" onclick="${action(category,back)}">← ${back==='reset'?'Gruppi':'Tutte le date'}</button></div>`;
  }
  async function openDates(category,id) {
    const current=state(category);current.id=id;current.data=null;
    const sequence=++current.sequence;
    show(category,'dates');
    pane(category).innerHTML=frame(category,'Incontri e appelli','reset')+'<p>Caricamento delle date…</p>';
    try {
      const data=await apiJson(endpoint(category,id,'registro')+'?periodo=anno');
      if(sequence!==current.sequence)return;
      current.data=data;
      const dates=[...data.date_incontri].sort((a,b)=>a.data.localeCompare(b.data));let month='';
      pane(category).innerHTML=frame(category,data.gruppo.nome+' · Incontri e appelli','reset')+`<p>${escapeHtml(data.gruppo.anno_scolastico||data.gruppo.anno_pastorale||'')} · Seleziona una data per aprire l’appello.</p>${data.avviso_calendario?`<p role="status">${escapeHtml(data.avviso_calendario)}</p>`:''}`+
        (dates.length?dates.map(day=>{const start=month!==day.data.slice(0,7);month=day.data.slice(0,7);return `${start?`<h3 class="catechismo-date-month">${escapeHtml(new Date(day.data+'T12:00:00').toLocaleDateString('it-IT',{month:'long',year:'numeric'}))}</h3>`:''}<button type="button" class="catechismo-date-row ${day.registrato?'is-recorded':''}" onclick="${action(category,'openAttendance',`'${day.data}'`)}"><span class="catechismo-date-day">${day.data.split('-').reverse().join('/')}</span><span class="catechismo-date-description"><strong>${escapeHtml(day.titolo_incontro||'Incontro del gruppo')}</strong><small>${day.registrato?`${day.presenti_count} presenti · ${day.assenti_count} assenti`:'Dal calendario del gruppo'}</small></span><span class="catechismo-date-status">${day.registrato?'Appello salvato':(day.data<GroupCalendar.localDate()?'Da compilare':'In programma')} →</span></button>`;}).join(''):'<p>Nessun incontro in calendario o appello salvato.</p>')+
        `<details class="catechismo-history"><summary>Storico incontri e statistiche di frequenza</summary><div class="table-responsive"><table class="custom-table"><thead><tr><th>Partecipante</th><th>Presenze</th><th>Assenze</th><th>Frequenza</th></tr></thead><tbody>${data.studenti.map(p=>`<tr><td>${escapeHtml(p.nominativo)}</td><td>${p.presenti}</td><td>${p.assenti}</td><td>${p.totale_incontri_validi?p.percentuale+'%':'—'}</td></tr>`).join('')}</tbody></table></div></details><form class="catechismo-manual-date" onsubmit="${action(category,'manualDate','event')}"><label for="${category}ManualRegisterDate">Incontro fuori calendario</label><input class="form-control" type="date" id="${category}ManualRegisterDate" value="${GroupCalendar.localDate()}" required><button type="submit" class="btn btn-secondary">Apri appello per questa data</button></form>`;
      document.getElementById(category+'RegisterTitle').focus?.();
    } catch(error) {if(sequence===current.sequence)pane(category).innerHTML=frame(category,'Incontri e appelli','reset')+`<p role="alert">${escapeHtml(error.message)}</p><button type="button" class="btn btn-secondary" onclick="${action(category,'back')}">Riprova</button>`;}
  }
  function back(category) {return openDates(category,state(category).id);}
  function manualDate(category,event) {event.preventDefault();return openAttendance(category,document.getElementById(category+'ManualRegisterDate').value);}
  async function openAttendance(category,day,id=null) {
    const current=state(category);if(id)current.id=id;current.day=day;current.marks={};current.data=null;
    const sequence=++current.sequence;show(category,'attendance');
    pane(category).innerHTML=frame(category,'Appello del '+day.split('-').reverse().join('/'),'back')+'<p>Caricamento appello…</p>';
    try {
      const data=await apiJson(endpoint(category,current.id,'registro')+'?mese='+day.slice(0,7));
      if(sequence!==current.sequence)return;
      current.data=data;
      for(const person of data.studenti)current.marks[person.codice_fiscale]=person.presenze_map[day]!==false;
      const meeting=data.date_incontri.find(row=>row.data===day);
      pane(category).innerHTML=frame(category,'Appello del '+day.split('-').reverse().join('/'),'back')+`<div class="attendance-group-banner"><div><small>Gruppo ${category==='giovani'?'Gruppi giovani':category==='oratorio'?'Oratorio':'Doposcuola'}</small><h3>${escapeHtml(data.gruppo.nome)}</h3><p>${escapeHtml(data.gruppo.anno_scolastico||data.gruppo.anno_pastorale||'')}</p></div><span class="badge badge-info">${data.studenti.length} iscritti</span></div>${data.avviso_calendario?`<p role="status">${escapeHtml(data.avviso_calendario)}</p>`:''}<form onsubmit="${action(category,'save','event')}"><div class="attendance-toolbar"><div class="staff-register-tools"><label>Data incontro<input type="date" class="form-control" value="${day}" readonly></label><label for="${category}MeetingTitle">Titolo incontro<input class="form-control" id="${category}MeetingTitle" value="${escapeHtml(meeting?.titolo_incontro||'')}" maxlength="100"></label><label class="choice-row"><input id="${category}MeetingPercentage" type="checkbox" ${meeting?.concorre_percentuale===false?'':'checked'}>Concorre alla percentuale delle presenze</label></div><div class="staff-register-tools"><span id="${category}AttendanceCount" class="badge badge-info"></span><button class="btn btn-secondary" type="button" onclick="${action(category,'markAll','true')}">Tutti presenti</button><button class="btn btn-secondary" type="button" onclick="${action(category,'markAll','false')}">Tutti assenti</button></div></div>
      <div class="table-responsive attendance-matrix"><table class="custom-table"><thead><tr><th>#</th><th>Partecipante</th><th>Appello data selezionata</th><th>Presenze</th><th>% Pres.</th></tr></thead><tbody>${attendanceRows(data.studenti,current.marks,category)||'<tr><td colspan="5">Nessun partecipante iscritto al gruppo.</td></tr>'}</tbody></table></div><p>Le presenze sono registrate solo premendo Salva.</p><div class="staff-register-tools"><button type="submit" id="${category}SaveAttendance" class="btn btn-primary" ${data.studenti.length?'':'disabled'}>Salva presenze</button><button type="button" class="btn btn-secondary" onclick="${action(category,'back')}">Annulla</button>${meeting?.registrato && data.puo_cancellare?`<button type="button" class="btn btn-danger" onclick="${action(category,'removeMeeting')}">Cancella appello</button>`:''}</div></form>`;
      updateCount(category);
      document.getElementById(category+'RegisterTitle').focus?.();
    } catch(error) {if(sequence===current.sequence)pane(category).innerHTML=frame(category,'Appello non disponibile','back')+`<p role="alert">${escapeHtml(error.message)}</p>`;}
  }
  function updateCount(category) {const values=Object.values(state(category).marks);const present=values.filter(Boolean).length;document.getElementById(category+'AttendanceCount').textContent=`${present} presenti · ${values.length-present} assenti`;}
  function mark(category,cf,present,update=true) {
    const current=state(category);if(!(cf in current.marks))return;
    current.marks[cf]=present;
    for(const [prefix,value,active] of [['sgp',present,'btn-success'],['sga',!present,'btn-danger']]) {
      const button=document.getElementById(prefix+'-'+category+'-'+cf);
      button.className='btn btn-sm '+(value?active:(prefix==='sgp'?'btn-outline-success':'btn-outline-danger'));button.style.fontWeight=value?'700':'normal';button.setAttribute?.('aria-pressed',String(value));
    }
    if(update)updateCount(category);
  }
  function markAll(category,value) {for(const cf of Object.keys(state(category).marks))mark(category,cf,value,false);updateCount(category);}
  async function save(category,event) {
    event.preventDefault();const current=state(category);if(!current.data)return;
    const button=document.getElementById(category+'SaveAttendance');if(button.disabled)return;button.disabled=true;
    try {
      await apiJson(endpoint(category,current.id,'registro'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:current.day,titolo_incontro:document.getElementById(category+'MeetingTitle').value,concorre_percentuale:document.getElementById(category+'MeetingPercentage').checked,presenze:Object.entries(current.marks).map(([cf,present])=>({codice_fiscale:cf,presente:present}))})});
      showToast('Presenze salvate','success');await back(category);
    } catch(error) {showToast(error.message,'error');button.disabled=false;}
  }
  async function removeMeeting(category) {
    if(!confirm('Cancellare l’appello salvato di questa data? L’appuntamento del calendario resterà disponibile.'))return;
    try {await apiJson(endpoint(category,state(category).id,'registro'),{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:state(category).day})});await back(category);}catch(error){showToast(error.message,'error');}
  }
  async function openRoster(category,id) {
    const current=state(category);current.id=id;const sequence=++current.sequence;show(category,'roster');
    pane(category).innerHTML=frame(category,'Elenco iscritti','reset')+'<p>Caricamento elenco…</p>';
    try {
      const data=await apiJson(endpoint(category,id,'elenco'));
      if(sequence!==current.sequence)return;
      pane(category).innerHTML=frame(category,data.gruppo.nome+' · Elenco','reset')+(data.puo_modificare?`<button type="button" class="btn btn-primary" onclick="${action(category,'addForm')}">+ Aggiungi ragazzo</button><div id="${category}AddParticipant"></div>`:'')+`<h3>Iscritti · ${data.persone.length}</h3>`+data.persone.map(person=>`<details class="catechismo-person"><summary>${escapeHtml(person.cognome+' '+person.nome)}</summary><h4>Contatti familiari</h4>${person.genitori.map(p=>`<p><strong>${escapeHtml(p.ruolo)}: ${escapeHtml(p.nominativo)}</strong><br>${escapeHtml(p.telefono||'Numero non indicato')}</p>`).join('')|| (person.referente?`<p>Referente: ${escapeHtml(person.referente.nominativo)}<br>${escapeHtml(person.referente.telefono||'Numero non indicato')}</p>`:'<p>Nessun genitore registrato nel nucleo.</p>')}<h4>Fascicolo sanitario</h4><dl><dt>Allergie</dt><dd>${escapeHtml(person.allergie||'Non indicate')}</dd><dt>Intolleranze</dt><dd>${escapeHtml(person.intolleranze_alimentari||'Non indicate')}</dd><dt>Terapie e medicinali</dt><dd>${escapeHtml(person.terapie_medicinali||'Non indicati')}</dd><dt>Note sanitarie</dt><dd>${escapeHtml(person.note_mediche||'Non indicate')}</dd></dl>${data.puo_modificare?`<button class="btn btn-sm btn-danger" type="button" onclick="${action(category,'removePerson',`'${person.codice_fiscale}'`)}">Rimuovi dal gruppo</button>`:''}</details>`).join('');
      document.getElementById(category+'RegisterTitle').focus?.();
    } catch(error){if(sequence===current.sequence)pane(category).innerHTML=frame(category,'Elenco non disponibile','reset')+`<p role="alert">${escapeHtml(error.message)}</p>`;}
  }
  async function addForm(category) {
    const current=state(category),sequence=current.sequence;
    try {const data=await apiJson(endpoint(category,current.id,'assegnabili'));if(sequence!==current.sequence)return;
      document.getElementById(category+'AddParticipant').innerHTML=data.persone.length?`<form class="staff-register-tools" onsubmit="${action(category,'addPerson','event')}"><label for="${category}Participant">Partecipante da aggiungere<select class="form-control" id="${category}Participant" required>${data.persone.map(p=>`<option value="${p.codice_fiscale}">${escapeHtml(p.nominativo)}</option>`).join('')}</select></label><button type="submit" class="btn btn-primary">Aggiungi al gruppo</button></form>`:'<p>Nessuna persona assegnabile alla fascia di età del gruppo.</p>';
    }catch(error){showToast(error.message,'error');}
  }
  async function changePerson(category,cf,method) {await apiJson(endpoint(category,state(category).id,'elenco'),{method,headers:{'Content-Type':'application/json'},body:JSON.stringify({codice_fiscale:cf})});await openRoster(category,state(category).id);}
  async function addPerson(category,event) {event.preventDefault();try{await changePerson(category,document.getElementById(category+'Participant').value,'POST');}catch(error){showToast(error.message,'error');}}
  async function removePerson(category,cf) {if(!confirm('Rimuovere questo partecipante dal gruppo?'))return;try{await changePerson(category,cf,'DELETE');}catch(error){showToast(error.message,'error');}}
  return {reset,openDates,back,manualDate,openAttendance,mark,markAll,save,removeMeeting,openRoster,addForm,addPerson,removePerson};
})();

function groupHealthButton(category,id) {
  if(!hasPermission(category+'.salute') || !hasPermission(category+'.cucina'))return '';
  return `<button type="button" class="btn btn-sm btn-secondary" data-permission="${category}.cucina" onclick="openGroupHealth('${category}',${id})">Quadro sanitario e cucina</button>`;
}
let groupHealthRequest=0;
async function openGroupHealth(category,id) {
  const sequence=++groupHealthRequest;
  const modal=document.getElementById('modalGroupHealth');modal.dataset.category=category;
  document.getElementById('groupHealthTitle').textContent='Caricamento…';
  const content=document.getElementById('groupHealthContent');content.dataset.permission=category+'.salute';content.innerHTML='';
  openModal('modalGroupHealth');
  try {
    const data=await apiJson(`/api/calendari-gruppi/${category}/${id}/sanita`);
    if(sequence!==groupHealthRequest)return;
    document.getElementById('groupHealthTitle').textContent=data.gruppo;
    const counts=data.conteggi;
    content.innerHTML=`<div class="health-summary-counts"><span><strong>${counts.iscritti}</strong> iscritti</span><span><strong>${counts.esigenze_alimentari}</strong> con allergie o intolleranze segnalate</span><span><strong>${counts.terapie}</strong> con terapie segnalate</span></div>`+
      (data.persone.length?`<div class="table-responsive"><table class="custom-table"><thead><tr><th>Iscritto</th><th>Allergie</th><th>Intolleranze alimentari</th><th>Terapie / medicinali</th><th>Note</th><th>Contatti familiari</th></tr></thead><tbody>${data.persone.map(p=>`<tr><td><strong>${escapeHtml(p.nominativo)}</strong></td><td>${escapeHtml(p.allergie||'Non indicate')}</td><td>${escapeHtml(p.intolleranze_alimentari||'Non indicate')}</td><td>${escapeHtml(p.terapie_medicinali||'Non indicate')}</td><td>${escapeHtml(p.note_mediche||'—')}</td><td>${p.contatti.map(c=>`${escapeHtml(c.nominativo)}<br>${escapeHtml(c.telefono||'Numero non indicato')}`).join('<br>')||'Non indicati'}</td></tr>`).join('')}</tbody></table></div>`:'<p>Nessun iscritto in questo gruppo.</p>');
  } catch(error){if(sequence===groupHealthRequest){document.getElementById('groupHealthTitle').textContent='';content.textContent=error.message;}}
}

function attendanceRows(studenti,marks,category) {
  return studenti.map((s, idx) => {
    const isPresente = marks[s.codice_fiscale] === true;

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
            <button type="button" aria-pressed="${isPresente}" id="${category==='catechismo'?'btn-pres-cat-':'sgp-'+category+'-'}${s.codice_fiscale}" class="btn btn-sm ${isPresente ? 'btn-success' : 'btn-outline-success'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${isPresente ? 'font-weight:700;' : ''}" onclick="${category==='catechismo'?`togglePresenzaRagazzoCatechismo('${s.codice_fiscale}', true)`:`StaffGroupRegister.mark('${category}','${s.codice_fiscale}',true)`}">
              ✓ Presente
            </button>
            <button type="button" aria-pressed="${!isPresente}" id="${category==='catechismo'?'btn-ass-cat-':'sga-'+category+'-'}${s.codice_fiscale}" class="btn btn-sm ${!isPresente ? 'btn-danger' : 'btn-outline-danger'}" style="border: none; border-radius: 0; padding: 4px 10px; font-size: 12px; ${!isPresente ? 'font-weight:700;' : ''}" onclick="${category==='catechismo'?`togglePresenzaRagazzoCatechismo('${s.codice_fiscale}', false)`:`StaffGroupRegister.mark('${category}','${s.codice_fiscale}',false)`}">
              ✗ Assente
            </button>
          </div>
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

}

/* Riepilogo caricato soltanto aprendo Calendari. Tre feed alla volta, cache di 5 minuti. */
const ParishWeek=(()=>{
  let calendars=[],offset=0,sequence=0,owner=null;
  const cache=new Map();
  const target=()=>document.getElementById('parishWeeklyCalendar');
  function endpoint(c) {
    if(c.calendar_api_url && /^(?:\/api\/(?:impostazioni\/)?calendari-gruppi\/(?:catechismo|oratorio|doposcuola|giovani)\/\d+|\/api\/impostazioni\/calendari\/\d+\/appuntamenti)$/.test(c.calendar_api_url))return c.calendar_api_url;
    return Number.isInteger(c.id)?`/api/impostazioni/calendari/${c.id}/appuntamenti`:null;
  }
  async function read(url) {
    const previous=cache.get(url);
    if(previous && previous.until>Date.now())return previous.value;
    const value=await apiJson(url);
    cache.set(url,{value,until:Date.now()+300000});
    while(cache.size>64)cache.delete(cache.keys().next().value);
    return value;
  }
  const sourceColor=value=>/^#[a-f0-9]{6}$/i.test(value||'')?value:'#8B1E1E';
  function eventStyle(event) {
    if(!event.fonti[0]?.colore)return '';
    const color=sourceColor(event.fonti[0].colore);
    return ` style="border-color:${color};background:${color}12"`;
  }
  function sourceLabels(event) {
    return event.fonti.map(source=>source.colore?`<span style="display:inline-block;border-left:3px solid ${sourceColor(source.colore)};padding-left:5px">${escapeHtml(source.nome)}</span>`:escapeHtml(source.nome)).join(' · ');
  }
  function markup(days,events,errors,stale) {
    const dateLabel=day=>new Date(day+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'short',year:'numeric'});
    return `<div class="weekly-toolbar"><strong>${dateLabel(days[0])} – ${dateLabel(days[6])}</strong><div><button type="button" class="btn btn-sm btn-secondary" aria-label="Settimana precedente" onclick="ParishWeek.move(-1)">←</button><button type="button" class="btn btn-sm btn-secondary" onclick="ParishWeek.move(0)">Questa settimana</button><button type="button" class="btn btn-sm btn-secondary" aria-label="Settimana successiva" onclick="ParishWeek.move(1)">→</button></div></div>
      ${errors.length?`<p role="status">Alcuni calendari non sono disponibili: ${errors.map(escapeHtml).join(', ')}. <button type="button" class="btn btn-sm btn-secondary" onclick="ParishWeek.load()">Riprova</button></p>`:''}
      ${stale?'<p>Alcuni appuntamenti provengono dall’ultima copia disponibile del calendario.</p>':''}
      <div class="weekly-calendar">${days.map(day=>{
        const appointments=events.filter(e=>(e.giorni||[e.giorno]).includes(day)).sort((a,b)=>(a.tutto_il_giorno?-1:0)-(b.tutto_il_giorno?-1:0) || (a.minute??celebrationSlots({orario:a.ora})[0].minute)-(b.minute??celebrationSlots({orario:b.ora})[0].minute) || a.titolo.localeCompare(b.titolo,'it'));
        return `<section class="weekly-day ${day===GroupCalendar.localDate()?'is-today':''}"><h4>${escapeHtml(new Date(day+'T12:00:00').toLocaleDateString('it-IT',{weekday:'long',day:'numeric',month:'short'}))}</h4>${appointments.map(e=>`<article class="weekly-mass" data-section="${escapeHtml(e.sezione||'calendario')}"${eventStyle(e)}><strong>${escapeHtml(e.tutto_il_giorno?'Tutto il giorno':e.giorno<day?'In corso':e.ora||'Orario da definire')}</strong><span>${escapeHtml(e.titolo)}</span><small>${sourceLabels(e)}</small>${e.luogo?`<small>${escapeHtml(e.luogo)}</small>`:''}</article>`).join('')||'<small class="weekly-empty">Nessun appuntamento</small>'}</section>`;
      }).join('')}</div>`;
  }
  async function load() {
    const container=target();if(!container)return;
    const token=++sequence,days=weeklyDays(offset),month=days[0].slice(0,7);
    container.innerHTML='<p>Caricamento degli appuntamenti della settimana…</p>';
    const sources=[...new Map(calendars.map(c=>[endpoint(c),c]).filter(([api])=>api)).values()];
    const events=new Map(),errors=[];let cursor=0,stale=false;
    const worship=hasPermission('calendari.comunita')?read('/api/impostazioni/dati-pubblici').catch(()=>{errors.push('Messe e liturgia');return null;}):Promise.resolve(null);
    async function worker() {
      while(cursor<sources.length) {
        if(token!==sequence)return;
        const order=cursor++,c=sources[order];
        const source={nome:c.titolo||c.nome||'Calendario parrocchiale',colore:sourceColor(c.colore),ordine:order};
        try {
          const data=await read(endpoint(c)+'?mese='+month);stale=stale||data.obsoleto;
          for(const event of data.eventi||[]) {
            if(!(event.giorni||[event.giorno]).some(day=>days.includes(day)))continue;
            // I gruppi genitori possono derivare lo stesso incontro con un ID diverso.
            const key=JSON.stringify([event.inizio,event.fine||'',event.titolo.trim().toLocaleLowerCase('it-IT'),(event.luogo||'').trim().toLocaleLowerCase('it-IT')]);
            if(events.has(key)) {const item=events.get(key);if(!item.fonti.some(s=>s.ordine===order))item.fonti.push(source);item.fonti.sort((a,b)=>a.ordine-b.ordine);}
            else events.set(key,{...event,fonti:[source]});
          }
        } catch(error) {errors.push(c.titolo||c.nome||'Calendario');}
      }
    }
    await Promise.all(Array.from({length:Math.min(3,sources.length)},worker));
    const publicData=await worship;
    if(publicData)days.forEach((day,index)=>celebrationDayEntries(publicData.celebrazioni||[],day,index).forEach((c,i)=>events.set('worship:'+day+':'+i,{...c,giorno:day,giorni:[day],ora:c.orario,fonti:[{nome:'Messe e liturgia'}]})));
    if(token!==sequence)return;
    container.innerHTML=markup(days,[...events.values()],errors,stale);
  }
  function setCalendars(value) {
    if(owner!==currentUser?.id){cache.clear();offset=0;owner=currentUser?.id;}
    calendars=value;return load();
  }
  function move(delta) {offset=delta===0?0:offset+delta;return load();}
  function clearCache(){cache.clear();}
  return {setCalendars,move,load,clearCache};
})();

function updateCalendarMode() {
  const manual=document.getElementById('inputCalTipo').value==='manuale';
  document.getElementById('inputCalGoogleGroup').hidden=manual;
  document.getElementById('inputCalUrl').required=!manual;
  document.getElementById('inputCalUrl').disabled=manual;
}
let calendarEventEditor={id:null,events:[],sequence:0};
async function openCalendarEvents(id) {
  calendarEventEditor.id=id;const sequence=++calendarEventEditor.sequence;
  const calendar=cacheSegreteriaCalendari.find(c=>c.id===id);
  document.getElementById('calendarEventsTitle').textContent='Appuntamenti · '+(calendar?.titolo||'Calendario');
  document.getElementById('calendarEventsList').innerHTML='<p>Caricamento appuntamenti…</p>';
  clearCalendarEvent();openModal('modalCalendarEvents');
  try {
    const data=await apiJson(`/api/impostazioni/calendari/${id}/eventi`);
    if(sequence!==calendarEventEditor.sequence)return;
    calendarEventEditor.events=data.eventi;
    document.getElementById('calendarEventsList').innerHTML=data.eventi.map(e=>`<article class="calendar-editor-event"><div><strong>${escapeHtml(e.titolo)}</strong><p>${escapeHtml(new Date(e.inizio).toLocaleString('it-IT'))} – ${escapeHtml(new Date(e.fine).toLocaleString('it-IT'))}${e.tutto_il_giorno?' · Tutto il giorno':''}</p><small>${escapeHtml(e.luogo)}</small></div><div><button type="button" class="btn btn-sm btn-secondary" onclick="editCalendarEvent(${e.id})">Modifica</button><button type="button" class="btn btn-sm btn-danger" onclick="deleteCalendarEvent(${e.id})">Elimina</button></div></article>`).join('')||'<p>Nessun appuntamento: aggiungi il primo con il modulo qui sotto.</p>';
  } catch(error){document.getElementById('calendarEventsList').textContent=error.message;}
}
function clearCalendarEvent() {
  for(const id of ['calendarEventId','calendarEventName','calendarEventStart','calendarEventEnd','calendarEventPlace'])document.getElementById(id).value='';
  document.getElementById('calendarEventAllDay').checked=false;
  document.getElementById('calendarEventFormTitle').textContent='Nuovo appuntamento';
}
function editCalendarEvent(id) {
  const event=calendarEventEditor.events.find(e=>e.id===id);if(!event)return;
  for(const [field,value] of Object.entries({calendarEventId:event.id,calendarEventName:event.titolo,calendarEventStart:event.inizio,calendarEventEnd:event.fine,calendarEventPlace:event.luogo}))document.getElementById(field).value=value;
  document.getElementById('calendarEventAllDay').checked=event.tutto_il_giorno;
  document.getElementById('calendarEventFormTitle').textContent='Modifica appuntamento';
  document.getElementById('calendarEventName').focus?.();
}
async function saveCalendarEvent(event) {
  event.preventDefault();const calendarId=calendarEventEditor.id,id=document.getElementById('calendarEventId').value;
  try {
    await apiJson(`/api/impostazioni/calendari/${calendarId}/eventi`+(id?'/'+id:''),{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({titolo:document.getElementById('calendarEventName').value,inizio:document.getElementById('calendarEventStart').value,fine:document.getElementById('calendarEventEnd').value,luogo:document.getElementById('calendarEventPlace').value,tutto_il_giorno:document.getElementById('calendarEventAllDay').checked})});
    ParishWeek.clearCache();await openCalendarEvents(calendarId);await ParishWeek.load();
    showToast('Appuntamento salvato','success');
  } catch(error){showToast(error.message,'error');}
}
async function deleteCalendarEvent(id) {
  if(!confirm('Eliminare questo appuntamento?'))return;
  const calendarId=calendarEventEditor.id;
  try {
    await apiJson(`/api/impostazioni/calendari/${calendarId}/eventi/${id}`,{method:'DELETE'});
    ParishWeek.clearCache();await openCalendarEvents(calendarId);await ParishWeek.load();
  } catch(error){showToast(error.message,'error');}
}
