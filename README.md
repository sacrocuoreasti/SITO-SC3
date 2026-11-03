# Portale Sacro Cuore Asti

Applicazione Flask con SQLite, servita in produzione da Gunicorn.

## Avvio e verifica

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node --check static/js/app.js
gunicorn --config gunicorn.conf.py 'app:create_app()'
```

Usare Python 3.11 in produzione. Il server ascolta su `$PORT` (default 5001).
Procfile e Docker condividono lo stesso profilo: un worker, quattro thread,
timeout 120 secondi e log su stdout/stderr. Non aumentare i worker senza
separare prima l'inizializzazione del database dall'avvio dei processi.
`/health` verifica la connessione al database: 200 se disponibile, 503 se guasta.
Impostare questo percorso come Health Check Path in Render.

## Configurazione Render e persistenza

Per un servizio Python esistente:

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --config gunicorn.conf.py 'app:create_app()'`
- Health Check Path: `/health`
- `SECRET_KEY`: valore casuale stabile nelle variabili ambiente, mai nel repository.
- `SMTP_USER`, `SMTP_PASS`, `SMTP_SERVER`, `SMTP_PORT`: configurazione email.

Le variabili ambiente si impostano su Render; `.env.example` è un riferimento,
non viene caricato automaticamente. In assenza di `SECRET_KEY`, viene creata una
chiave privata `database/.session-key`: è adatta allo sviluppo, ma su filesystem
non persistente viene persa al deploy e gli utenti devono riaccedere.
Il cambio dalla vecchia chiave del codice invalida le sessioni precedenti.

**Render usa un filesystem effimero:** i dati SQLite e gli upload vengono persi
ai riavvii/deploy senza disco persistente. Un push non configura un disco.
Prima di cambiare percorsi, fare un backup del database live con SQLite Backup
API e una copia degli upload, sospendendo temporaneamente le scritture durante
la migrazione. Non copiare soltanto il `.db` mentre è in uso in modalità WAL.

Con un disco già attivato e montato su `/var/data`, copiare il backup verificato
in `/var/data/database/sacro_cuore.db` e i file in `/var/data/uploads`, poi impostare:

```text
DATA_DIR=/var/data
DATABASE_URL=sqlite:////var/data/database/sacro_cuore.db
UPLOAD_FOLDER=/var/data/uploads
```

Verificare utenti, contenuti e allegati dopo un riavvio. Il codice non migra o
sovrascrive automaticamente dati live. `DATABASE_URL` e `UPLOAD_FOLDER`
possono anche mantenere percorsi di un disco già esistente.
La configurazione delle connessioni distingue SQLite dagli altri dialect, ma
l'eventuale passaggio a PostgreSQL richiede driver, migrazione e verifiche dedicate.

