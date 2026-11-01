# Regole del progetto

- Ogni aggiornamento del sito deve incrementare la versione in VERSION e package.json. La versione corrente di partenza è alpha 2.0.0; per correzioni successive incrementare il patch, salvo istruzioni diverse dell'utente.
- Mantenere utenti, famiglie, password, eventi, iscrizioni, allegati e configurazioni esistenti. Usare migrazioni additive con backup prima delle modifiche allo schema. Non eseguire seed o reinizializzazioni sui database esistenti.
- Non aggiungere dati dimostrativi, non reimpostare account e non cancellare dati come parte di un aggiornamento.
- Prima di push sul branch collegato alla pubblicazione o di un deploy verificare la persistenza e un backup aggiornato del database e degli allegati online. Render Free con SQLite sul filesystem effimero non garantisce la conservazione al deploy: non avviare un deploy in questa situazione senza una procedura di conservazione verificata.
- Eseguire i test su database temporanei; mai sul database reale. Non committare database, backup, allegati o segreti.
