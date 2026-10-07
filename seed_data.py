import os
import json
from datetime import date, datetime
from app import create_app
from models import db, Utente, Persona, NucleoFamiliare, Attivita, Iscrizione, NotiziaEvento
from services.excel_service import importa_da_excel
from io import BytesIO

app = create_app()

def seed():
    with app.app_context():
        db.create_all()
        print("--- Inizializzazione Database Parrocchia Sacro Cuore Asti ---")

        # 1. Attività Parrocchiali
        attivita_list = [
            {
                'titolo': 'Estate Ragazzi 2026',
                'categoria': 'oratorio',
                'descrizione': 'GREST ed Estate Ragazzi della Parrocchia del Sacro Cuore. Giochi di squadra, tornei, laboratori creativi, gite e preghiera insieme.',
                'anno_pastorale': '2025/2026',
                'eta_min': 6,
                'eta_max': 14,
                'quota_iscrizione': 60.0,
                'posti_massimi': 150,
                'data_inizio': date(2026, 6, 15),
                'data_fine': date(2026, 7, 10),
                'is_attiva': True
            },
            {
                'titolo': 'Catechismo - 1ª Comunione',
                'categoria': 'catechismo',
                'descrizione': 'Cammino di preparazione al Sacramento dell\'Eucaristia per i fanciulli della 3ª e 4ª elementare.',
                'anno_pastorale': '2025/2026',
                'eta_min': 8,
                'eta_max': 10,
                'quota_iscrizione': 20.0,
                'posti_massimi': 45,
                'data_inizio': date(2025, 10, 1),
                'data_fine': date(2026, 5, 20),
                'is_attiva': True
            },
            {
                'titolo': 'Catechismo - Santa Cresima',
                'categoria': 'catechismo',
                'descrizione': 'Percorso di confermazione nella fede e testimonianza cristiana per i ragazzi di 2ª e 3ª media.',
                'anno_pastorale': '2025/2026',
                'eta_min': 12,
                'eta_max': 14,
                'quota_iscrizione': 20.0,
                'posti_massimi': 35,
                'data_inizio': date(2025, 10, 1),
                'data_fine': date(2026, 5, 20),
                'is_attiva': True
            },
            {
                'titolo': 'Campo Estivo Montagna - Bardonecchia',
                'categoria': 'campo_estivo',
                'descrizione': 'Settimana comunitaria in montagna tra natura, escursioni e momenti di riflessione per ragazzi dai 10 ai 16 anni.',
                'anno_pastorale': '2025/2026',
                'eta_min': 10,
                'eta_max': 16,
                'quota_iscrizione': 220.0,
                'posti_massimi': 40,
                'data_inizio': date(2026, 7, 19),
                'data_fine': date(2026, 7, 26),
                'is_attiva': True
            },
            {
                'titolo': 'Doposcuola & Oratorio Invernale',
                'categoria': 'doposcuola',
                'descrizione': 'Supporto compiti pomeridiano e giochi in cortile ogni martedì e giovedì dalle 16:30 alle 18:30.',
                'anno_pastorale': '2025/2026',
                'eta_min': 6,
                'eta_max': 13,
                'quota_iscrizione': 0.0,
                'posti_massimi': 60,
                'data_inizio': date(2025, 10, 15),
                'data_fine': date(2026, 5, 30),
                'is_attiva': True
            },
            {
                'titolo': 'Festa Patronale Sacro Cuore 2026',
                'categoria': 'evento',
                'descrizione': 'Festa della comunità parrocchiale con cena insieme, banco di beneficenza e spettacolo dei ragazzi.',
                'anno_pastorale': '2025/2026',
                'eta_min': 0,
                'eta_max': 99,
                'quota_iscrizione': 0.0,
                'posti_massimi': 300,
                'data_inizio': date(2026, 6, 12),
                'data_fine': date(2026, 6, 14),
                'is_attiva': True
            }
        ]

        for att_data in attivita_list:
            if not Attivita.query.filter_by(titolo=att_data['titolo']).first():
                att = Attivita(**att_data)
                db.session.add(att)
        db.session.commit()

        # 2. Don Rodrigo (Parroco)
        cf_don = "LMRRDR75A01Z602X"
        don = db.session.get(Persona, cf_don)
        if not don:
            don = Persona(
                codice_fiscale=cf_don,
                nome="Rodrigo Adriano",
                cognome="Dos Santos Limeira",
                sesso="M",
                data_nascita=date(1975, 1, 1),
                luogo_nascita="Brasile",
                indirizzo_residenza="Via Pier Santi Mattarella 2",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="0141 355150",
                email="donrodrigo@sacrocuoreasti.it",
                ruolo_famiglia="Parroco"
            )
            db.session.add(don)
            db.session.flush()

        utente_parroco = Utente.query.filter_by(email="donrodrigo@sacrocuoreasti.it").first()
        if not utente_parroco:
            utente_parroco = Utente(
                email="donrodrigo@sacrocuoreasti.it",
                codice_fiscale=cf_don,
                ruolo="parroco",
                privilegi_extra=json.dumps(['parroco', 'segreteria', 'admin']),
                is_attivo=True
            )
            utente_parroco.set_password("parroco2026")
            db.session.add(utente_parroco)

        # 3. Segreteria (Laura Massano)
        cf_seg = "MSSNLR82M45A479K"
        p_seg = db.session.get(Persona, cf_seg)
        if not p_seg:
            p_seg = Persona(
                codice_fiscale=cf_seg,
                nome="Laura",
                cognome="Massano",
                sesso="F",
                data_nascita=date(1982, 8, 15),
                luogo_nascita="Asti",
                indirizzo_residenza="Corso Dante 112",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="0141 355150",
                email="segreteria@sacrocuoreasti.it",
                ruolo_famiglia="Capofamiglia"
            )
            db.session.add(p_seg)
            db.session.flush()

        utente_seg = Utente.query.filter_by(email="segreteria@sacrocuoreasti.it").first()
        if not utente_seg:
            utente_seg = Utente(
                email="segreteria@sacrocuoreasti.it",
                codice_fiscale=cf_seg,
                ruolo="segreteria",
                privilegi_extra=json.dumps(['segreteria', 'oratorio', 'catechista']),
                is_attivo=True
            )
            utente_seg.set_password("segreteria2026")
            db.session.add(utente_seg)

        # 4. Admin Sistema (Marco Rossi)
        cf_admin = "RSSMRC88T10A479V"
        p_admin = db.session.get(Persona, cf_admin)
        if not p_admin:
            p_admin = Persona(
                codice_fiscale=cf_admin,
                nome="Marco",
                cognome="Rossi",
                sesso="M",
                data_nascita=date(1988, 12, 10),
                luogo_nascita="Asti",
                indirizzo_residenza="Piazza Alfieri 14",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3381122334",
                email="admin@sacrocuoreasti.it",
                ruolo_famiglia="Capofamiglia"
            )
            db.session.add(p_admin)
            db.session.flush()

        utente_admin = Utente.query.filter_by(email="admin@sacrocuoreasti.it").first()
        if not utente_admin:
            utente_admin = Utente(
                email="admin@sacrocuoreasti.it",
                codice_fiscale=cf_admin,
                ruolo="admin",
                privilegi_extra=json.dumps(['admin', 'segreteria', 'parroco']),
                is_attivo=True
            )
            utente_admin.set_password("admin2026")
            db.session.add(utente_admin)

        # 5. Catechista (Chiara Gatti)
        cf_cat = "GTTCHR91P50A479F"
        p_cat = db.session.get(Persona, cf_cat)
        if not p_cat:
            p_cat = Persona(
                codice_fiscale=cf_cat,
                nome="Chiara",
                cognome="Gatti",
                sesso="F",
                data_nascita=date(1991, 9, 20),
                luogo_nascita="Asti",
                indirizzo_residenza="Via Cavour 35",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3475566778",
                email="catechista@sacrocuoreasti.it",
                ruolo_famiglia="Capofamiglia"
            )
            db.session.add(p_cat)
            db.session.flush()

        utente_cat = Utente.query.filter_by(email="catechista@sacrocuoreasti.it").first()
        if not utente_cat:
            utente_cat = Utente(
                email="catechista@sacrocuoreasti.it",
                codice_fiscale=cf_cat,
                ruolo="catechista",
                privilegi_extra=json.dumps(['catechista']),
                is_attivo=True
            )
            utente_cat.set_password("catechista2026")
            db.session.add(utente_cat)

        # 6. Oratorio / Animatore (Matteo B.)
        cf_ora = "BRNMTT98B14A479Q"
        p_ora = db.session.get(Persona, cf_ora)
        if not p_ora:
            p_ora = Persona(
                codice_fiscale=cf_ora,
                nome="Matteo",
                cognome="Barbero",
                sesso="M",
                data_nascita=date(1998, 2, 14),
                luogo_nascita="Asti",
                indirizzo_residenza="Corso Alessandria 80",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3397788990",
                email="oratorio@sacrocuoreasti.it",
                ruolo_famiglia="Capofamiglia"
            )
            db.session.add(p_ora)
            db.session.flush()

        utente_ora = Utente.query.filter_by(email="oratorio@sacrocuoreasti.it").first()
        if not utente_ora:
            utente_ora = Utente(
                email="oratorio@sacrocuoreasti.it",
                codice_fiscale=cf_ora,
                ruolo="oratorio",
                privilegi_extra=json.dumps(['oratorio']),
                is_attivo=True
            )
            utente_ora.set_password("oratorio2026")
            db.session.add(utente_ora)

        # 7. Famiglia Demo Ferraris (Genitore: Paolo Ferraris, Figli: Lorenzo e Sofia)
        cf_padre = "FRRPLA78E15A479L"
        cf_lorenzo = "FRRLNZ14H12A479K"
        cf_sofia = "FRRSFO17M45A479T"

        p_padre = db.session.get(Persona, cf_padre)
        if not p_padre:
            p_padre = Persona(
                codice_fiscale=cf_padre,
                nome="Paolo",
                cognome="Ferraris",
                sesso="M",
                data_nascita=date(1978, 5, 15),
                luogo_nascita="Asti",
                indirizzo_residenza="Via Brofferio 42",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3389876543",
                email="genitore@sacrocuoreasti.it",
                ruolo_famiglia="Capofamiglia"
            )
            db.session.add(p_padre)
            db.session.flush()

        # Nucleo Famiglia Ferraris
        nucleo_ferraris = NucleoFamiliare.query.filter_by(codice_fiscale_capofamiglia=cf_padre).first()
        if not nucleo_ferraris:
            nucleo_ferraris = NucleoFamiliare(
                nome_famiglia="Famiglia Ferraris",
                codice_fiscale_capofamiglia=cf_padre,
                telefono_principale="3389876543",
                indirizzo="Via Brofferio 42",
                citta="Asti"
            )
            db.session.add(nucleo_ferraris)
            db.session.flush()

        p_padre.nucleo_id = nucleo_ferraris.id

        utente_gen = Utente.query.filter_by(email="genitore@sacrocuoreasti.it").first()
        if not utente_gen:
            utente_gen = Utente(
                email="genitore@sacrocuoreasti.it",
                codice_fiscale=cf_padre,
                ruolo="genitore",
                privilegi_extra=json.dumps(['genitore']),
                is_attivo=True
            )
            utente_gen.set_password("genitore2026")
            db.session.add(utente_gen)

        # Figlio Lorenzo (ha allergia e intolleranza per testare il cruscotto oratorio)
        p_lorenzo = db.session.get(Persona, cf_lorenzo)
        if not p_lorenzo:
            p_lorenzo = Persona(
                codice_fiscale=cf_lorenzo,
                nome="Lorenzo",
                cognome="Ferraris",
                sesso="M",
                data_nascita=date(2014, 6, 12),
                luogo_nascita="Asti",
                indirizzo_residenza="Via Brofferio 42",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3389876543",
                nucleo_id=nucleo_ferraris.id,
                ruolo_famiglia="Figlio/a",
                intolleranze_alimentari="Celiachia (senza glutine)",
                allergie="Allergia grave alle arachidi e crostacei. Porta siringa autoiniettante e antistaminico."
            )
            db.session.add(p_lorenzo)

        # Figlia Sofia
        p_sofia = db.session.get(Persona, cf_sofia)
        if not p_sofia:
            p_sofia = Persona(
                codice_fiscale=cf_sofia,
                nome="Sofia",
                cognome="Ferraris",
                sesso="F",
                data_nascita=date(2017, 8, 5),
                luogo_nascita="Asti",
                indirizzo_residenza="Via Brofferio 42",
                comune_residenza="Asti",
                cap_residenza="14100",
                telefono="3389876543",
                nucleo_id=nucleo_ferraris.id,
                ruolo_famiglia="Figlio/a",
                intolleranze_alimentari="Intolleranza lieve al lattosio",
                allergie="Nessuna"
            )
            db.session.add(p_sofia)

        db.session.commit()

        # Iscrizioni demo
        att_oratorio = Attivita.query.filter_by(titolo='Estate Ragazzi 2026').first()
        if att_oratorio and not Iscrizione.query.filter_by(attivita_id=att_oratorio.id, codice_fiscale_partecipante=cf_lorenzo).first():
            isc1 = Iscrizione(
                attivita_id=att_oratorio.id,
                codice_fiscale_partecipante=cf_lorenzo,
                iscritto_da_id=utente_gen.id,
                stato='confermata',
                stato_pagamento='saldato',
                importo_dovuto=60.0,
                importo_pagato=60.0,
                squadra='Rossi',
                note_iscrizione='Taglia maglietta: M (10-12 anni). Delegata la zia Elena al ritiro serale.',
                consenso_privacy=True,
                consenso_foto=True,
                consenso_uscite=True
            )
            db.session.add(isc1)

        att_catechismo = Attivita.query.filter_by(titolo='Catechismo - 1ª Comunione').first()
        if att_catechismo and not Iscrizione.query.filter_by(attivita_id=att_catechismo.id, codice_fiscale_partecipante=cf_sofia).first():
            isc2 = Iscrizione(
                attivita_id=att_catechismo.id,
                codice_fiscale_partecipante=cf_sofia,
                iscritto_da_id=utente_gen.id,
                stato='confermata',
                stato_pagamento='saldato',
                importo_dovuto=20.0,
                importo_pagato=20.0,
                note_iscrizione='Frequenta 3ª elementare alla scuola Dante Alighieri',
                consenso_privacy=True,
                consenso_foto=True,
                consenso_uscite=True
            )
            db.session.add(isc2)

        # 8. Notizie ed Eventi Parrocchiali
        avvisi = [
            {
                'titolo': 'Apertura Iscrizioni Estate Ragazzi 2026',
                'categoria': 'oratorio',
                'contenuto': 'Sono aperte le iscrizioni all\'Estate Ragazzi 2026 della Parrocchia del Sacro Cuore! Quattro settimane di giochi, laboratori e gite dal 15 giugno al 10 luglio. È possibile iscrivere i propri figli comodamente da questo portale.',
                'data_evento': date(2026, 6, 15),
                'in_evidenza': True
            },
            {
                'titolo': 'Incontro Genitori del Catechismo con Don Rodrigo',
                'categoria': 'avviso',
                'contenuto': 'Domenica prossima dopo la Santa Messa delle ore 10:00 ci sarà un momento di incontro e confronto con Don Rodrigo e i catechisti nel salone parrocchiale.',
                'data_evento': date(2026, 10, 18),
                'in_evidenza': True
            }
        ]
        for a in avvisi:
            if not NotiziaEvento.query.filter_by(titolo=a['titolo']).first():
                db.session.add(NotiziaEvento(**a))

        db.session.commit()

        # 9. Carica anche i dati dal template Excel se presente!
        excel_path = os.path.join(app.root_path, 'template_anagrafica_sacro_cuore.xlsx')
        if os.path.exists(excel_path):
            print(f"Caricamento dati dal file Excel: {excel_path}...")
            with open(excel_path, 'rb') as f:
                res = importa_da_excel(BytesIO(f.read()))
                print(f"Risultato Excel: {res['persone_create']} persone create, {res['persone_aggiornate']} aggiornate, {res['nuclei_creati']} famiglie create.")

        print("--- Inizializzazione completata con successo! ---")
        print("Account demo disponibili:")
        print("  - Parroco:    donrodrigo@sacrocuoreasti.it / parroco2026")
        print("  - Segreteria: segreteria@sacrocuoreasti.it / segreteria2026")
        print("  - Admin:      admin@sacrocuoreasti.it / admin2026")
        print("  - Catechista: catechista@sacrocuoreasti.it / catechista2026")
        print("  - Oratorio:   oratorio@sacrocuoreasti.it / oratorio2026")
        print("  - Genitore:   genitore@sacrocuoreasti.it / genitore2026")

if __name__ == '__main__':
    seed()