Riferimenti: [dischi Render](https://render.com/docs/disks),
[Flask su Render](https://render.com/docs/deploy-flask).

## Account e file privati

L'avvio non crea account con password note, non ripristina password/ruoli e non
riapre gruppi chiusi. La registrazione pubblica crea solo utenti ordinari.
Per una nuova installazione vuota, creare il primo amministratore dalla shell:

```sh
flask --app 'app:create_app()' create-admin
```

Le password vengono richieste interattivamente e non passate come argomenti.
Gli account esistenti restano invariati: cambiare le vecchie password predefinite
e revocare la password SMTP precedentemente presente nella cronologia Git;
configurare una nuova `SMTP_PASS` su Render. Senza SMTP il recupero password
segnala indisponibilità invece di dichiarare falsamente l'invio del codice.

Database e file caricati già tracciati in precedenza sono conservati in questa
modifica per evitare un reset involontario delle installazioni esistenti.
`.gitignore` esclude nuovi file runtime; non rimuove quelli già tracciati né la
cronologia. Dopo la migrazione verificata, rimuovere i dati runtime dal repository
e gestire separatamente la bonifica della cronologia pubblica e dei segreti esposti.
Non aggiungere certificati, anagrafiche o credenziali a GitHub.

## Verifiche automatiche

GitHub Actions esegue test isolati su database temporanei e controlla la sintassi
JavaScript a ogni push/PR. I test coprono API pubbliche, autenticazione, permessi
amministrativi, risposte JSON di errore, recupero dopo errori database, richieste
concorrenti e conservazione delle impostazioni al riavvio. Non usano il database
reale e non inviano email.

## Email con Google Apps Script (Render Free)

Il codice da incollare è in `integrations/google-apps-script/Code.gs`.
Procedura completa in `integrations/google-apps-script/INSTALLAZIONE.txt`.
Il piano Render Free blocca le porte SMTP: l’integrazione usa HTTPS, senza
password Gmail. Le chiamate sono firmate con HMAC SHA-256 e scadono dopo
cinque minuti. Lo script registra per dieci minuti solo gli identificativi delle
richieste, per impedire invii ripetuti; non conserva destinatari, corpi email o OTP.

Variabili Render:

```text
EMAIL_PROVIDER=google_apps_script
GOOGLE_SCRIPT_URL=https://script.google.com/macros/s/ID_DEPLOYMENT/exec
GOOGLE_SCRIPT_SECRET=<valore MAILER_SECRET dalle proprietà dello script>
```

Il mittente è l'account Google proprietario che esegue la web app. L'API non
consente di scegliere arbitrariamente un altro indirizzo mittente. Le quote di
Google continuano ad applicarsi. Una risposta positiva conferma la presa in
carico, non la consegna nella casella del destinatario.
L'endpoint `/api/utenti/email-status` è riservato allo staff e mostra solo lo
stato della configurazione, senza segreti né invii di prova.
Per hosting con SMTP disponibile resta supportato `EMAIL_PROVIDER=smtp`,
con STARTTLS sulla porta 587 e TLS sulla porta 465.

Riferimenti: [limiti Render Free](https://render.com/docs/free#other-limitations),
[web app Apps Script](https://developers.google.com/apps-script/guides/web),
[MailApp](https://developers.google.com/apps-script/reference/mail/mail-app).

## Alpha 2.0.0: aggiornamenti e dati esistenti

La versione è definita in `VERSION` e mostrata nella homepage, nel login e in
`/health`. Ogni successiva modifica deve incrementarla, in accordo con AGENTS.md.
Il capofamiglia è il responsabile del nucleo, indipendentemente dal ruolo di
padre, madre, figlio o altro. I campi sanitari preesistenti restano invariati:
terapie e medicinali usano una nuova colonna, senza riclassificare vecchie note.
I suggerimenti sono opzioni dell'interfaccia, non nuovi record nel database.

Le migrazioni aggiungono colonne e una tabella per le richieste di ingresso;
assegnano un codice univoco di tre caratteri ai nuclei esistenti. Non cambiano
password, utenti, eventi, clausole, categorie, dati sanitari o gruppi esistenti.
L'avvio non esegue seed su database già esistenti, anche se alcune tabelle sono
vuote. I nuovi consensi sono registrati solo quando dichiarati: non vengono
attribuiti retroattivamente agli utenti esistenti.

### Backup prima del deploy

Per SQLite viene eseguito un backup coerente prima delle modifiche allo schema.
Questo protegge la migrazione sullo stesso filesystem; non recupera i file che
Render Free ha già perso sostituendo un'istanza durante il deploy.

- `python scripts/backup_local.py`: copia completa del database LOCALE e degli
  upload locali, con manifest, checksum e verifica SQLite. Non è una copia del
  servizio online.
- Quando alpha 2.0.0 è già installata, un amministratore può scaricare il backup
  completo da `/api/backup/export`, oppure usare `python scripts/backup_remote.py`.
  Le credenziali vengono richieste interattivamente e non salvate.
- Ripristino a server fermo:
  `python scripts/restore_backup.py ARCHIVIO.zip --data-dir CARTELLA_DATI --server-stopped`.
  Il ripristino crea prima una copia dei dati eventualmente presenti, verifica
  il manifest e conserva gli allegati non in conflitto. Impostare `DATA_DIR`
  sulla cartella ripristinata prima dell'avvio del sito.

Database, password hash, dati sanitari e allegati sono privati: i backup sono
esclusi da Git e dalle immagini Docker. Non caricarli su GitHub pubblico.
L'utente ha autorizzato il primo deploy di alpha 2.0.0 accettando l'eventuale
ripristino dei dati oggi online dalla copia iniziale. Questa eccezione non vale
per gli aggiornamenti successivi.

### Pubblicazioni successive con conservazione dei dati

Da `main`, dopo aver committato le modifiche al codice, eseguire:

```sh
python scripts/release.py
```

Il comando richiede l'accesso amministratore senza salvarne la password:

1. Esegue i controlli; poi sospende temporaneamente le operazioni sul sito e
   attende la conclusione delle richieste già in corso.
2. Scarica un archivio completo dal sito, verifica SQLite e checksum, conserva
   copie private in `backups/` e prepara uno snapshot cifrato AES-GCM.
3. Incrementa la versione, committa su GitHub soltanto codice, manifest tecnico
   e `.deployment/restore.enc` cifrato, quindi avvia il deploy tramite push.
4. Il server ripristina database e allegati prima di avviarsi e resta in
   manutenzione. Il client confronta tutti i valori delle colonne preesistenti,
   comprese password, consensi e pagamenti, e i checksum degli allegati.
5. Solo dopo il confronto positivo il sito viene riaperto. Il campo volatile
   `last_login` è escluso perché la verifica richiede un nuovo accesso.

Build e avvio fermano le nuove versioni prive di snapshot corrispondente.
La chiave non è nel repository: viene derivata da `BACKUP_ENCRYPTION_KEY`,
oppure dalla `GOOGLE_SCRIPT_SECRET` già configurata su Render. Non modificare
questo segreto senza preparare una nuova copia cifrata prima del cambio.

Se la preparazione viene annullata prima del push, le operazioni riprendono.
Per annullare esplicitamente sul vecchio server: `python scripts/release.py --cancel`.
Se il deploy è già partito, la manutenzione resta attiva finché i dati non sono
stati verificati; non aggirare il controllo.

Questo flusso conserva i dati attraverso gli aggiornamenti controllati. Render
Free resta privo di disco persistente: un riavvio o sospensione non pianificati
possono riportare lo stato all'ultimo snapshot di rilascio. Per proteggere anche
le scritture successive contro questi eventi serve uno storage persistente.

## Ruoli, privilegi e viste

In **Utenti e privilegi → Ruoli, privilegi e viste**, l’amministratore configura
separatamente ogni menu laterale e le sue funzioni. I ruoli base sono Admin,
Segreteria e Utente; Animatore, Responsabile oratorio e Catechista sono privilegi
aggiuntivi. È possibile creare altri ruoli e privilegi. Il profilo Educatore
conserva la compatibilità con gli incarichi del doposcuola già assegnati.

I permessi del ruolo e degli incarichi si sommano: per disabilitare una funzione
occorre rimuoverla da tutti i profili che la concedono. Admin mantiene sempre
accesso completo e soltanto un amministratore può modificare account e permessi.
Le verifiche sono applicate anche alle API private, mantenendo i vincoli sui
nuclei familiari e sui gruppi assegnati. Le definizioni iniziali sono nel codice;
le personalizzazioni sono conservate nel database e incluse nei backup di rilascio.
Gli account precedenti non vengono riscritti durante l’aggiornamento.

Nell’elenco account, **Impersonifica** apre l’anteprima di un altro utente attivo.
La sessione adotta i suoi permessi effettivi e blocca le scritture lato server.
La barra di anteprima permette di tornare all’amministratore; uscire elimina
anche il contesto di ritorno. Nessuna password, ruolo o data di accesso del
destinatario viene modificata dall’anteprima.

Le sezioni Oratorio, Catechismo e Doposcuola mantengono distinta la parte
**La mia famiglia** dall’area **Il mio incarico**, quando sono entrambe presenti.
I gruppi del nucleo con le presenze precedono quelli disponibili per l’iscrizione.
Ogni scheda staff offre il quadro sanitario e cucina del singolo gruppo,
subordinato ai permessi sanitari/cucina e all’assegnazione al gruppo.
I profili personalizzati si rinominano senza cambiare codice e assegnazioni;
si possono eliminare dopo aver rimosso le assegnazioni, anche agli account
inattivi. I profili di sistema restano disponibili.

I menu pastorali hanno sei voci distinte: **Oratorio / Oratorio staff**,
**Catechismo / Catechismo staff**, **Doposcuola / Doposcuola staff**.
Le voci familiari seguono le opportunità e le iscrizioni del nucleo; quelle staff
richiedono il permesso operativo della categoria e mantengono i vincoli di gruppo.
L’appello dell’oratorio usa la stessa matrice del catechismo, con frequenza e
conteggio immediato dei presenti e assenti.

Le nuove iscrizioni al catechismo sono limitate a un gruppo per persona e anno
pastorale, anche tramite API, assegnazioni di massa e richieste simultanee.
I gruppi genitori sono distinti e le eventuali iscrizioni precedenti non vengono
cancellate automaticamente. Per il doposcuola, la tabella di associazione degli
educatori permette più incaricati, conservando anche gli assegnatari precedenti.

Il calendario settimanale della panoramica include Messe, Liturgia e Avvenimenti.
I nuovi avvenimenti usano una data specifica, mentre le ricorrenze e gli
avvenimenti precedenti conservano i giorni già registrati. Da Messe e liturgia
si possono creare avvisi pubblicati o in bozza: quelli pubblicati confluiscono
in Avvisi & Orari Messe, con gestione compatibile delle date italiane precedenti.

Il catalogo dei calendari comunitari include automaticamente i calendari dei
gruppi dell’anno pastorale corrente (1 settembre–31 agosto, Europe/Rome).
I calendari manuali sono conservati; i collegamenti identici vengono accorpati
nella vista, senza creare nuove righe. I calendari in bozza restano riservati
allo staff autorizzato. Le viste mensili pubbliche mostrano soltanto gli
appuntamenti e caricano Google su richiesta, senza esporre presenze o anagrafiche.

I calendari vengono raggruppati per tipologia nelle viste pubbliche, personali
e di segreteria; i collegamenti condivisi fra attività diverse hanno un gruppo
dedicato. La nuova sezione **Gruppi giovani** mantiene viste famiglia/staff
separate e riutilizza iscrizioni, calendario, elenco, quadro sanitario e appelli.
Sono consentiti al massimo due gruppi giovani per anno pastorale, con controllo
anche sulle richieste concorrenti. Non vengono creati gruppi o iscritti dimostrativi.

Ogni gruppo pastorale ha una bacheca privata, con argomento, titolo, testo e
bozze. La lettura è consentita agli iscritti/nuclei autorizzati e allo staff
assegnato; la gestione richiede anche il permesso **Pubblica e gestisci avvisi**.
La panoramica riunisce gli avvisi pubblicati dei gruppi accessibili, per attività
e argomento, senza duplicare i gruppi presenti sia nell’ambito familiare sia
nell’incarico staff. Le anteprime sono limitate e il testo completo è conservato.
Il privilegio Responsabile gruppi giovani e i nuovi permessi delle bacheche sono
configurabili in Utenti e privilegi. Gli avvisi di gruppo non sono avvisi pubblici
della comunità e non compaiono negli endpoint pubblici.
