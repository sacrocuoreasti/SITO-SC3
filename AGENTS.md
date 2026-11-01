# Regole del progetto

- Ogni aggiornamento del sito deve incrementare la versione in VERSION e package.json. La versione corrente di partenza è alpha 2.0.0; per correzioni successive incrementare il patch, salvo istruzioni diverse dell'utente.
- Mantenere utenti, famiglie, password, eventi, iscrizioni, allegati e configurazioni esistenti. Usare migrazioni additive con backup prima delle modifiche allo schema. Non eseguire seed o reinizializzazioni sui database esistenti.
- Non aggiungere dati dimostrativi, non reimpostare account e non cancellare dati come parte di un aggiornamento.
- L'utente ha autorizzato esplicitamente il primo deploy di alpha 2.0.0 anche se i dati online di oggi vengono ripristinati dalla copia locale. È un'eccezione limitata a questo avvio iniziale.
- Per OGNI rilascio successivo usare `python scripts/release.py` da main, con le modifiche al codice già committate. Il comando esegue controlli, mette in manutenzione il server, scarica e verifica un backup online completo in `backups/`, prepara la copia cifrata `.deployment/restore.enc`, incrementa VERSION/package.json, pubblica e confronta tutti i record e allegati dopo il ripristino. Solo il confronto positivo riapre il sito.
- Non fare push diretti su main dopo il bootstrap: build e avvio rifiutano versioni senza il proprio snapshot. Non riutilizzare un backup vecchio. Se il rilascio non conclude il confronto, mantenere la manutenzione e verificare il problema; annullare la preparazione sul vecchio server con `python scripts/release.py --cancel` soltanto se il nuovo deploy non viene pubblicato.
- È consentito committare soltanto lo snapshot cifrato e il suo manifest tecnico. Non estrarre né mostrare la chiave: il server usa BACKUP_ENCRYPTION_KEY oppure la GOOGLE_SCRIPT_SECRET già configurata. Non cambiarla senza ricifrare i backup.
- Eseguire i test su database temporanei; mai sul database reale. Non committare database, backup, allegati o segreti.
