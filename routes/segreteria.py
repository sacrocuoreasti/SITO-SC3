from flask import Blueprint, jsonify
from models import db, Persona, NucleoFamiliare, Attivita, Iscrizione, Utente
from sqlalchemy import func

segreteria_bp = Blueprint('segreteria_bp', __name__, url_prefix='/api/segreteria')

@segreteria_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Statistiche complete per il Parroco e la Segreteria:
    - Numero totale anagrafica parrocchiale
    - Nuclei familiari censiti
    - Utenti registrati a portale
    - Iscrizioni complessive confermate e in attesa
    - Contabilità quote: totale dovuto, totale incassato, saldo residuo
    - Ripartizione per categoria di attività
    """
    tot_persone = Persona.query.count()
    tot_famiglie = NucleoFamiliare.query.count()
    tot_utenti = Utente.query.count()
    tot_iscrizioni = Iscrizione.query.count()
    iscrizioni_confermate = Iscrizione.query.filter_by(stato='confermata').count()
    iscrizioni_in_attesa = Iscrizione.query.filter_by(stato='in_attesa').count()

    # Calcolo quote
    tot_dovuto = db.session.query(func.coalesce(func.sum(Iscrizione.importo_dovuto), 0.0)).filter(Iscrizione.stato != 'annullata').scalar()
    tot_incassato = db.session.query(func.coalesce(func.sum(Iscrizione.importo_pagato), 0.0)).filter(Iscrizione.stato != 'annullata').scalar()
    da_incassare = max(0.0, float(tot_dovuto) - float(tot_incassato))

    # Conteggi per categoria attività
    attivita = Attivita.query.all()
    attivita_stat = []
    for a in attivita:
        attivita_stat.append({
            'id': a.id,
            'titolo': a.titolo,
            'categoria': a.categoria,
            'posti_massimi': a.posti_massimi,
            'numero_iscritti': a.numero_iscritti,
            'quota': a.quota_iscrizione
        })

    return jsonify({
        'totale_persone': tot_persone,
        'totale_famiglie': tot_famiglie,
        'totale_utenti': tot_utenti,
        'totale_iscrizioni': tot_iscrizioni,
        'iscrizioni_confermate': iscrizioni_confermate,
        'iscrizioni_in_attesa': iscrizioni_in_attesa,
        'contabilita': {
            'totale_dovuto': round(float(tot_dovuto), 2),
            'totale_incassato': round(float(tot_incassato), 2),
            'saldo_residuo': round(float(da_incassare), 2)
        },
        'attivita': attivita_stat
    })
