const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const elements = new Map();
const selected = [];
const requests = [];
const nodes = id => {
  if (!elements.has(id)) elements.set(id, { value:'', style:{}, hidden:false, disabled:false, classList:{add(){},remove(){}}, textContent:'', _html:'',
    set innerHTML(value) { this._html=value; if (id==='iscrizioneAttivitaSelect') this.value='7'; },
    get innerHTML() { return this._html; },
  });
  return elements.get(id);
};
const people = [{codice_fiscale:'RSSMRA80A01H501U',nominativo:'Genitore di prova',eta:46}, {codice_fiscale:'RSSLGI14A01H501A',nominativo:'Figlio di prova',eta:12}];
const fixtures = {
  '/api/attivita':{attivita:[{id:7,titolo:'Attività selezionata',eta_min:0,eta_max:99,quota_iscrizione:10,campi_personalizzati:[{nome:'Taglia',chiave:'taglia',obbligatorio:true}]}]},
  '/api/famiglie/mia':{nucleo:{id:1,componenti:people},puo_gestire:true},
  '/api/iscrizioni?solo_mie=true':{iscrizioni:[]},
  '/api/configurazioni/clausole':{clausole:[{id:1,obbligatoria:true,titolo:'Clausola',testo:'Testo'}]},
  '/api/auth/registration-options':{consensi:{privacy:{titolo:'Privacy',testo:'Per la famiglia'},foto_video:{titolo:'Foto e video',testo:'Per la famiglia'}},salute:{allergie:['Polline'],intolleranze_alimentari:['Lattosio'],terapie_medicinali:['Terapia prescritta']}},
};
const context = vm.createContext({
  console, AbortController, setTimeout, clearTimeout,
  window:{addEventListener(){}},
  document:{addEventListener(){},getElementById:nodes,querySelectorAll(selector){
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
  await context.renderRegistrationConsents('registrationConsents');
  const html=nodes('registrationConsents').innerHTML;
  assert.equal((html.match(/type="checkbox"/g)||[]).length,2);
  assert.equal((html.match(/ required/g)||[]).length,2);
  assert.ok(!html.includes(' checked'));
  nodes('membroAllergie').value='Allergia preesistente';
  await context.renderHealthSections('membro');
  assert.equal(nodes('membroAllergie').value,'Allergia preesistente');
  assert.ok(nodes('membroTerapiePills').innerHTML.includes('Terapia prescritta'));
  console.log('Alpha famiglia: attività fissata, selezione multipla, quota, invio unico, consensi e salute verificati.');
})().catch(error=>{console.error(error);process.exitCode=1;});
