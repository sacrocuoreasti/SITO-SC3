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
