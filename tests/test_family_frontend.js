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
  if (!elements.has(id)) elements.set(id, { value:'', style:{}, hidden:false, disabled:false, classList:{add(){},remove(){},contains(){return false;}}, textContent:'', _html:'',
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
    return {ok:true,headers:{get:()=> 'application/json'},json:async()=>url==='/api/iscrizioni'?{success:true,message:'Registrato'}:fixtures[url]};
  },
});
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
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes('Iscrivi altri familiari'));
  assert.ok(!nodes('activitiesCatalogGrid').innerHTML.includes('Iscriviti</button>'));
  option.partecipanti=[];
  await context.loadAttivita();
  assert.ok(nodes('activitiesCatalogGrid').innerHTML.includes('Iscrizione effettuata'));
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
    fixtures['/api/'+category+'/miei-figli']={ha_famiglia:true,figli:[]};
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
  const calendar=context.groupCalendarMarkup({calendar_embed_url:url});
  assert.ok(calendar.includes('Mostra appuntamenti'));
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
  console.log('Alpha famiglia: attività fissata, selezione multipla, quota, invio unico, consensi e salute verificati.');
})().catch(error=>{console.error(error);process.exitCode=1;});
