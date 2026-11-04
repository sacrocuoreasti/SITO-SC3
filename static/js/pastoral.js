const pastoralLabels={oratorio:'Oratorio',catechismo:'Catechismo',doposcuola:'Doposcuola',giovani:'Gruppi giovani'};
function calendarType(calendar){const types=[...new Set((calendar.gruppi_origine||[]).map(g=>g.categoria))];return types.length>1?'condivisi':calendar.categoria||'parrocchia';}
function calendarTypeLabel(type){return pastoralLabels[type]||({parrocchia:'Parrocchia e comunità',liturgia:'Liturgia',condivisi:'Calendari condivisi',giovani:'Gruppi giovani'}[type])||type.replace(/_/g,' ');}
function calendarBuckets(items){const groups=new Map();for(const item of items){const type=calendarType(item);if(!groups.has(type))groups.set(type,[]);groups.get(type).push(item);}return [...groups].sort((a,b)=>calendarTypeLabel(a[0]).localeCompare(calendarTypeLabel(b[0]),'it'));}
function groupedCalendarCards(items,render=communityCalendarCard){return calendarBuckets(items).map(([type,rows])=>`<section class="calendar-type-section"><h2>${escapeHtml(calendarTypeLabel(type))}</h2><div class="calendar-type-grid">${rows.map(render).join('')}</div></section>`).join('');}

