/* Calendario mensile dei gruppi. Date da Google, appelli salvati soltanto nel portale. */
const GroupCalendar = (() => {
  const views = new WeakMap();
  const apiPattern = /^\/api\/calendari-gruppi\/(catechismo|doposcuola|oratorio)\/\d+$/;
  const localDate = () => {const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());return ['year','month','day'].map(type=>parts.find(part=>part.type===type).value).join('-');};
  const iso = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
  function days(month) {
    const [year,number] = month.split('-').map(Number);
    const first=new Date(year,number-1,1);
    first.setDate(first.getDate()-((first.getDay()+6)%7));
    return Array.from({length:42},(_,index)=>{const day=new Date(first);day.setDate(day.getDate()+index);return iso(day);});
  }
  function markup(group) {
    const api=group.calendar_api_url;
    if(!apiPattern.test(api || '')) return '';
    return `<div class="group-calendar"><button type="button" class="btn btn-sm btn-secondary" data-calendar-api="${escapeHtml(api)}" onclick="loadGroupCalendar(this)">Calendario mensile</button><div class="group-calendar-content"></div></div>`;
  }
  async function load(button) {
    const content=button.parentElement.querySelector('.group-calendar-content');
    if(content.childElementCount){content.hidden=!content.hidden;return;}
    const api=button.dataset.calendarApi;
    if(!apiPattern.test(api || '')) return;
    const root=document.createElement('div');root.className='native-group-calendar';content.appendChild(root);
    views.set(root,{api,month:localDate().slice(0,7),sequence:0,data:null});
    button.textContent='Mostra / nascondi calendario';
    await fetchMonth(root);
  }
  async function fetchMonth(root) {
    const state=views.get(root),sequence=++state.sequence;
    root.setAttribute('aria-busy','true');
    root.innerHTML='<p class="monthly-status" role="status">Caricamento appuntamenti…</p>';
    try {
      const data=await apiJson(state.api+'?mese='+encodeURIComponent(state.month));
      if(sequence!==state.sequence || root.isConnected===false) return;
      state.data=data;render(root);
    } catch(error) {
      if(sequence!==state.sequence) return;
      root.innerHTML=`<p class="monthly-status" role="alert">${escapeHtml(error.message)}</p><button type="button" class="btn btn-sm btn-secondary" onclick="GroupCalendar.retry(this)">Riprova</button>`;
    } finally {if(sequence===state.sequence) root.setAttribute('aria-busy','false');}
  }
  function render(root) {
    const state=views.get(root),data=state.data;
    const title=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric'}).format(new Date(state.month+'-01T12:00:00'));
    const grid=days(state.month),today=localDate();
    root.innerHTML=`<div class="monthly-toolbar"><div><h4>${escapeHtml(title)}</h4><small>${escapeHtml(data.nome_gruppo)}</small></div><div class="monthly-controls"><button type="button" class="btn btn-sm btn-secondary" aria-label="Mese precedente" onclick="GroupCalendar.move(this,-1)">‹</button><button type="button" class="btn btn-sm btn-secondary" onclick="GroupCalendar.today(this)">Oggi</button><button type="button" class="btn btn-sm btn-secondary" aria-label="Mese successivo" onclick="GroupCalendar.move(this,1)">›</button></div></div>
      ${data.obsoleto ? '<p class="monthly-status" role="status">Google non è raggiungibile: stai consultando l’ultima copia disponibile.</p>':''}
      <div class="monthly-table-wrap"><table class="monthly-table"><caption class="sr-only">Appuntamenti di ${escapeHtml(title)}</caption><thead><tr>${['Lun','Mar','Mer','Gio','Ven','Sab','Dom'].map(day=>`<th scope="col">${day}</th>`).join('')}</tr></thead><tbody>${Array.from({length:6},(_,row)=>`<tr>${grid.slice(row*7,row*7+7).map(day=>{
        const events=(data.eventi || []).filter(event=>event.giorni.includes(day));
        const own=(data.presenze || []).filter(record=>record.data===day);
        return `<td class="${day.slice(0,7)!==state.month ? 'monthly-outside':''} ${day===today ? 'monthly-today':''}"><button type="button" class="monthly-day" data-day="${day}" aria-label="Mostra il ${day}" onclick="GroupCalendar.select(this)">${Number(day.slice(-2))}</button>${events.map(event=>`<button type="button" class="monthly-event" data-day="${day}" title="${escapeHtml(event.titolo)}" onclick="GroupCalendar.select(this)">${event.ora ? `<span>${escapeHtml(event.ora)}</span>`:''}${escapeHtml(event.titolo)}</button>`).join('')}${own.length ? `<span class="monthly-presence-dot" title="Appello salvato">●</span>`:''}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>
      <p class="monthly-hint">Seleziona un giorno per i dettagli.${data.puo_registrare_presenze ? ' Apri l’appello dalla data dell’incontro. Le presenze vengono salvate solo nel sito.':''}</p>
      ${!data.configurato ? '<p class="monthly-status">Nessun calendario Google collegato.</p>' : !(data.eventi || []).length ? '<p class="monthly-status">Nessun appuntamento in questo mese.</p>':''}
      <div class="monthly-day-details" aria-live="polite"></div>`;
    const defaultDay=grid.includes(today) && today.slice(0,7)===state.month ? today : (data.eventi?.[0]?.giorni.find(day=>day.slice(0,7)===state.month) || state.month+'-01');
    showDay(root,defaultDay);
  }
  function showDay(root,day) {
    const data=views.get(root).data;
    const events=(data.eventi || []).filter(event=>event.giorni.includes(day));
    const own=(data.presenze || []).filter(record=>record.data===day);
    const title=new Intl.DateTimeFormat('it-IT',{weekday:'long',day:'numeric',month:'long'}).format(new Date(day+'T12:00:00'));
    root.querySelectorAll('.monthly-day').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.day===day)));
    root.querySelector('.monthly-day-details').innerHTML=`<h4>${escapeHtml(title)}</h4>${events.map(event=>`<article><strong>${escapeHtml(event.titolo)}</strong><p>${event.tutto_il_giorno ? 'Tutto il giorno' : escapeHtml(event.ora)}${event.luogo ? ' · '+escapeHtml(event.luogo):''}</p></article>`).join('') || '<p>Nessun appuntamento previsto.</p>'}${own.length ? `<div class="monthly-attendance-list">${own.map(record=>`<p><strong>${escapeHtml(record.nominativo)}</strong><span class="badge ${record.presente ? 'badge-success':'badge-danger'}">${record.presente ? 'Presente':'Assente'}</span></p>`).join('')}</div>` : events.length && (data.iscritto || data.puo_registrare_presenze) ? '<p>Presenze non ancora registrate.</p>':''}${data.puo_registrare_presenze && (events.length || own.length) ? `<button type="button" class="btn btn-sm btn-primary" data-day="${day}" onclick="GroupCalendar.attendance(this)">Apri appello del ${day.split('-').reverse().join('/')}</button>`:''}`;
  }
  function select(button){showDay(button.closest('.native-group-calendar'),button.dataset.day);}
  async function move(button,delta) {
    const root=button.closest('.native-group-calendar'),state=views.get(root);
    const [year,month]=state.month.split('-').map(Number),next=new Date(year,month-1+delta,1);
    if(next.getFullYear()<1900 || next.getFullYear()>2100) return;
    state.month=iso(next).slice(0,7);await fetchMonth(root);
  }
  async function today(button){const root=button.closest('.native-group-calendar');views.get(root).month=localDate().slice(0,7);await fetchMonth(root);}
  async function retry(button){await fetchMonth(button.closest('.native-group-calendar'));}
  async function attendance(button) {
    const data=views.get(button.closest('.native-group-calendar')).data;
    if(!data.puo_registrare_presenze) return;
    try {await openCalendarGroupAttendance(data.categoria,data.gruppo_id,button.dataset.day);} catch(error){showToast(error.message,'error');}
  }
  return {markup,load,move,today,retry,select,attendance,days,localDate};
})();
