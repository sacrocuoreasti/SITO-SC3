/* Il server decide gli accessi; questa vista presenta gli stessi permessi nei menu. */
function hasPermission(key) {
  if(key.endsWith('_staff'))key=key.slice(0,-6)+'.staff';
  if(!currentUser)return false;
  if(Array.isArray(currentUser.permessi))return currentUser.permessi.includes(key);
  const roles=currentUser.tutti_i_ruoli||[currentUser.ruolo];
  if(roles.some(r=>['admin','segreteria','parroco'].includes(r)))return true;
  const module=key.split('.')[0];
  if(key==='giovani.staff')return roles.includes('responsabile_giovani');
  if(key.endsWith('.staff'))return roles.some(r=>(module==='oratorio'?['oratorio','animatore']:module==='catechismo'?['catechista']:['educatore','doposcuola']).includes(r));
  if(/\.(gestione|assegnazioni|tutti|cassa)$/.test(key))return module==='oratorio' && roles.includes('oratorio');
  return !['utenti','segreteria','anagrafica','excel'].includes(module);
}
const AccessUI=(()=>{
  let config=null,observer=null,timer=null;
  const roles=()=>config?.profili.filter(p=>p.tipo==='ruolo')||[];
  const privileges=()=>config?.profili.filter(p=>p.tipo==='privilegio')||[];
  const label=(key,fallback)=>config?.profili.find(p=>p.chiave===key)?.nome||fallback||currentUser?.nomi_profili?.[key]||key.replace(/_/g,' ');
  function keyFor(element) {
    if(element.dataset.permission)return element.dataset.permission;
    const code=element.getAttribute('onclick')||element.getAttribute('onsubmit')||'';
    let match=code.match(/switchSegreteriaTab\('([^']+)'/);
    if(match)return 'segreteria.'+match[1];
    match=code.match(/switchOratorioTab\('([^']+)'/);
    if(match)return 'oratorio.'+(match[1]==='allergie'?'cucina':match[1]);
    match=code.match(/StaffGroupRegister\.(\w+)\('(oratorio|doposcuola|giovani)'/);
    if(match)return ['reset','back'].includes(match[1])?null:match[2]+'.'+(['openRoster'].includes(match[1])?'elenco':['addForm','addPerson','removePerson'].includes(match[1])?'assegnazioni':'appelli');
    for(const [pattern,key] of [
      [/openCatechismoDates|openModalAppelloCatechismo|handleSalvaAppelloCatechismo/,'catechismo.appelli'],
      [/openModalStoricoIncontriCatechismo/,'catechismo.storico'],
      [/openModalAllergieGruppoCatechismo/,'catechismo.elenco'],
      [/openModalAssegnaRagazzoCatechismo|rimuoviRagazzoDaGruppo/,'catechismo.assegnazioni'],
      [/openModalNuovoGruppoCatechismo|openModalModificaGruppoCatechismo|eliminaGruppoCatechismo/,'catechismo.gestione'],
      [/openModalNuovoGruppoOratorio|openModalModificaGruppoOratorio|eliminaGruppoOratorio/,'oratorio.gestione'],
      [/openModalNuovoGruppoDoposcuola|openModalModificaGruppoDoposcuola|eliminaGruppoDoposcuola/,'doposcuola.gestione'],
      [/openModalNuovaAttivita|openModalModificaAttivita|eliminaAttivita|togglePubblicazioneAttivita/,'attivita.gestione'],
      [/annullaMiaIscrizione/,currentView==='famiglia'?'famiglia.iscrizioni':'attivita.iscrizioni'],
      [/openModalNuovaIscrizione|openUserEnrollmentManagement/,'attivita.iscrizioni'],
      [/openModalAssegnaPermessiUtente|openModalModificaRuoli|eseguiBulkPrivilegi/,'utenti.permessi'],
      [/openModalNuovoUtente|eliminaSingoloUtente|eseguiBulkStatoUtenti|eseguiBulkEliminaUtenti|resetPassword|openModalAdminResetPassword|toggleStatoUtente/,'utenti.gestione'],
      [/openModalOfferteDonazioni/,'famiglia.offerte'],
      [/openMemberAccount|handleSaveMemberAccount/,'famiglia.accessi'],
      [/reviewFamilyInvitation/,'famiglia.inviti'],
      [/openModalAggiungiFiglio|handleSalvaNuovoMembro/,'famiglia.membri'],
      [/openModalCalendarioComunita|salvaCalendarioComunita|eliminaCalendarioComunita/,'segreteria.calendari'],
      [/openModalNotizia|openModalEvento|eliminaEvento|togglePubblicazioneEvento/,'segreteria.avvisi'],
      [/openModalPagamentoQuota|apriRicevutaIscrizione|eseguiBulkPagamento/,'segreteria.pagamenti'],
      [/openModalGestisciBadgePersona|bulkAggiungiLista/,'anagrafica.liste'],
      [/openModalNuovaPersona|openModalNuovoMembroInFamiglia|eliminaSingolaPersona|eseguiBulkEliminaPersone/,'anagrafica.gestione'],
      [/exportExcel|eseguiBulkExportExcelPersone/,'excel.export'],
      [/handleSalvaNuovoMembro|openModalNuovoMembro/,'famiglia.membri'],
      [/openModalModificaPersona|handleSalvaModificaPersona/,currentView==='anagrafica'?'anagrafica.gestione':'famiglia.membri']])if(pattern.test(code))return key;
    match=code.match(/openModalAssegnaPersoneMassa\('([^']+)'/);
    if(match)return (match[1].startsWith('oratorio')?'oratorio':match[1])+'.assegnazioni';
    return null;
  }
  function gate(element,allowed) {
    if(!allowed){if(!element.dataset.aclHidden)element.dataset.aclDisplay=element.style.display;element.dataset.aclHidden='1';element.style.display='none';}
    else if(element.dataset.aclHidden){element.style.display=element.dataset.aclDisplay||'';delete element.dataset.aclHidden;delete element.dataset.aclDisplay;}
  }
  function apply() {
    if(!currentUser || !Array.isArray(currentUser.permessi))return;
    document.querySelectorAll('.nav-item[data-view]').forEach(link=>{
      const view=link.dataset.view;let allowed=hasPermission(view);
      if(view==='giovani' && currentUser.is_admin)allowed=false;
      if(['oratorio','catechismo','doposcuola'].includes(view))allowed=allowed && !!(enrollmentOptions?.gruppi?.[view]?.length || enrollmentOptions?.gruppi_iscritti?.[view]?.length);
      link.style.display=allowed?'flex':'none';
    });
    document.querySelectorAll('[data-permission],button[onclick],form[onsubmit]').forEach(element=>{
      const key=keyFor(element);if(!key)return;
      const allowed=hasPermission(key);
      gate(element,allowed);
    });
    const mappings={
      tabContentSegIscrizioni:'segreteria.iscrizioni',tabContentSegListe:'segreteria.liste',tabContentSegCelebrazioni:'segreteria.celebrazioni',tabContentSegHomepage:'segreteria.homepage',tabContentSegConfigurazioni:'segreteria.configurazioni',tabContentSegCampiAccount:'segreteria.campi_account',
      dashAttivitaList:'dashboard.attivita',dashWeeklyCalendar:'dashboard.settimana',dashAvvisiContainer:'dashboard.settimana',dashKpiGrid:'dashboard.cassa',activityTimeFilter:'attivita.passati',
      familyMembersGrid:'famiglia.membri',famigliaInfoSummary:'famiglia.membri',familyInvitationPanel:'famiglia.inviti',
      activitiesCatalogGrid:'attivita.catalogo',anagraficaFamiglieTreeContainer:'anagrafica.elenco',
      tabContentOraEstivo:'oratorio.estivo',tabContentOraInvernale:'oratorio.invernale',
      tabContentOraAllergie:'oratorio.cucina',tbodySegreteriaCalendari:'segreteria.calendari',tableSegreteriaEventi:'segreteria.avvisi'};
    for(const [id,key] of Object.entries(mappings)){const el=document.getElementById(id);if(el)gate(el,hasPermission(key));}
    for(const label of ['sectionLabelGestione','sectionLabelPastorale']){
      const modules=label==='sectionLabelGestione'?['segreteria','anagrafica','excel','utenti']:['oratorio','catechismo','doposcuola','oratorio_staff','catechismo_staff','doposcuola_staff','giovani','giovani_staff'];
      const el=document.getElementById(label);if(el)el.style.display=modules.some(module=>document.querySelector(`.nav-item[data-view="${module}"]`)?.style.display!=='none' && hasPermission(module))?'block':'none';
    }
    document.querySelectorAll('h4,fieldset.family-section legend').forEach(heading=>{
      if(!/fascicolo sanitario|scheda sanitaria|allergie|intolleranze|terapie/i.test(heading.textContent||''))return;
      const module=heading.closest('#viewOratorio,#viewCatechismo,#viewDoposcuola,#viewOratorioStaff,#viewCatechismoStaff,#viewDoposcuolaStaff,#viewGiovani,#viewGiovaniStaff,#modalAllergieGruppoCatechismo');
      const key=module ? (module.id.includes('Giovani')?'giovani':module.id.includes('Oratorio')?'oratorio':module.id.includes('Doposcuola')?'doposcuola':'catechismo')+'.salute' : (currentView==='anagrafica'?'anagrafica':'famiglia')+'.salute';
      if(!hasPermission(key)) {
        if(heading.tagName==='LEGEND')heading.parentElement.style.display='none';
        else{heading.style.display='none';const next=heading.nextElementSibling;if(next && next.tagName==='DL')next.style.display='none';}
      }
    });
    document.querySelectorAll('[data-profile-section]').forEach(el=>{
      const name=el.dataset.profileSection;
      const prefix=hasPermission('anagrafica.gestione')?'anagrafica':'famiglia';
      const key=name==='documenti'?prefix+'.documenti':name==='contatti'?prefix+'.contatti':null;
      if(key){const allowed=hasPermission(key);gate(el,allowed);el.querySelectorAll('input,select,textarea').forEach(input=>{if(!allowed && !input.disabled){input.disabled=true;input.dataset.aclDisabled='1';}else if(allowed && input.dataset.aclDisabled){input.disabled=false;delete input.dataset.aclDisabled;}});}
    });
    document.querySelectorAll('.catechismo-history').forEach(el=>{
      const parent=el.closest('#catechismoDatesSection,#oratorioRegisterSection,#doposcuolaRegisterSection,#giovaniRegisterSection');
      if(parent){const category=parent.id.startsWith('catechismo')?'catechismo':parent.id.startsWith('oratorio')?'oratorio':parent.id.startsWith('giovani')?'giovani':'doposcuola';if(!hasPermission(category+'.storico'))el.style.display='none';}
    });
    const healthModal=document.getElementById('modalGroupHealth');
    if(healthModal?.dataset.category && (!hasPermission(healthModal.dataset.category+'.salute') || !hasPermission(healthModal.dataset.category+'.cucina'))){const content=document.getElementById('groupHealthContent');if(content.innerHTML)content.innerHTML='';}
    if(currentView && !hasPermission(currentView))navigateTo(currentView);
  }
  function start() {
    apply();if(observer || typeof MutationObserver==='undefined')return;
    observer=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(apply,0);});
    observer.observe(document.getElementById('appShell'),{childList:true,subtree:true});
    window.addEventListener('focus',()=>refresh().catch(()=>{}));
  }
  async function refresh() {
    const result=await apiJson('/api/auth/me');
    if(currentUser && (!result.user || currentUser.id!==result.user.id)){window.location.reload();return;}
    renderImpersonationBanner(result.impersonazione);
    if(result.user){currentUser=result.user;applyRolePermissions();apply();}
  }
  function profileOptions(key) {
    document.getElementById('accessProfile').innerHTML=config.profili.map(p=>`<option value="${p.chiave}">${escapeHtml(p.nome)} · ${p.tipo==='ruolo'?'ruolo':'privilegio'}</option>`).join('');
    document.getElementById('accessProfile').value=key;
  }
  async function load() {
    if(!currentUser.is_admin){document.getElementById('accessManager').style.display='none';return;}
    document.getElementById('accessManager').style.display='';
    config=await apiJson('/api/accessi');
    profileOptions('utente');showProfile();populate();
  }
  function populate() {
    if(!config)return;
    for(const id of ['assegnaPermessoRuoloPrimario','nuovoUtenteRuolo','ruoloPrimarioSelect']){
      const select=document.getElementById(id);if(!select)continue;const previous=select.value;
      select.innerHTML=roles().map(p=>`<option value="${p.chiave}">${escapeHtml(p.nome)}</option>`).join('');select.value=roles().some(p=>p.chiave===previous)?previous:'utente';
    }
    const filter=document.getElementById('filterUtentiRuolo');if(filter)filter.innerHTML='<option value="">Tutti i ruoli e privilegi</option>'+config.profili.map(p=>`<option value="${p.chiave}">${escapeHtml(p.nome)}</option>`).join('');
    for(const [id,attr] of [['assignmentPrivileges','class="chk-extra-perm"'],['newUserPrivileges','class="new-user-privilege"'],['editUserPrivileges','name="privilegiCheck"']]){
      const target=document.getElementById(id);if(target)target.innerHTML=privileges().map(p=>`<label class="choice-row"><input type="checkbox" ${attr} value="${p.chiave}"><span>${escapeHtml(p.nome)}</span></label>`).join('');
    }
    const bulk=document.getElementById('bulkRuoloSelect');if(bulk)bulk.innerHTML=privileges().map(p=>`<option value="${p.chiave}">${escapeHtml(p.nome)}</option>`).join('');
  }
  function showProfile() {
    const key=document.getElementById('accessProfile').value,profile=config.profili.find(p=>p.chiave===key);if(!profile)return;
    const locked=key==='admin';const grants=new Set(profile.permessi);
    document.getElementById('accessProfileName').value=profile.nome;document.getElementById('accessProfileName').disabled=locked;document.getElementById('accessSave').disabled=locked;
    document.getElementById('accessDelete').disabled=profile.predefinito;
    document.getElementById('accessDeleteHelp').textContent=profile.predefinito?'Profilo di sistema: non eliminabile.':'Puoi eliminare questo profilo dopo aver rimosso le sue assegnazioni agli account.';
    document.getElementById('accessTree').innerHTML=config.viste.map(section=>`<fieldset class="access-section"><legend><label><input class="access-check" type="checkbox" value="${section.chiave}" ${grants.has(section.chiave)?'checked':''} ${locked?'disabled':''} onchange="AccessUI.toggleSection(this)"> ${escapeHtml(section.nome)}</label></legend><div class="access-children">${section.figli.map(child=>`<label><input class="access-check" type="checkbox" value="${child.chiave}" ${grants.has(child.chiave)?'checked':''} ${locked||child.solo_admin?'disabled':''} onchange="AccessUI.toggleChild(this)"> ${escapeHtml(child.nome)}</label>`).join('')}</div></fieldset>`).join('');
  }
  function toggleSection(box){document.querySelectorAll('#accessTree .access-check').forEach(child=>{if(child.value.startsWith(box.value+'.') && !child.disabled)child.checked=box.checked;});}
  function toggleChild(box){if(box.checked){const module=box.value.split('.')[0];const parent=document.querySelector(`#accessTree input[value="${module}"]`);if(parent)parent.checked=true;if(['appelli','elenco','salute','gestione','assegnazioni','tutti','cucina','avvisi'].includes(box.value.split('.')[1])){const staff=document.querySelector(`#accessTree input[value="${module}.staff"]`);if(staff)staff.checked=true;}}}
  async function save(event){event.preventDefault();const key=document.getElementById('accessProfile').value;const button=document.getElementById('accessSave');button.disabled=true;
    try{const data=await apiJson('/api/accessi/'+key,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:document.getElementById('accessProfileName').value,permessi:[...document.querySelectorAll('#accessTree .access-check:checked')].filter(x=>!x.disabled).map(x=>x.value)})});config.profili=config.profili.map(p=>p.chiave===key?data.profilo:p);profileOptions(key);populate();filtraUtenti();await refresh();showToast('Nome e permessi salvati','success');}
    catch(error){showToast(error.message,'error');}finally{button.disabled=key==='admin';}}
  async function create(event){event.preventDefault();try{const data=await apiJson('/api/accessi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:document.getElementById('accessNewName').value,chiave:document.getElementById('accessNewKey').value,tipo:document.getElementById('accessNewType').value,permessi:[]})});await load();document.getElementById('accessProfile').value=data.profilo.chiave;showProfile();showToast('Profilo creato: scegli le viste e salva prima di assegnarlo','success');}catch(error){showToast(error.message,'error');}}
  async function remove(){const key=document.getElementById('accessProfile').value,profile=config.profili.find(p=>p.chiave===key);if(!profile || profile.predefinito || !confirm(`Eliminare il profilo «${profile.nome}»?`))return;try{await apiJson('/api/accessi/'+key,{method:'DELETE'});await load();showToast('Profilo eliminato','success');}catch(error){showToast(error.message,'error');}}
  return {label,apply,start,refresh,load,populate,showProfile,toggleSection,toggleChild,save,create,remove};
})();