const PastoralBoards=(()=>{
  let active=null,noticeRows=[],sequences={};
  function article(n,manage=false){return `<article class="group-board-notice"><div><span class="badge badge-info">${escapeHtml(n.argomento)}</span>${!n.is_pubblicato?'<span class="badge badge-warning">Bozza</span>':''}</div><h4>${escapeHtml(n.titolo)}</h4><p>${escapeHtml(n.contenuto)}${n.anteprima?'…':''}</p>${n.anteprima?`<button class="btn btn-sm btn-secondary" onclick="PastoralBoards.open('${n.categoria}',${n.gruppo_id})">Leggi l’avviso completo</button>`:''}<small>${escapeHtml(n.gruppo)} · ${escapeHtml(new Date(n.created_at).toLocaleDateString('it-IT'))}</small>${manage?`<div><button class="btn btn-sm btn-secondary" onclick="PastoralBoards.edit(${n.id})">Modifica</button><button class="btn btn-sm btn-danger" onclick="PastoralBoards.remove(${n.id})">Elimina</button></div>`:''}</article>`;}
  function topics(rows){const groups=new Map();for(const n of rows){if(!groups.has(n.argomento))groups.set(n.argomento,[]);groups.get(n.argomento).push(n);}return [...groups].map(([topic,items])=>`<section class="board-topic"><h4>${escapeHtml(topic)}</h4>${items.map(n=>article(n)).join('')}</section>`).join('');}
  async function load(category,target,scope='famiglia'){
    const root=document.getElementById(target);if(!root)return;
    const allowed=category?hasPermission(category+'.bacheca'):hasPermission('dashboard.bacheche');root.hidden=!allowed;if(!allowed){root.innerHTML='';return;}
    const sequence=(sequences[target]||0)+1;sequences[target]=sequence;
    root.innerHTML='<p>Caricamento bacheche…</p>';
    try{
      const data=await apiJson('/api/bacheche');if(sequences[target]!==sequence)return;
      if(category){const groups=(data.gruppi||[]).filter(g=>g.categoria===category && g.ambiti.includes(scope));root.innerHTML='<h3>Bacheca dei gruppi</h3>'+(groups.map(g=>{const rows=(data.avvisi||[]).filter(n=>n.categoria===category && n.gruppo_id===g.id && (scope==='staff'||n.is_pubblicato));return `<section class="group-board-preview"><h4>${escapeHtml(g.nome)}</h4>${rows.slice(0,3).map(n=>article(n)).join('')||'<p>Nessun avviso pubblicato.</p>'}<button class="btn btn-sm btn-secondary" onclick="PastoralBoards.open('${category}',${g.id})">${g.puo_gestire && scope==='staff'?'Apri e gestisci bacheca':'Apri bacheca'}</button></section>`;}).join('')||'<p>Gli avvisi saranno visibili nei gruppi a cui sei iscritto.</p>');}
      else{const rows=(data.avvisi||[]).filter(n=>n.is_pubblicato);root.innerHTML=Object.keys(pastoralLabels).map(c=>{const selected=rows.filter(n=>n.categoria===c);return selected.length?`<section class="board-category"><h3>${escapeHtml(pastoralLabels[c])}</h3>${topics(selected)}</section>`:'';}).join('')||'<p>Nessun avviso dai tuoi gruppi.</p>';}
    }catch(error){root.textContent=error.message;}
  }
  async function open(category,id){
    active={category,id};document.getElementById('modalGroupBoard').dataset.permission=category+'.bacheca';const root=document.getElementById('groupBoardContent');root.innerHTML='<p>Caricamento bacheca…</p>';openModal('modalGroupBoard');
    try{const data=await apiJson(`/api/bacheche/${category}/${id}`);if(active?.category!==category || active?.id!==id)return;noticeRows=data.avvisi;document.getElementById('groupBoardTitle').textContent='Bacheca · '+data.gruppo;
      root.innerHTML=`<div class="board-dialog-summary"><div><span class="board-eyebrow">Comunicazioni del gruppo</span><p>${data.puo_gestire?'Scrivi agli iscritti, prepara una bozza e ritrova gli avvisi pubblicati.':'Tutti gli aggiornamenti e le comunicazioni per il tuo gruppo.'}</p></div><span class="badge badge-neutral">${data.avvisi.length} avvisi</span>${data.puo_gestire?'<button type="button" class="btn btn-primary" onclick="PastoralBoards.newNotice()">+ Scrivi un avviso</button>':''}</div>`+
        `<div class="board-dialog-notices">${data.avvisi.map(n=>article(n,data.puo_gestire)).join('')||'<div class="board-empty"><strong>La bacheca è pronta</strong><p>Qui troverai gli avvisi del gruppo.</p></div>'}</div>`+
        (data.puo_gestire?`<form id="boardEditor" class="board-editor" onsubmit="PastoralBoards.save(event)" hidden><div class="board-editor-heading"><span class="board-eyebrow">Bacheca del gruppo</span><h3 id="boardEditorTitle">Nuovo avviso</h3><p>Il messaggio sarà visibile soltanto agli iscritti e allo staff di questo gruppo.</p></div><input id="boardNoticeId" type="hidden"><div class="form-row"><div class="form-group"><label for="boardTopic">Argomento</label><input id="boardTopic" class="form-control" value="Comunicazioni" list="boardTopics" maxlength="80" required></div><div class="form-group"><label for="boardTitle">Titolo dell’avviso</label><input id="boardTitle" class="form-control" maxlength="150" placeholder="Un titolo chiaro per gli iscritti" required></div></div><datalist id="boardTopics"><option value="Comunicazioni"><option value="Incontri"><option value="Materiali"><option value="Organizzazione"></datalist><div class="form-group"><label for="boardBody">Messaggio</label><textarea id="boardBody" class="form-control" rows="8" maxlength="20000" placeholder="Scrivi qui le informazioni da condividere…" required></textarea></div><label class="board-publication"><input id="boardPublished" type="checkbox" checked><span><strong>Pubblica per gli iscritti</strong><small>Disattiva per salvare una bozza visibile soltanto allo staff.</small></span></label><div class="board-editor-actions"><button class="btn btn-primary" type="submit">Salva avviso</button><button type="button" class="btn btn-secondary" onclick="PastoralBoards.cancel()">Annulla</button></div></form>`:'');
    }catch(error){root.textContent=error.message;}
  }
  function clear(){document.getElementById('boardNoticeId').value='';document.getElementById('boardTopic').value='Comunicazioni';document.getElementById('boardTitle').value='';document.getElementById('boardBody').value='';document.getElementById('boardPublished').checked=true;}
  function newNotice(){clear();document.getElementById('boardEditorTitle').textContent='Nuovo avviso';document.getElementById('boardEditor').hidden=false;document.getElementById('boardEditor').scrollIntoView?.({behavior:'smooth',block:'start'});document.getElementById('boardTitle').focus?.();}
  function cancel(){clear();document.getElementById('boardEditor').hidden=true;}
  function edit(id){const n=noticeRows.find(n=>n.id===id);if(!n)return;document.getElementById('boardEditor').hidden=false;document.getElementById('boardEditorTitle').textContent='Modifica avviso';document.getElementById('boardEditor').scrollIntoView?.({behavior:'smooth',block:'start'});document.getElementById('boardNoticeId').value=id;document.getElementById('boardTopic').value=n.argomento;document.getElementById('boardTitle').value=n.titolo;document.getElementById('boardBody').value=n.contenuto;document.getElementById('boardPublished').checked=n.is_pubblicato;document.getElementById('boardTitle').focus?.();}
  function refresh(){const category=currentView?.replace('_staff','');if(pastoralLabels[category])return load(category,category+(currentView.endsWith('_staff')?'BoardStaff':'BoardFamily'),currentView.endsWith('_staff')?'staff':'famiglia');if(currentView==='dashboard')return load(null,'dashboardGroupBoards');}
  async function save(event){event.preventDefault();const context={...active};const id=document.getElementById('boardNoticeId').value;try{await apiJson(id?'/api/bacheche/avvisi/'+id:`/api/bacheche/${context.category}/${context.id}`,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({argomento:document.getElementById('boardTopic').value,titolo:document.getElementById('boardTitle').value,contenuto:document.getElementById('boardBody').value,is_pubblicato:document.getElementById('boardPublished').checked})});await open(context.category,context.id);await refresh();showToast('Avviso salvato','success');}catch(error){showToast(error.message,'error');}}
  async function remove(id){if(!confirm('Eliminare questo avviso del gruppo?'))return;const context={...active};try{await apiJson('/api/bacheche/avvisi/'+id,{method:'DELETE'});await open(context.category,context.id);await refresh();}catch(error){showToast(error.message,'error');}}
  return {load,open,edit,clear,newNotice,cancel,save,remove,refresh};
})();

