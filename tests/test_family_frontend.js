const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const template=fs.readFileSync('templates/index.html','utf8');
assert.ok(!template.includes('id="modPersonaBattesimoInput"'));
assert.ok(template.includes('id="modPersonaBattesimoLink"'));
const elements = new Map();
const selected = [];
const requests = [];
const nodes = id => {
  if (!elements.has(id)) elements.set(id, { value:'', style:{}, dataset:{}, hidden:false, disabled:false, classList:{add(){},remove(){},toggle(){},contains(){return false;}}, textContent:'', _html:'',
    set innerHTML(value) { this._html=value; if (id==='iscrizioneAttivitaSelect') this.value='7'; },
    get innerHTML() { return this._html; },
  });
  return elements.get(id);
};
const people = [{codice_fiscale:'RSSMRA80A01H501U',nominativo:'Genitore di prova',eta:46}, {codice_fiscale:'RSSLGI14A01H501A',nominativo:'Figlio di prova',eta:12}];
const fixtures = {
  '/api/attivita':{attivita:[{id:7,titolo:'Attività selezionata',eta_min:0,eta_max:99,quota_iscrizione:10,campi_personalizzati:[{nome:'Taglia',chiave:'taglia',obbligatorio:true}]}]},
  '/api/famiglie/calendari-gruppi':{calendari:[]},
  '/api/famiglie/opportunita':{attivita:{7:{partecipanti:people.map(p=>p.codice_fiscale),gia_iscritto:false}},gruppi:{oratorio:[],catechismo:[],doposcuola:[]}},
  '/api/famiglie/mia':{nucleo:{id:1,componenti:people},puo_gestire:true},
  '/api/iscrizioni?solo_mie=true':{iscrizioni:[]},
  '/api/configurazioni/clausole':{clausole:[{id:1,obbligatoria:true,titolo:'Clausola',testo:'Testo'}]},
  '/api/auth/registration-options':{consensi:{privacy:{titolo:'Privacy',testo:'Per la famiglia'},foto_video:{titolo:'Foto e video',testo:'Per la famiglia'}},salute:{allergie:['Polline'],intolleranze_alimentari:['Lattosio'],terapie_medicinali:['Terapia prescritta']}},
};
const context = vm.createContext({
  console, AbortController, setTimeout, clearTimeout, confirm:()=>true,
  window:{addEventListener(){}},
  document:{addEventListener(){},querySelector(selector){return /^\.(oratorio|catechismo|doposcuola)-nav$/.test(selector) ? nodes(selector) : null;},getElementById:nodes,querySelectorAll(selector){
    if(selector==='.family-participant:checked')return selected.map(value=>({value}));
    if(selector==='#iscrizioneClausoleContainer .clause-checkbox')return [{dataset:{id:'1',req:'true'},checked:true}];
    return [];
  }},
  fetch:async(url,options={})=>{
    requests.push({url,options});
    return {ok:true,headers:{get:()=> 'application/json'},json:async()=>url==='/api/iscrizioni'?{success:true,message:'Registrato'}:fixtures[url] || (url==='/api/attivita?solo_attive=false' ? fixtures['/api/attivita']:undefined)};
  },
});
vm.runInContext(fs.readFileSync('static/js/group-calendar.js','utf8'),context);
vm.runInContext(fs.readFileSync('static/js/portal-views.js','utf8'),context);
vm.runInContext(fs.readFileSync('static/js/access-control.js','utf8'),context);
vm.runInContext(fs.readFileSync('static/js/app.js','utf8'),context);
const loadDashboardOriginal=context.loadDashboard;
vm.runInContext("currentUser={codice_fiscale:'RSSMRA80A01H501U',tutti_i_ruoli:['utente'],is_capofamiglia:true}; showToast=()=>{}; loadDashboard=async()=>{};",context);
(async()=>{
  await context.openModalNuovaIscrizione(7);
  assert.equal(nodes('iscrizioneAttivitaSelect').style.display,'none');
  assert.equal(nodes('iscrizioneAttivitaTitolo').textContent,'Attività selezionata');
  assert.equal(nodes('iscrizioneAttivitaSelect').required,false);
  assert.ok(nodes('iscrizionePartecipantiCheckbox').innerHTML.includes('type="checkbox"'));
  assert.equal(nodes('btnConfermaIscrizione').disabled,true);
  selected.push(...people.map(p=>p.codice_fiscale));
  context.updateFamilyEnrollmentSelection();
  assert.equal(nodes('btnConfermaIscrizione').disabled,false);
  assert.ok(nodes('previewQuotaAttivita').textContent.includes('20.00'));
  for(const person of people) assert.ok(nodes('iscrizioneCampiEventoContainer').innerHTML.includes('data-cf="'+person.codice_fiscale+'"'));
  await context.handleSalvaIscrizione({preventDefault(){}});
  const posted=requests.filter(r=>r.url==='/api/iscrizioni'&&r.options.method==='POST');
  assert.equal(posted.length,1);
  assert.deepEqual(JSON.parse(posted[0].options.body).partecipanti,people.map(p=>p.codice_fiscale));
  assert.equal(JSON.parse(posted[0].options.body).attivita_id,7);
  assert.ok(!('clausole_accettate' in JSON.parse(posted[0].options.body)));
  assert.ok(!requests.some(r=>r.url==='/api/configurazioni/clausole'));
  nodes('regPassword').value='password-test-123';
  nodes('regConfermaPassword').value='diversa';
  assert.equal(context.passwordMismatch(),true);
  nodes('regConfermaPassword').value='password-test-123';
  assert.equal(context.passwordMismatch(),false);
  context.setGroupAges('test',{eta_min:0,eta_max:14});
  assert.deepEqual(JSON.parse(JSON.stringify(context.readGroupAges('test'))),{eta_min:0,eta_max:14});
  context.setGroupAges('test',{});
  assert.deepEqual(JSON.parse(JSON.stringify(context.readGroupAges('test'))),{eta_min:null,eta_max:null});
  await context.renderRegistrationConsents('registrationConsents');
  const html=nodes('registrationConsents').innerHTML;
  assert.equal((html.match(/type="checkbox"/g)||[]).length,2);
  assert.equal((html.match(/ required/g)||[]).length,2);
  assert.ok(!html.includes(' checked'));
  nodes('membroAllergie').value='Allergia preesistente';
  await context.renderHealthSections('membro');
  assert.equal(nodes('membroAllergie').value,'Allergia preesistente');
  assert.ok(nodes('membroTerapiePills').innerHTML.includes('Terapia prescritta'));
  fixtures['/api/attivita']={attivita:[]};
  fixtures['/api/impostazioni/dati-pubblici']={impostazioni:{},avvisi:[]};
  fixtures['/api/celebrazioni?sezione=messe']={messe:[]};
  fixtures['/api/impostazioni/calendari?solo_pubblici=true']={calendari:[]};
  await loadDashboardOriginal();
  await context.loadUserCalendari();
  assert.ok(requests.some(r=>r.url==='/api/impostazioni/calendari?solo_pubblici=true'));
  assert.ok(nodes('dashUserCalendariGrid').innerHTML.includes('Nessun calendario'));
  // Fresh eligibility controls buttons, even without opening the family screen.
  const activity={id:7,titolo:'Evento famiglia',categoria:'evento',quota_iscrizione:0,posti_disponibili:null,eta_min:null,eta_max:null};
  fixtures['/api/attivita']={attivita:[activity]};
  const option=fixtures['/api/famiglie/opportunita'].attivita[7];
  option.partecipanti=people.map(p=>p.codice_fiscale); option.gia_iscritto=false;
  await context.loadAttivita();
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes('Iscriviti</button>'));
  option.partecipanti=[people[1].codice_fiscale]; option.gia_iscritto=true;
  await context.loadAttivita();
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes('Gestisci iscrizione'));
  assert.ok(!nodes('activitiesCatalogGrid').innerHTML.includes('Iscriviti</button>'));
  option.partecipanti=[];
  await context.loadAttivita();
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes('Gestisci iscrizione'));
  assert.ok(!nodes('activitiesCatalogGrid').innerHTML.includes('openModalNuovaIscrizione'));
  assert.equal(context.ageEligible({eta:null},{eta_min:null,eta_max:null}),true);
  assert.equal(context.ageEligible({eta:100},{eta_min:18,eta_max:null}),true);
  assert.equal(context.ageEligible({eta:null},{eta_min:0,eta_max:10}),false);
  assert.equal(context.ageEligible({eta:2},{eta_min:null,eta_max:0}),false);
  assert.equal(context.ageRangeLabel({eta_min:null,eta_max:null}),'Senza limiti di età');
  nodes('attEtaMin').value=''; assert.equal(context.optionalAgeValue('attEtaMin'),null);
  nodes('attEtaMin').value='0'; assert.equal(context.optionalAgeValue('attEtaMin'),0);
  for (const category of ['catechismo','doposcuola']) {
    fixtures['/api/famiglie/opportunita'].gruppi[category]=[{id:3,nome:'Gruppo disponibile '+category,eta_min:6,eta_max:14,partecipanti:[people[1]]}];
    fixtures['/api/famiglie/registri-gruppi/'+category]={gruppi:[]};
    await context[category==='catechismo' ? 'loadCatechismoParentView' : 'loadDoposcuolaParentView']();
    const content=nodes(category+'ParentContainer').innerHTML;
    assert.ok(content.includes('Gruppo disponibile '+category));
    assert.ok(content.includes('class="group-participant"'));
    assert.ok(!content.includes('NON ANCORA ISCRITTO'));
    assert.equal(nodes('.'+category+'-nav').style.display,'flex');
    fixtures['/api/famiglie/opportunita'].gruppi[category]=[];
    await context[category==='catechismo' ? 'loadCatechismoParentView' : 'loadDoposcuolaParentView']();
    assert.equal(nodes(category+'ParentContainer').innerHTML,'');
    assert.equal(nodes('.'+category+'-nav').style.display,'none');
  }
  assert.equal(nodes('sectionLabelPastorale').style.display,'none');
  const dashboard=template.slice(template.indexOf('id="viewDashboard"'),template.indexOf('<!-- KPI Grid -->'));
  assert.ok(!dashboard.includes('openModalNuovaIscrizione'));
  assert.ok(!dashboard.includes('openModalOfferteDonazioni'));
  assert.ok(!template.includes('Iscrivi un Partecipante'));
  assert.equal(context.visibleDocumentKind('identita',null),true);
  assert.equal(context.visibleDocumentKind('battesimo',0),true);
  for(const [kind,threshold] of [['comunione',8],['cresima',12],['matrimonio',30]]) {
    assert.equal(context.visibleDocumentKind(kind,null),false);
    assert.equal(context.visibleDocumentKind(kind,threshold),false);
    assert.equal(context.visibleDocumentKind(kind,threshold+1),true);
  }
  for(const modal of ['modalNuovaPersona','modalModificaPersona','modalAggiungiFiglio','modalSchedaPersonaVisualizzazione']) {
    const start=template.indexOf('id="'+modal+'"');
    const end=template.indexOf('class="modal-footer"',start);
    const contents=template.slice(start,end);
    assert.equal((contents.match(/data-profile-section=/g)||[]).length,5);
    for(const section of ['anagrafica','residenza','contatti','documenti','altro']) assert.ok(contents.includes('data-profile-section="'+section+'"'));
  }
  await context.renderRegistrationConsents('memberAccountConsents',true);
  assert.equal((nodes('memberAccountConsents').innerHTML.match(/ required/g)||[]).length,2);
  assert.ok(!nodes('memberAccountConsents').innerHTML.includes(' checked'));
  const url='https://calendar.google.com/calendar/embed?src=test%40group.calendar.google.com';
  const calendar=context.groupCalendarMarkup({calendar_api_url:'/api/calendari-gruppi/catechismo/3',calendar_embed_url:url});
  assert.ok(calendar.includes('Calendario mensile'));
  assert.ok(!calendar.includes('<iframe'));
  assert.equal(context.groupCalendarMarkup({calendar_embed_url:'javascript:alert(1)'}),'');
  assert.ok(context.withdrawButton({id:5,puo_disiscriversi:true,stato:'confermata'}).includes('annullaMiaIscrizione(5)'));
  assert.equal(context.withdrawButton({id:5,puo_disiscriversi:true,stato:'annullata'}),'');
  assert.equal(context.withdrawButton({id:5,puo_disiscriversi:false,stato:'confermata'}),'');
  fixtures['/api/iscrizioni/5/disiscrivi']={success:true,message:'Disiscrizione completata'};
  await context.annullaMiaIscrizione(5);
  assert.ok(requests.some(r=>r.url==='/api/iscrizioni/5/disiscrivi' && r.options.method==='POST'));
  for(const category of ['catechismo','doposcuola','oratorio']) {
    const group={id:9,nome:'Gruppo <prova>',anno_pastorale:'2026/2027',anno_scolastico:category==='doposcuola' ? '2026/2027':null,anno_catechismo:'Terza elementare',fascia_eta:'Scuola primaria',tipo_oratorio:'invernale',orario_incontri:'Sabato 15:30',aula:'Aula Don Bosco',catechista_nome:'Referente Test',educatore_nome:'Referente Test',animatori_nomi:'Referente Test',note:'Portare il quaderno <test>',totale_ragazzi:7,partecipanti:[people[1]]};
    const card=context.availableGroupCards(category,[group]);
    for(const info of ['2026/2027','Sabato 15:30','Aula Don Bosco','Referente Test','Portare il quaderno &lt;test&gt;','Chi vuoi iscrivere?']) assert.ok(card.includes(info));
    assert.ok(card.includes('Gruppo &lt;prova&gt;'));
    assert.ok(card.includes('family-enrollment-card--'+category));
    assert.ok(card.includes('type="submit" class="btn btn-primary" disabled'));
    assert.ok(!card.includes('openModalModificaGruppo'));
  }
  const selection={textContent:''}, submit={disabled:true};
  let count=2;
  const fakeForm={querySelectorAll:()=>Array(count).fill({}),querySelector:selector=>selector==='.family-enrollment-selection' ? selection:submit};
  context.updateGroupEnrollmentSelection({closest:()=>fakeForm});
  assert.equal(submit.disabled,false);assert.equal(selection.textContent,'2 figli selezionati');
  count=0;context.updateGroupEnrollmentSelection({closest:()=>fakeForm});assert.equal(submit.disabled,true);
  const monthDays=vm.runInContext("GroupCalendar.days('2028-02')",context);
  assert.equal(monthDays.length,42);assert.ok(monthDays.includes('2028-02-29'));
  assert.equal(new Date(monthDays[0]+'T12:00:00').getDay(),1);
  fixtures['/api/famiglie/opportunita'].gruppi_iscritti={catechismo:[{id:3,nome:'Gruppo già frequentato'}]};
  fixtures['/api/famiglie/registri-gruppi/catechismo']={gruppi:[{id:3,nome:'Gruppo già frequentato',componenti:[{nominativo:'Figlio iscritto',presenti:1,assenti:0,percentuale:100,presenze:[{data:'2026-11-01',titolo_incontro:'Incontro salvato',presente:true}]}]}]};
  await context.loadCatechismoParentView();
  assert.equal(nodes('.catechismo-nav').style.display,'flex');
  assert.ok(nodes('catechismoParentContainer').innerHTML.includes('catechismoAssignedContainer'));
  assert.ok(nodes('catechismoAssignedContainer').innerHTML.includes('Incontro salvato'));
  assert.ok(!nodes('catechismoParentContainer').innerHTML.includes('Iscrivi al gruppo'));
  // Staff: scegli la data nell'elenco, compila una sezione dedicata e torna all'elenco aggiornato.
  vm.runInContext("currentUser={tutti_i_ruoli:['admin']}; cacheGruppiCatechismo=[{id:3,nome:'Gruppo di prova',anno_pastorale:'2026/2027'}];",context);
  const register={mese:'2026-11',incontri_registrati:1,studenti:[{codice_fiscale:people[1].codice_fiscale,nominativo:'Figlio di prova',presenze_map:{'2026-11-01':true},presenti:1,totale_incontri:1,percentuale:100}],date_incontri:[{data:'2026-11-01',titolo_incontro:'Primo incontro',registrato:true,presenti_count:1,assenti_count:0},{data:'2026-11-08',titolo_incontro:'Secondo <incontro>',registrato:false,da_google:true}]};
  fixtures['/api/catechismo/gruppi/3/registro?periodo=anno']=register;
  for(const day of ['2026-11-08','2026-11-15']) fixtures['/api/catechismo/gruppi/3/registro?mese=2026-11&giorno='+day]=register;
  await context.openCatechismoDates(3);
  assert.equal(nodes('catechismoDatesSection').style.display,'block');
  assert.equal(nodes('catechismoAttendanceSection').style.display,'none');
  assert.ok(nodes('catechismoDatesList').innerHTML.includes('Appello salvato'));
  assert.ok(nodes('catechismoDatesList').innerHTML.includes("openModalAppelloCatechismo(3,'2026-11-08')"));
  assert.ok(nodes('catechismoDatesList').innerHTML.includes('Secondo &lt;incontro&gt;'));
  await context.openModalAppelloCatechismo(3,'2026-11-08');
  assert.equal(nodes('catechismoDatesSection').style.display,'none');
  assert.equal(nodes('catechismoAttendanceSection').style.display,'block');
  assert.equal(nodes('appelloDataIncontro').value,'2026-11-08');
  assert.equal(nodes('appelloTitoloIncontro').value,'Secondo <incontro>');
  context.togglePresenzaRagazzoCatechismo(people[1].codice_fiscale,false);
  fixtures['/api/catechismo/presenze']={success:true};
  register.date_incontri[1].registrato=true;register.date_incontri[1].presenti_count=0;register.date_incontri[1].assenti_count=1;
  register.studenti[0].presenze_map['2026-11-08']=false;
  await context.handleSalvaAppelloCatechismo({preventDefault(){}});
  const attendancePost=requests.find(r=>r.url==='/api/catechismo/presenze' && r.options.method==='POST');
  assert.equal(JSON.parse(attendancePost.options.body).data,'2026-11-08');
  assert.equal(JSON.parse(attendancePost.options.body).presenze[0].presente,false);
  assert.equal(nodes('catechismoDatesSection').style.display,'block');
  assert.ok(nodes('catechismoDatesList').innerHTML.includes('0 presenti · 1 assenti'));
  await context.openModalAppelloCatechismo(3,'2026-11-08');
  assert.equal(vm.runInContext("statoPresenzeCorrentiCatechismo['"+people[1].codice_fiscale+"']",context),false);
  await context.tornaDateCatechismo();
  context.tornaGruppiCatechismo();
  assert.equal(nodes('catechismoGroupOverview').style.display,'block');
  const originalFetch=context.fetch;
  context.fetch=async()=>{throw new Error('Registro temporaneamente non disponibile');};
  await context.openModalAppelloCatechismo(3,'2026-11-15');
  assert.equal(nodes('btnSalvaRegistroCatechismo').disabled,true);
  assert.equal(vm.runInContext('Object.keys(statoPresenzeCorrentiCatechismo).length',context),0);
  assert.ok(nodes('registroElettronicoCatechismoBody').innerHTML.includes('Registro temporaneamente non disponibile'));
  context.fetch=originalFetch;
  await context.tornaDateCatechismo();
  assert.ok(!template.includes('id="modalAppelloCatechismo"'));
  fixtures['/api/catechismo/gruppi/3/allergie']={gruppo:{id:3,nome:'Gruppo prova'},ragazzi:[{codice_fiscale:people[1].codice_fiscale,nome:'Anna',cognome:'Verdi',nominativo:'Verdi Anna',genitori:[{ruolo:'Padre',nominativo:'Genitore prova',telefono:'123456'}],allergie:'Polline',intolleranze_alimentari:'Lattosio',terapie_medicinali:'Terapia test',note_mediche:'Note test'},{nome:'Luca',cognome:'Bianchi',genitori:[]}]};
  await context.openModalAllergieGruppoCatechismo(3);
  const roster=nodes('allergieGruppoContent').innerHTML;
  assert.ok(roster.indexOf('Bianchi Luca')<roster.indexOf('Verdi Anna'));
  for(const value of ['Aggiungi ragazzo','<details','Genitore prova','123456','Fascicolo sanitario','Terapia test','Lattosio']) assert.ok(roster.includes(value));
  vm.runInContext("cacheGruppiCatechismo=[{id:3,nome:'Gruppo prova',eta_min:8,eta_max:14,ragazzi:[{codice_fiscale:'"+people[1].codice_fiscale+"'}]}]; currentMassaTipo='catechismo';",context);
  fixtures['/api/catechismo/gruppi/3/assegnabili']={persone:[...people,{codice_fiscale:'NEWCODE',nominativo:'Persona assegnabile',eta:10}]};
  nodes('massaSelectGruppoDestinazione').value='3';
  await context.aggiornaAssegnabiliMassa();
  assert.ok(nodes('massaTablePersoneBody').innerHTML.includes('Persona assegnabile'));
  assert.ok(!nodes('massaTablePersoneBody').innerHTML.includes('Genitore di prova'));
  assert.ok(!nodes('massaTablePersoneBody').innerHTML.includes('Figlio di prova'));
  nodes('massaSelectGruppoDestinazione').value='';context.filtraPersoneMassa();
  assert.ok(!nodes('massaTablePersoneBody').innerHTML.includes('type="checkbox"'));
  for(const id of ['catAnnoPercorso','modCatAnnoCatechismo','modCatAttivitaSelect']) assert.ok(!template.includes('id="'+id+'"'));
  // Panoramica: solo iscritti non conclusi, calendario settimanale e calendari nel menu.
  const future={...activity,id:31,titolo:'Evento futuro iscritto',data_inizio:'2099-01-01'};
  const past={...activity,id:32,titolo:'Evento passato iscritto',data_fine:'2000-01-01'};
  const available={...activity,id:33,titolo:'Evento futuro disponibile',data_inizio:'2099-01-01'};
  fixtures['/api/attivita']={attivita:[future,past,available]};
  fixtures['/api/famiglie/opportunita'].attivita={31:{gia_iscritto:true,partecipanti:[]},32:{gia_iscritto:true,partecipanti:[]},33:{gia_iscritto:false,partecipanti:[people[1].codice_fiscale]}};
  vm.runInContext("currentUser={codice_fiscale:'RSSMRA80A01H501U',tutti_i_ruoli:['utente']};",context);
  await loadDashboardOriginal();
  assert.equal(nodes('dashKpiGrid').style.display,'none');
  assert.ok(nodes('dashAttivitaList').innerHTML.includes(future.titolo));
  assert.ok(!nodes('dashAttivitaList').innerHTML.includes(past.titolo));
  assert.ok(!nodes('dashAttivitaList').innerHTML.includes(available.titolo));
  await context.loadAttivita();context.filterAttivitaByTime('past');
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes(past.titolo));
  assert.ok(!nodes('activitiesCatalogGrid').innerHTML.includes(future.titolo));
  assert.equal((context.activityEnrollmentAction(future).match(/<button/g)||[]).length,1);
  assert.ok(context.activityEnrollmentAction(future).includes('Gestisci iscrizione'));
  const days=context.weeklyDays();assert.equal(days.length,7);assert.equal(new Date(days[0]+'T12:00:00').getDay(),1);
  assert.deepEqual(Array.from(context.celebrationWeekdays('Lunedì - Venerdì')),[0,1,2,3,4]);
  assert.deepEqual(Array.from(context.celebrationWeekdays('Venerdì - Lunedì')),[4,5,6,0]);
  context.renderDashboardWeek([{giorno:'Lunedì - Venerdì',titolo:'Messa feriale',orario:'ore 18:00',is_attivo:true}],[{titolo:'Avviso datato',data_evento:days[1],contenuto:'Incontro comunitario'}],{});
  assert.equal((nodes('dashWeeklyCalendar').innerHTML.match(/class="weekly-day /g)||[]).length,7);
  assert.equal((nodes('dashWeeklyCalendar').innerHTML.match(/Messa feriale/g)||[]).length,5);
  assert.ok(nodes('dashWeeklyCalendar').innerHTML.includes('Avviso datato'));
  // Messe, liturgia e avvenimenti datati condividono la settimana senza ripetere le date specifiche.
  const dated=[{sezione:'messe',giorno:'Lunedì',titolo:'Messa settimanale'}, {sezione:'liturgia',giorno:'Martedì',titolo:'Liturgia settimanale'}, {sezione:'avvenimenti',data_specifica:days[2],titolo:'Avvenimento unico'}];
  const italian=days[3].split('-').reverse().join('/');
  context.renderDashboardWeek(dated,[{titolo:'Avviso italiano',data_evento:italian,contenuto:'Testo'}],{});
  for(const title of ['Messa settimanale','Liturgia settimanale','Avvenimento unico','Avviso italiano'])assert.ok(nodes('dashWeeklyCalendar').innerHTML.includes(title));
  assert.equal((nodes('dashWeeklyCalendar').innerHTML.match(/Avvenimento unico/g)||[]).length,1);
  assert.ok(!nodes('dashAvvisiContainer').innerHTML.includes('Avvenimento unico'));
  context.moveDashboardWeek(1);
  assert.ok(!nodes('dashWeeklyCalendar').innerHTML.includes('Avvenimento unico'));
  assert.ok(nodes('dashWeeklyCalendar').innerHTML.includes('Messa settimanale'));
  context.moveDashboardWeek(0);
  assert.ok(context.groupCalendarMarkup({calendar_api_url:'/api/impostazioni/calendari-gruppi/catechismo/1'}).includes('Calendario mensile'));
  context.openModalNuovaCelebrazione();nodes('celSezione').value='avvenimenti';context.updateCelebrationDateMode();
  assert.equal(nodes('celWeekdaysGroup').hidden,true);assert.equal(nodes('celDataSpecifica').required,true);
  nodes('celDataSpecifica').value=days[2];nodes('celTitolo').value='Avvenimento datato';
  fixtures['/api/celebrazioni']={success:true,celebrazioni:[],avvisi:[]};
  await context.handleSalvaCelebrazione({preventDefault(){}});
  const occurrencePost=requests.find(r=>r.url==='/api/celebrazioni' && r.options.method==='POST');
  assert.equal(JSON.parse(occurrencePost.options.body).data_specifica,days[2]);
  assert.equal(JSON.parse(occurrencePost.options.body).giorno,'');
  context.openModalNuovoEvento('celebrazioni');nodes('eventoTitolo').value='Avviso dalla liturgia';nodes('eventoContenuto').value='Testo avviso';nodes('eventoData').value=days[3];
  fixtures['/api/celebrazioni/avvisi']={success:true};
  await context.handleSalvaNuovoEvento({preventDefault(){}});
  assert.ok(requests.some(r=>r.url==='/api/celebrazioni/avvisi' && r.options.method==='POST'));
  context.openModalNuovoEvento();assert.equal(nodes('eventoCategoria').disabled,false);
  assert.ok(template.indexOf('id="dashUserCalendariGrid"')>template.indexOf('id="viewCalendari"'));
  // Stesso percorso date → appello per oratorio e doposcuola, con salvataggio sulla data scelta.
  const staffRegister=vm.runInContext('StaffGroupRegister',context);
  for(const category of ['oratorio','doposcuola']) {
    const route='/api/calendari-gruppi/'+category+'/9/registro';
    const data={...register,gruppo:{id:9,nome:'Gruppo '+category,anno_pastorale:'2026/2027'},puo_cancellare:true};
    fixtures[route+'?periodo=anno']=data;fixtures[route+'?mese=2026-11']=data;fixtures[route]={success:true};
    await staffRegister.openDates(category,9);
    assert.ok(nodes(category+'RegisterSection').innerHTML.includes('Storico incontri'));
    await staffRegister.openAttendance(category,'2026-11-08');
    assert.ok(nodes(category+'RegisterSection').innerHTML.includes('attendance-matrix'));
    assert.ok(nodes(category+'RegisterSection').innerHTML.includes('% Pres.'));
    staffRegister.mark(category,people[1].codice_fiscale,false);
    assert.equal(nodes(category+'AttendanceCount').textContent,'0 presenti · 1 assenti');
    nodes(category+'MeetingTitle').value='Incontro di prova';nodes(category+'MeetingPercentage').checked=true;
    await staffRegister.save(category,{preventDefault(){}});
    const post=requests.find(r=>r.url===route && r.options.method==='POST');
    assert.equal(JSON.parse(post.options.body).data,'2026-11-08');
    assert.equal(JSON.parse(post.options.body).presenze[0].presente,false);
  }
  // Menu familiari e staff distinti: cambiare vista non miscela le due aree.
  vm.runInContext("currentUser={id:1,codice_fiscale:'RSSMRA80A01H501U',ruolo:'utente',tutti_i_ruoli:['utente','catechista','oratorio','educatore'],permessi:['oratorio','catechismo','doposcuola',...['oratorio','catechismo','doposcuola'].flatMap(c=>['staff','salute','cucina','calendario','storico','elenco'].map(p=>c+'.'+p))]};",context);
  fixtures['/api/oratorio/allergie']={conteggi:{},segnalazioni:[]};
  fixtures['/api/famiglie/opportunita'].gruppi_iscritti={};
  for(const [category,load] of [['catechismo','loadCatechismo'],['oratorio','loadOratorio'],['doposcuola','loadDoposcuola']]) {
    fixtures['/api/'+category+'/gruppi']={gruppi:[],is_catechista_only:true};
    fixtures['/api/famiglie/opportunita'].gruppi[category]=[{id:3,nome:'Disponibile '+category,partecipanti:[people[1]]}];
    fixtures['/api/famiglie/opportunita'].gruppi_iscritti[category]=[{id:9}];
    fixtures['/api/famiglie/registri-gruppi/'+category]={gruppi:[{id:9,nome:'Gruppo del figlio',componenti:[]}]};
    vm.runInContext("currentView='"+category+"';",context);
    await context[load]();
    assert.equal(nodes(category+'ParentSection').style.display,'block');
    assert.equal(nodes(category+'StaffSection').style.display,'none');
    const content=nodes(category+'ParentContainer').innerHTML;
    assert.ok(content.indexOf(category+'AssignedContainer')<content.indexOf('Gruppi disponibili'));
    assert.ok(nodes(category+'AssignedContainer').innerHTML.includes('I tuoi gruppi e le presenze'));
    assert.ok(template.indexOf('id="'+category+'ParentSection"')<template.indexOf('id="'+category+'StaffSection"'));
    vm.runInContext("currentView='"+category+"_staff';",context);
    await context[load]();
    assert.equal(nodes(category+'StaffSection').style.display,'block');
    assert.equal(nodes(category+'ParentSection').style.display,'none');
    fixtures['/api/famiglie/opportunita'].gruppi[category]=[];
    fixtures['/api/famiglie/opportunita'].gruppi_iscritti[category]=[];
    await context[load]();
    assert.equal(nodes(category+'ParentSection').style.display,'none');
    assert.equal(nodes(category+'StaffSection').style.display,'block');
    assert.equal(vm.runInContext('currentView',context),category+'_staff');
    assert.ok(template.includes('data-view="'+category+'_staff"'));
    assert.equal(context.hasPermission(category+'_staff'),true);
  }
  fixtures['/api/calendari-gruppi/catechismo/9/sanita']={gruppo:'Gruppo di prova',conteggi:{iscritti:1,esigenze_alimentari:1,terapie:0},persone:[{nominativo:'Nome <prova>',allergie:'Arachidi',intolleranze_alimentari:'',terapie_medicinali:'',note_mediche:'',contatti:[]}]};
  await context.openGroupHealth('catechismo',9);
  assert.ok(nodes('groupHealthContent').innerHTML.includes('Arachidi'));
  assert.ok(nodes('groupHealthContent').innerHTML.includes('Nome &lt;prova&gt;'));
  assert.ok(!nodes('groupHealthContent').innerHTML.includes('Nome <prova>'));
  // I sei collegamenti aprono pannelli distinti e gli utenti senza incarico non entrano nello staff.
  const beforeNavigation=context.document.querySelectorAll;
  context.document.querySelectorAll=selector=>selector==='.view-panel'?['Oratorio','Catechismo','Doposcuola'].flatMap(c=>[nodes('view'+c),nodes('view'+c+'Staff')]):beforeNavigation(selector);
  await context.navigateTo('catechismo_staff');
  assert.equal(nodes('viewCatechismoStaff').style.display,'block');
  assert.equal(nodes('viewCatechismo').style.display,'none');
  fixtures['/api/famiglie/opportunita'].gruppi.catechismo=[{id:3,nome:'Gruppo disponibile',partecipanti:[people[1]]}];
  await context.navigateTo('catechismo');
  assert.equal(nodes('viewCatechismo').style.display,'block');
  assert.equal(nodes('viewCatechismoStaff').style.display,'none');
  vm.runInContext("currentUser.permessi=['dashboard'];",context);
  await context.navigateTo('catechismo_staff');
  assert.equal(context.hasPermission('catechismo_staff'),false);
  assert.equal(vm.runInContext('currentView',context),'dashboard');
  context.document.querySelectorAll=beforeNavigation;
  vm.runInContext("currentUser.permessi=['doposcuola','doposcuola.staff'];currentView='doposcuola_staff';",context);
  // La selezione multipla degli educatori arriva alla API come elenco di ID.
  fixtures['/api/doposcuola/educatori']={educatori:[{id:41,nominativo:'Educatore uno',email:'uno@example.test'},{id:42,nominativo:'Educatore due',email:'due@example.test'}]};
  await context.loadEducatoriDoposcuolaSelect('dopSelectEducatore',[{id:41,nominativo:'Educatore uno'}]);
  assert.equal((nodes('dopSelectEducatore').innerHTML.match(/type="checkbox"/g)||[]).length,2);
  assert.equal((nodes('dopSelectEducatore').innerHTML.match(/checked/g)||[]).length,1);
  const previousSelections=context.document.querySelectorAll;
  context.document.querySelectorAll=selector=>selector==='#dopSelectEducatore input:checked'?[{value:'41'},{value:'42'}]:previousSelections(selector);
  nodes('dopNomeGruppo').value='Gruppo condiviso';
  await context.handleSalvaGruppoDoposcuola({preventDefault(){}});
  const groupPost=requests.find(r=>r.url==='/api/doposcuola/gruppi' && r.options.method==='POST');
  assert.deepEqual(JSON.parse(groupPost.options.body).educatori_ids,[41,42]);
  context.document.querySelectorAll=previousSelections;
  vm.runInContext("currentUser.permessi=['calendari','calendari.comunita'];",context);
  assert.equal(context.hasPermission('calendari.comunita'),true);
  assert.equal(context.hasPermission('utenti.permessi'),false);
  vm.runInContext("currentUser.permessi=[];",context);
  const requestCount=requests.length;
  context.navigateTo('utenti');
  assert.equal(nodes('viewNoAccess').style.display,'block');
  assert.equal(requests.length,requestCount);
  assert.ok(template.includes('data-permission="excel.template"'));
  assert.ok(!template.includes('id="nuovoOratorioAnimatoriSelect"'));
  // L’anteprima non riusa le cache admin: ingresso e ritorno ricaricano il sito.
  let reloads=0;
  context.window.location={reload(){reloads++;}};
  context.renderImpersonationBanner({attiva:true,utente:'utente@example.test'});
  assert.equal(nodes('impersonationBanner').hidden,false);
  assert.equal(nodes('impersonationName').textContent,'utente@example.test');
  fixtures['/api/utenti/1/impersona']={success:true};
  fixtures['/api/auth/impersonazione/fine']={success:true};
  await context.impersonateUser(1);
  await context.stopImpersonation();
  assert.equal(reloads,2);
  assert.ok(requests.some(r=>r.url==='/api/utenti/1/impersona' && r.options.method==='POST'));
  assert.equal(nodes('stopImpersonationButton').disabled,false);
  context.renderImpersonationBanner(null);
  assert.equal(nodes('impersonationBanner').hidden,true);
  const originalQuery=context.document.querySelector;
  context.document.querySelector=selector=>selector==='#tableUtentiRuoli tbody'?nodes('utentiBody'):originalQuery(selector);
  vm.runInContext("currentUser={id:3,is_admin:true};",context);
  const accounts=[{id:1,email:'utente@example.test',nominativo:'Utente',ruolo:'utente',is_attivo:true},{id:2,email:'inattivo@example.test',nominativo:'Inattivo',ruolo:'utente',is_attivo:false},{id:3,email:'admin@example.test',nominativo:'Admin',ruolo:'admin',is_attivo:true}];
  context.renderTableUtenti(accounts);
  assert.equal((nodes('utentiBody').innerHTML.match(/onclick="impersonateUser/g)||[]).length,1);
  vm.runInContext("currentUser={id:1,is_admin:false};",context);
  context.renderTableUtenti(accounts);
  assert.ok(!nodes('utentiBody').innerHTML.includes('onclick="impersonateUser'));
  console.log('Alpha famiglia: attività fissata, selezione multipla, quota, invio unico, consensi e salute verificati.');
})().catch(error=>{console.error(error);process.exitCode=1;});