const YouthGroups=(()=>{
  let groups=[],currentYear='',selectedYear=null;
  async function load(){
    const staff=currentView==='giovani_staff';
    document.getElementById('giovaniStaffSection').style.display=staff?'block':'none';
    if(!staff){await PastoralBoards.load('giovani','giovaniBoardFamily');await loadFamilyGroupView('giovani',()=>loadAssignedGroupRegisters('giovani'));return;}
    StaffGroupRegister.reset('giovani');
    await PastoralBoards.load('giovani','giovaniBoardStaff','staff');
    try{
      const data=await apiJson('/api/giovani/gruppi');groups=data.gruppi;currentYear=data.anno_pastorale_corrente;
      if(selectedYear===null)selectedYear=currentYear;
      document.getElementById('youthYear').value=selectedYear;
      render();
    }catch(error){showToast(error.message,'error');}
  }
  function selectYear(year){selectedYear=year;document.getElementById('youthYear').value=year;render();}
  function render(){
    const year=document.getElementById('youthYear').value;
    const search=(document.getElementById('youthSearch').value||'').trim().toLocaleLowerCase('it');
    const first=Number(currentYear.slice(0,4));
    const years=[...new Set([...(currentYear?[currentYear,`${first-1}/${first}`,`${first+1}/${first+2}`]:[]),...groups.map(g=>g.anno_pastorale)])].filter(Boolean).sort().reverse();
    document.getElementById('youthYearButtons').innerHTML=['',...years].map(y=>`<button type="button" class="btn btn-sm ${y===year?'btn-primary':'btn-secondary'}" aria-pressed="${y===year}" onclick="YouthGroups.selectYear('${escapeHtml(y)}')">${escapeHtml(y||'Tutti')}</button>`).join('');
    const inYear=groups.filter(g=>!year || g.anno_pastorale===year);
    const rows=inYear.filter(g=>!search || [g.nome,g.catechista_nome,g.aula,g.orario_incontri,g.note].some(value=>(value||'').toLocaleLowerCase('it').includes(search)));
    document.getElementById('youthGroupsCount').textContent=year?`${inYear.length} gruppi nell’anno ${year} · ${rows.length} visualizzati`:`${rows.length} gruppi · tutti gli anni pastorali`;
    document.getElementById('youthGroupsGrid').innerHTML=rows.map(g=>{
      const status=g.stato==='bozza'?['badge-neutral','🔒 Bozza']:g.stato==='chiuso'?['badge-danger','🔴 Chiuso']:['badge-success','🟢 Pubblico'];
      return `<article class="catechismo-card youth-group-card">
        <div class="pastoral-group-card-heading"><div><h3>${escapeHtml(g.nome)}</h3><div class="pastoral-group-badges"><span class="badge badge-info">📁 ${escapeHtml(g.anno_pastorale)}</span><span class="badge ${status[0]}">${status[1]}</span></div></div><span class="badge badge-success">${g.totale_ragazzi} iscritti</span></div>
        <div class="pastoral-group-facts"><div>👤 Responsabili: <strong>${escapeHtml(g.catechista_nome||'Non assegnati')}</strong></div><div>🕒 Orario: <strong>${escapeHtml(g.orario_incontri||'Non specificato')}</strong></div><div>📍 Aula / luogo: <strong>${escapeHtml(g.aula||'Non specificata')}</strong></div><div>👥 Età: <strong>${escapeHtml(ageRangeLabel(g))}</strong></div>${groupCalendarMarkup(g)}${g.note?`<p class="pastoral-group-note">📝 ${escapeHtml(g.note)}</p>`:''}</div>
        <div class="pastoral-group-actions">${hasPermission('giovani.appelli')?`<button class="btn btn-primary btn-sm" onclick="StaffGroupRegister.openDates('giovani',${g.id})">📅 Incontri e appelli</button>`:''}${hasPermission('giovani.elenco')?`<button class="btn btn-secondary btn-sm" onclick="StaffGroupRegister.openRoster('giovani',${g.id})">Elenco</button>`:''}${groupHealthButton('giovani',g.id)}${hasPermission('giovani.bacheca')?`<button class="btn btn-secondary btn-sm" onclick="PastoralBoards.open('giovani',${g.id})">Bacheca</button>`:''}${hasPermission('giovani.gestione')?`<button class="btn btn-secondary btn-sm" onclick="YouthGroups.form(${g.id})">✏️ Modifica</button>`:''}</div>
        ${hasPermission('giovani.gestione')?`<div class="pastoral-group-card-footer"><button class="btn btn-danger btn-sm" onclick="YouthGroups.remove(${g.id})">🗑️ Elimina gruppo</button></div>`:''}
      </article>`;
    }).join('')||`<div class="pastoral-group-empty">${search?'Nessun gruppo trovato con i filtri selezionati.':'Nessun gruppo giovani per l’anno selezionato.'}${hasPermission('giovani.gestione')?'<p>Usa “Crea nuovo gruppo giovani” per aggiungerne uno.</p>':''}</div>`;
  }
  async function form(id=null) {
    const group=groups.find(g=>g.id===id)||{};
    try {
      const data=await apiJson('/api/giovani/responsabili');
      const choices=new Map(data.responsabili.map(u=>[u.id,u]));
      for(const user of group.catechisti||[])if(!choices.has(user.id))choices.set(user.id,user);
      document.getElementById('youthStaffChoices').innerHTML=[...choices.values()].map(user=>`<label class="choice-row"><input type="checkbox" value="${user.id}" ${(group.catechisti_ids||[]).includes(user.id)?'checked':''}>${escapeHtml(user.nominativo)}</label>`).join('');
      const chosenYear=group.anno_pastorale||selectedYear||currentYear;
      const adjacentYears=[-1,1].map(offset=>{const year=Number(currentYear.slice(0,4))+offset;return `${year}/${year+1}`;});
      const years=[...new Set([chosenYear,currentYear,...adjacentYears,...groups.map(g=>g.anno_pastorale)].filter(Boolean))];
      document.getElementById('youthGroupYear').innerHTML=years.sort().reverse().map(year=>`<option value="${escapeHtml(year)}">${escapeHtml(year)}</option>`).join('');
      const values={youthId:group.id||'',youthName:group.nome||'',youthGroupYear:chosenYear,youthStatus:group.stato||'pubblico',youthTime:group.orario_incontri||'',youthRoom:group.aula||'',youthNotes:group.note||'',youthCalendar:group.google_calendar_url||''};
      for(const [key,value] of Object.entries(values))document.getElementById(key).value=value;
      setGroupAges('youth',group);
      document.getElementById('youthFormTitle').textContent=id?'Modifica gruppo giovani':'Crea nuovo gruppo giovani';
      document.getElementById('youthSubmit').textContent=id?'Salva modifiche':'Crea gruppo';
      openModal('modalYouthGroup');
    } catch(error) {showToast(error.message,'error');}
  }
  async function save(event){event.preventDefault();const id=document.getElementById('youthId').value;try{await apiJson('/api/giovani/gruppi'+(id?'/'+id:''),{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:document.getElementById('youthName').value,anno_pastorale:document.getElementById('youthGroupYear').value,stato:document.getElementById('youthStatus').value,orario_incontri:document.getElementById('youthTime').value,aula:document.getElementById('youthRoom').value,note:document.getElementById('youthNotes').value,google_calendar_url:document.getElementById('youthCalendar').value,catechisti_ids:[...document.querySelectorAll('#youthStaffChoices input:checked')].map(input=>Number(input.value)),...readGroupAges('youth')})});selectedYear=document.getElementById('youthGroupYear').value.replace(/\s/g,'').replace('-','/');document.getElementById('youthSearch').value='';closeModal('modalYouthGroup');await load();}catch(error){showToast(error.message,'error');}}
  async function remove(id){if(!confirm('Eliminare questo gruppo giovani vuoto?'))return;try{await apiJson('/api/giovani/gruppi/'+id,{method:'DELETE'});await load();}catch(error){showToast(error.message,'error');}}
  return {load,render,selectYear,form,save,remove};
})();
