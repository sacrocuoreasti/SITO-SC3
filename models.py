import json
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Tabella di associazione molti-a-molti: Persona <-> Lista
persona_lista = db.Table(
    'persona_lista',
    db.Column('codice_fiscale', db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), primary_key=True),
    db.Column('lista_id', db.Integer, db.ForeignKey('lista.id', ondelete='CASCADE'), primary_key=True)
)

# Tabella di associazione molti-a-molti: Persona <-> GruppoCatechismo
gruppo_catechismo_persona = db.Table(
    'gruppo_catechismo_persona',
    db.Column('gruppo_id', db.Integer, db.ForeignKey('gruppo_catechismo.id', ondelete='CASCADE'), primary_key=True),
    db.Column('codice_fiscale', db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), primary_key=True)
)

# Tabella di associazione molti-a-molti: Persona <-> GruppoDoposcuola
gruppo_doposcuola_persona = db.Table(
    'gruppo_doposcuola_persona',
    db.Column('gruppo_id', db.Integer, db.ForeignKey('gruppo_doposcuola.id', ondelete='CASCADE'), primary_key=True),
    db.Column('codice_fiscale', db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), primary_key=True)
)

# Tabella di associazione molti-a-molti: GruppoCatechismo <-> Utente (Più catechisti per gruppo)
gruppo_catechismo_catechisti = db.Table(
    'gruppo_catechismo_catechisti',
    db.Column('gruppo_id', db.Integer, db.ForeignKey('gruppo_catechismo.id', ondelete='CASCADE'), primary_key=True),
    db.Column('utente_id', db.Integer, db.ForeignKey('utente.id', ondelete='CASCADE'), primary_key=True)
)

# Tabella di associazione molti-a-molti: Persona <-> GruppoOratorio
gruppo_oratorio_persona = db.Table(
    'gruppo_oratorio_persona',
    db.Column('gruppo_id', db.Integer, db.ForeignKey('gruppo_oratorio.id', ondelete='CASCADE'), primary_key=True),
    db.Column('codice_fiscale', db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), primary_key=True)
)

# Tabella di associazione molti-a-molti: GruppoOratorio <-> Utente (Più animatori/referenti per gruppo)
gruppo_oratorio_animatori = db.Table(
    'gruppo_oratorio_animatori',
    db.Column('gruppo_id', db.Integer, db.ForeignKey('gruppo_oratorio.id', ondelete='CASCADE'), primary_key=True),
    db.Column('utente_id', db.Integer, db.ForeignKey('utente.id', ondelete='CASCADE'), primary_key=True)
)


class Persona(db.Model):
    __tablename__ = 'persona'

    codice_fiscale = db.Column(db.String(16), primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    sesso = db.Column(db.String(1), nullable=True)  # 'M' o 'F'
    data_nascita = db.Column(db.Date, nullable=True)
    luogo_nascita = db.Column(db.String(100), nullable=True)
    provincia_nascita = db.Column(db.String(10), nullable=True)
    
    # Residenza
    indirizzo_residenza = db.Column(db.String(200), nullable=True)
    comune_residenza = db.Column(db.String(100), default='Asti')
    cap_residenza = db.Column(db.String(10), default='14100')
    provincia_residenza = db.Column(db.String(10), default='AT')
    
    # Contatti
    telefono = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    
    # Quadro sanitario e alimentare
    intolleranze_alimentari = db.Column(db.Text, nullable=True)  # es. Celiachia, Lattosio, Favismo
    allergie = db.Column(db.Text, nullable=True)                 # es. Arachidi, Farmaci, Punture, Polline
    note_generali = db.Column(db.Text, nullable=True)
    
    # Documenti e sacramenti
    certificato_battesimo_path = db.Column(db.String(255), nullable=True)
    foto_profilo_url = db.Column(db.String(500), nullable=True)

    # Nucleo familiare
    nucleo_id = db.Column(db.Integer, db.ForeignKey('nucleo_familiare.id', ondelete='SET NULL'), nullable=True)
    ruolo_famiglia = db.Column(db.String(50), default='Figlio/a')  # 'Padre', 'Madre', 'Figlio/a', 'Fratello', 'Sorella', 'Nonno', 'Nonna', 'Capofamiglia', 'Coniuge', 'Altro'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relazioni
    nucleo = db.relationship('NucleoFamiliare', back_populates='componenti', foreign_keys=[nucleo_id])
    iscrizioni = db.relationship('Iscrizione', back_populates='partecipante', cascade='all, delete-orphan')
    utente = db.relationship('Utente', back_populates='persona', uselist=False, cascade='all, delete-orphan')
    liste = db.relationship('Lista', secondary=persona_lista, back_populates='membri')

    @property
    def nominativo(self):
        return f"{self.cognome} {self.nome}"

    @property
    def eta(self):
        if not self.data_nascita:
            return None
        today = date.today()
        return today.year - self.data_nascita.year - (
            (today.month, today.day) < (self.data_nascita.month, self.data_nascita.day)
        )

    def to_dict(self, include_family=True):
        d = {
            'codice_fiscale': self.codice_fiscale,
            'nome': self.nome,
            'cognome': self.cognome,
            'nominativo': self.nominativo,
            'sesso': self.sesso or 'M',
            'data_nascita': self.data_nascita.strftime('%Y-%m-%d') if self.data_nascita else None,
            'data_nascita_it': self.data_nascita.strftime('%d/%m/%Y') if self.data_nascita else '',
            'eta': self.eta,
            'luogo_nascita': self.luogo_nascita or '',
            'provincia_nascita': self.provincia_nascita or '',
            'indirizzo_residenza': self.indirizzo_residenza or '',
            'comune_residenza': self.comune_residenza or 'Asti',
            'cap_residenza': self.cap_residenza or '14100',
            'provincia_residenza': self.provincia_residenza or 'AT',
            'telefono': self.telefono or '',
            'email': self.email or '',
            'intolleranze_alimentari': self.intolleranze_alimentari or '',
            'allergie': self.allergie or '',
            'note_generali': self.note_generali or '',
            'certificato_battesimo_path': self.certificato_battesimo_path or '',
            'certificato_battesimo_url': self.certificato_battesimo_path if (self.certificato_battesimo_path and self.certificato_battesimo_path.startswith('http')) else (f"/uploads/{self.certificato_battesimo_path}" if self.certificato_battesimo_path else None),
            'foto_profilo_url': self.foto_profilo_url or '',
            'nucleo_id': self.nucleo_id,
            'ruolo_famiglia': self.ruolo_famiglia or 'Figlio/a',
            'has_account': bool(self.utente),
            'liste': [{'id': l.id, 'nome': l.nome, 'colore': l.colore or '#8B1E1E', 'icona': getattr(l, 'icona', '🏅') or '🏅', 'descrizione': l.descrizione or ''} for l in self.liste],
            'badges': [{'id': l.id, 'nome': l.nome, 'colore': l.colore or '#8B1E1E', 'icona': getattr(l, 'icona', '🏅') or '🏅', 'descrizione': l.descrizione or ''} for l in self.liste]
        }
        if include_family and self.nucleo:
            d['nome_famiglia'] = self.nucleo.nome_famiglia
            d['cf_capofamiglia'] = self.nucleo.codice_fiscale_capofamiglia
        else:
            d['nome_famiglia'] = None
            d['cf_capofamiglia'] = None
        return d


class NucleoFamiliare(db.Model):
    __tablename__ = 'nucleo_familiare'

    id = db.Column(db.Integer, primary_key=True)
    nome_famiglia = db.Column(db.String(120), nullable=False)
    codice_fiscale_capofamiglia = db.Column(
        db.String(16),
        db.ForeignKey('persona.codice_fiscale', ondelete='SET NULL', use_alter=True, name='fk_nucleo_capofamiglia'),
        nullable=True
    )
    telefono_principale = db.Column(db.String(30), nullable=True)
    indirizzo = db.Column(db.String(200), nullable=True)
    citta = db.Column(db.String(100), default='Asti')
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    capofamiglia = db.relationship('Persona', foreign_keys=[codice_fiscale_capofamiglia], post_update=True)
    componenti = db.relationship('Persona', back_populates='nucleo', foreign_keys=[Persona.nucleo_id])

    def to_dict(self, include_members=True):
        d = {
            'id': self.id,
            'nome_famiglia': self.nome_famiglia,
            'codice_fiscale_capofamiglia': self.codice_fiscale_capofamiglia,
            'telefono_principale': self.telefono_principale or '',
            'indirizzo': self.indirizzo or '',
            'citta': self.citta or 'Asti',
            'note': self.note or '',
            'numero_componenti': len(self.componenti) if self.componenti else 0
        }
        if self.capofamiglia:
            d['capofamiglia_nome'] = self.capofamiglia.nominativo
            d['capofamiglia_email'] = self.capofamiglia.email
            d['capofamiglia_telefono'] = self.capofamiglia.telefono
        else:
            d['capofamiglia_nome'] = 'Non specificato'
            d['capofamiglia_email'] = ''
            d['capofamiglia_telefono'] = ''

        if include_members and self.componenti:
            d['componenti'] = [c.to_dict(include_family=False) for c in self.componenti]
        else:
            d['componenti'] = []
        return d


class Utente(UserMixin, db.Model):
    __tablename__ = 'utente'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    codice_fiscale = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), unique=True, nullable=True)
    
    # Ruoli: 'utente', 'genitore', 'catechista', 'oratorio', 'segreteria', 'parroco', 'admin'
    ruolo = db.Column(db.String(30), default='utente', nullable=False)
    privilegi_extra = db.Column(db.Text, default='[]')  # memorizza JSON di ruoli extra
    campi_extra = db.Column(db.Text, default='{}')      # campi dinamici personalizzati dalla segreteria
    is_attivo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relazioni
    persona = db.relationship('Persona', back_populates='utente', foreign_keys=[codice_fiscale])
    iscrizioni_effettuate = db.relationship('Iscrizione', back_populates='iscritto_da')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_all_roles(self):
        roles = {self.ruolo}
        try:
            extra = json.loads(self.privilegi_extra or '[]')
            if isinstance(extra, list):
                for r in extra:
                    roles.add(r)
        except Exception:
            pass
        return list(roles)

    def has_role(self, *ruoli):
        all_roles = self.get_all_roles()
        if 'admin' in all_roles:
            return True
        if any(r in all_roles for r in ruoli):
            return True
        # Parroco ha accesso supervisore completo
        if 'parroco' in all_roles and any(r in ['segreteria', 'catechista', 'oratorio', 'parroco', 'genitore', 'utente'] for r in ruoli):
            return True
        # Segreteria ha accesso anche alle viste oratorio/catechismo
        if 'segreteria' in all_roles and any(r in ['catechista', 'oratorio', 'utente'] for r in ruoli):
            return True
        # Utente base o genitore
        if ('utente' in all_roles or 'genitore' in all_roles) and any(r in ['utente', 'genitore'] for r in ruoli):
            return True
        return False

    def to_dict(self):
        campi_extra_dict = {}
        try:
            campi_extra_dict = json.loads(self.campi_extra or '{}')
        except Exception:
            pass

        return {
            'id': self.id,
            'email': self.email,
            'ruolo': self.ruolo,
            'tutti_i_ruoli': self.get_all_roles(),
            'codice_fiscale': self.codice_fiscale,
            'is_attivo': self.is_attivo,
            'campi_extra': campi_extra_dict,
            'is_gestione_pura': self.ruolo in ['segreteria', 'oratorio'] or not self.codice_fiscale,
            'nominativo': self.persona.nominativo if self.persona else self.email.split('@')[0],
            'telefono': self.persona.telefono if self.persona else '',
            'nucleo_id': self.persona.nucleo_id if self.persona else None,
            'persona': self.persona.to_dict() if self.persona else None
        }


class Attivita(db.Model):
    __tablename__ = 'attivita'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)  # 'oratorio', 'catechismo', 'campo_estivo', 'doposcuola', 'evento', 'altro'
    descrizione = db.Column(db.Text, nullable=True)
    anno_pastorale = db.Column(db.String(20), default='2025/2026')
    eta_min = db.Column(db.Integer, default=0)
    eta_max = db.Column(db.Integer, default=99)
    quota_iscrizione = db.Column(db.Float, default=0.0)
    posti_massimi = db.Column(db.Integer, nullable=True)
    data_inizio = db.Column(db.Date, nullable=True)
    data_fine = db.Column(db.Date, nullable=True)
    is_attiva = db.Column(db.Boolean, default=True)
    is_pubblicato = db.Column(db.Boolean, default=True)  # True = Pubblicato, False = Bozza
    locandina_path = db.Column(db.String(255), nullable=True)  # Volantino o locandina caricata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    iscrizioni = db.relationship('Iscrizione', back_populates='attivita', cascade='all, delete-orphan')

    @property
    def numero_iscritti(self):
        return len([i for i in self.iscrizioni if i.stato in ['confermata', 'in_attesa']])

    @property
    def posti_disponibili(self):
        if self.posti_massimi is None:
            return None
        return max(0, self.posti_massimi - self.numero_iscritti)

    _campi_extra = db.Column('campi_extra', db.Text, default='{}')
    _campi_personalizzati = db.Column('campi_personalizzati', db.Text, default='[]')

    @property
    def campi_extra(self):
        if not self._campi_extra:
            return {}
        try:
            import json
            return json.loads(self._campi_extra)
        except Exception:
            return {}

    @campi_extra.setter
    def campi_extra(self, val):
        import json
        if isinstance(val, (dict, list)):
            self._campi_extra = json.dumps(val)
        elif isinstance(val, str):
            self._campi_extra = val
        else:
            self._campi_extra = '{}'

    @property
    def campi_personalizzati(self):
        if not self._campi_personalizzati:
            return []
        try:
            import json
            val = json.loads(self._campi_personalizzati)
            return val if isinstance(val, list) else []
        except Exception:
            return []

    @campi_personalizzati.setter
    def campi_personalizzati(self, val):
        import json
        if isinstance(val, list):
            self._campi_personalizzati = json.dumps(val)
        elif isinstance(val, str):
            self._campi_personalizzati = val
        else:
            self._campi_personalizzati = '[]'

    def to_dict(self):
        return {
            'id': self.id,
            'titolo': self.titolo,
            'categoria': self.categoria,
            'descrizione': self.descrizione or '',
            'anno_pastorale': self.anno_pastorale,
            'eta_min': self.eta_min,
            'eta_max': self.eta_max,
            'quota_iscrizione': self.quota_iscrizione,
            'posti_massimi': self.posti_massimi,
            'posti_disponibili': self.posti_disponibili,
            'numero_iscritti': self.numero_iscritti,
            'data_inizio': self.data_inizio.strftime('%Y-%m-%d') if self.data_inizio else None,
            'data_fine': self.data_fine.strftime('%Y-%m-%d') if self.data_fine else None,
            'data_inizio_it': self.data_inizio.strftime('%d/%m/%Y') if self.data_inizio else '',
            'data_fine_it': self.data_fine.strftime('%d/%m/%Y') if self.data_fine else '',
            'is_attiva': self.is_attiva,
            'is_pubblicato': self.is_pubblicato,
            'locandina_path': self.locandina_path or '',
            'locandina_url': self.locandina_path if (self.locandina_path and self.locandina_path.startswith('http')) else (f"/uploads/{self.locandina_path}" if self.locandina_path else None),
            'campi_extra': self.campi_extra,
            'campi_personalizzati': self.campi_personalizzati
        }


class Iscrizione(db.Model):
    __tablename__ = 'iscrizione'

    id = db.Column(db.Integer, primary_key=True)
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='CASCADE'), nullable=False)
    codice_fiscale_partecipante = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), nullable=False)
    iscritto_da_id = db.Column(db.Integer, db.ForeignKey('utente.id', ondelete='SET NULL'), nullable=True)
    
    data_iscrizione = db.Column(db.DateTime, default=datetime.utcnow)
    stato = db.Column(db.String(30), default='confermata')  # 'in_attesa', 'confermata', 'rifiutata', 'annullata'
    stato_pagamento = db.Column(db.String(30), default='da_pagare')  # 'da_pagare', 'acconto', 'saldato', 'esente'
    
    importo_dovuto = db.Column(db.Float, default=0.0)
    importo_pagato = db.Column(db.Float, default=0.0)
    
    note_iscrizione = db.Column(db.Text, nullable=True)
    squadra = db.Column(db.String(50), nullable=True)  # 'Rossi', 'Gialli', 'Blu', 'Verdi'
    consenso_privacy = db.Column(db.Boolean, default=True)
    consenso_foto = db.Column(db.Boolean, default=True)
    consenso_uscite = db.Column(db.Boolean, default=True)
    clausole_accettate = db.Column(db.Text, default='{}')  # memorizza JSON di clausole personalizzate accettate
    campi_personalizzati = db.Column(db.Text, default='{}')  # risposte ai campi personalizzati specifici dell'evento

    # Relazioni
    attivita = db.relationship('Attivita', back_populates='iscrizioni')
    partecipante = db.relationship('Persona', back_populates='iscrizioni')
    iscritto_da = db.relationship('Utente', back_populates='iscrizioni_effettuate')

    def to_dict(self):
        p = self.partecipante
        nucleo = p.nucleo if p else None
        capo = nucleo.capofamiglia if nucleo else None
        
        telefono_contatto = p.telefono if p and p.telefono else (capo.telefono if capo else '')
        email_contatto = p.email if p and p.email else (capo.email if capo else '')

        clausole_dict = {}
        try:
            clausole_dict = json.loads(self.clausole_accettate or '{}')
        except Exception:
            pass

        campi_pers_dict = {}
        try:
            campi_pers_dict = json.loads(self.campi_personalizzati or '{}')
        except Exception:
            pass

        return {
            'id': self.id,
            'attivita_id': self.attivita_id,
            'attivita_titolo': self.attivita.titolo if self.attivita else '',
            'attivita_categoria': self.attivita.categoria if self.attivita else '',
            'codice_fiscale_partecipante': self.codice_fiscale_partecipante,
            'partecipante_nome': p.nominativo if p else '',
            'partecipante_eta': p.eta if p else '',
            'partecipante_sesso': p.sesso if p else '',
            'partecipante_data_nascita': p.data_nascita.strftime('%d/%m/%Y') if (p and p.data_nascita) else '',
            'allergie': p.allergie if p else '',
            'intolleranze_alimentari': p.intolleranze_alimentari if p else '',
            'nome_famiglia': nucleo.nome_famiglia if nucleo else 'Non associato',
            'telefono_contatto': telefono_contatto,
            'email_contatto': email_contatto,
            'data_iscrizione': self.data_iscrizione.strftime('%d/%m/%Y %H:%M') if self.data_iscrizione else '',
            'stato': self.stato,
            'stato_pagamento': self.stato_pagamento,
            'importo_dovuto': self.importo_dovuto,
            'importo_pagato': self.importo_pagato,
            'saldo_rimanente': max(0.0, (self.importo_dovuto or 0.0) - (self.importo_pagato or 0.0)),
            'note_iscrizione': self.note_iscrizione or '',
            'squadra': self.squadra or '',
            'consenso_privacy': self.consenso_privacy,
            'consenso_foto': self.consenso_foto,
            'consenso_uscite': self.consenso_uscite,
            'clausole_accettate': clausole_dict,
            'campi_personalizzati': campi_pers_dict
        }


# ================= LISTE & BADGE SEGRETERIA =================
class Lista(db.Model):
    __tablename__ = 'lista'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    colore = db.Column(db.String(20), default='#8B1E1E')
    icona = db.Column(db.String(30), default='🏅')
    categoria = db.Column(db.String(50), default='badge')
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    membri = db.relationship('Persona', secondary=persona_lista, back_populates='liste')
    attivita = db.relationship('Attivita')

    def to_dict(self, include_members=True):
        d = {
            'id': self.id,
            'nome': self.nome,
            'descrizione': self.descrizione or '',
            'colore': self.colore or '#8B1E1E',
            'icona': self.icona or '🏅',
            'categoria': self.categoria or 'badge',
            'attivita_id': self.attivita_id,
            'attivita_titolo': self.attivita.titolo if self.attivita else '',
            'totale_iscritti': len(self.membri),
            'created_at': self.created_at.strftime('%d/%m/%Y') if self.created_at else ''
        }
        if include_members:
            d['membri'] = [m.to_dict(include_family=False) for m in self.membri]
        return d


# ================= GRUPPI CATECHISMO =================
class GruppoCatechismo(db.Model):
    __tablename__ = 'gruppo_catechismo'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)  # es. "3ª Elementare - Gruppo A"
    anno_pastorale = db.Column(db.String(20), default='2026/2027')
    anno_catechismo = db.Column(db.String(50), nullable=True)  # es. "1° Anno Comunione", "2° Anno Comunione", "Cresima"
    catechista_nome = db.Column(db.String(120), nullable=True)
    catechista_cf = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='SET NULL'), nullable=True)
    catechista_utente_id = db.Column(db.Integer, db.ForeignKey('utente.id', ondelete='SET NULL'), nullable=True)
    orario_incontri = db.Column(db.String(100), nullable=True)
    aula = db.Column(db.String(50), nullable=True)
    google_calendar_url = db.Column(db.String(500), nullable=True)
    note = db.Column(db.Text, nullable=True)
    stato = db.Column(db.String(20), default='pubblico')  # 'pubblico', 'bozza', 'chiuso'
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    ragazzi = db.relationship('Persona', secondary=gruppo_catechismo_persona, backref='gruppi_catechismo')
    catechisti = db.relationship('Utente', secondary=gruppo_catechismo_catechisti, backref='gruppi_catechismo_assegnati')
    catechista = db.relationship('Persona', foreign_keys=[catechista_cf])
    catechista_utente = db.relationship('Utente', foreign_keys=[catechista_utente_id])
    attivita = db.relationship('Attivita')

    def to_dict(self, include_ragazzi=True):
        catechisti_list = []
        if self.catechisti:
            for u in self.catechisti:
                catechisti_list.append({
                    'id': u.id,
                    'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                    'email': u.email,
                    'telefono': u.persona.telefono if u.persona else ''
                })
        elif self.catechista_utente:
            u = self.catechista_utente
            catechisti_list.append({
                'id': u.id,
                'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                'email': u.email,
                'telefono': u.persona.telefono if u.persona else ''
            })

        nomi_catechisti = ", ".join([c['nominativo'] for c in catechisti_list]) if catechisti_list else (self.catechista_nome or (self.catechista.nominativo if self.catechista else 'Da assegnare'))

        d = {
            'id': self.id,
            'nome': self.nome,
            'anno_pastorale': self.anno_pastorale or '2026/2027',
            'anno_catechismo': self.anno_catechismo or '',
            'catechista_nome': nomi_catechisti,
            'catechista_cf': self.catechista_cf or '',
            'catechista_utente_id': self.catechista_utente_id,
            'catechisti': catechisti_list,
            'catechisti_ids': [c['id'] for c in catechisti_list],
            'orario_incontri': self.orario_incontri or '',
            'aula': self.aula or '',
            'google_calendar_url': self.google_calendar_url or '',
            'note': self.note or '',
            'stato': self.stato or 'pubblico',
            'attivita_id': self.attivita_id,
            'attivita_titolo': self.attivita.titolo if self.attivita else '',
            'totale_ragazzi': len(self.ragazzi)
        }
        if include_ragazzi:
            d['ragazzi'] = [r.to_dict(include_family=True) for r in self.ragazzi]
        return d


# ================= GRUPPI DOPOSCUOLA =================
class GruppoDoposcuola(db.Model):
    __tablename__ = 'gruppo_doposcuola'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)  # es. "Doposcuola Primaria - Compiti e Studio"
    anno_scolastico = db.Column(db.String(20), default='2026/2027')
    fascia_eta = db.Column(db.String(50), nullable=True)  # es. "Scuola Primaria (6-10 anni)", "Secondaria (11-14 anni)"
    educatore_nome = db.Column(db.String(120), nullable=True)
    educatore_cf = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='SET NULL'), nullable=True)
    educatore_utente_id = db.Column(db.Integer, db.ForeignKey('utente.id', ondelete='SET NULL'), nullable=True)
    giorni_orari = db.Column(db.String(100), nullable=True)  # es. "Lun-Mer-Ven 16:30 - 18:30"
    aula = db.Column(db.String(50), nullable=True)
    note = db.Column(db.Text, nullable=True)
    stato = db.Column(db.String(20), default='pubblico')  # 'pubblico', 'bozza', 'chiuso'
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    studenti = db.relationship('Persona', secondary=gruppo_doposcuola_persona, backref='gruppi_doposcuola')
    educatore = db.relationship('Persona', foreign_keys=[educatore_cf])
    educatore_utente = db.relationship('Utente', foreign_keys=[educatore_utente_id])
    attivita = db.relationship('Attivita')

    def to_dict(self, include_studenti=True):
        d = {
            'id': self.id,
            'nome': self.nome,
            'anno_scolastico': self.anno_scolastico or '2026/2027',
            'anno_pastorale': self.anno_scolastico or '2026/2027',
            'fascia_eta': self.fascia_eta or '',
            'educatore_nome': self.educatore_nome or (self.educatore.nominativo if self.educatore else 'Da assegnare'),
            'educatore_cf': self.educatore_cf or '',
            'educatore_utente_id': self.educatore_utente_id,
            'giorni_orari': self.giorni_orari or '',
            'orario_incontri': self.giorni_orari or '',
            'aula': self.aula or '',
            'note': self.note or '',
            'stato': self.stato or 'pubblico',
            'attivita_id': self.attivita_id,
            'attivita_titolo': self.attivita.titolo if self.attivita else '',
            'totale_studenti': len(self.studenti),
            'totale_ragazzi': len(self.studenti)
        }
        if include_studenti:
            d['studenti'] = [r.to_dict(include_family=True) for r in self.studenti]
            d['ragazzi'] = d['studenti']
        return d


# ================= GRUPPI ORATORIO (ESTIVO & INVERNALE) =================
class GruppoOratorio(db.Model):
    __tablename__ = 'gruppo_oratorio'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)  # es. "Squadra Gialla - Estivo", "Oratorio Invernale Medie"
    anno_pastorale = db.Column(db.String(20), default='2026/2027')
    tipo_oratorio = db.Column(db.String(30), default='estivo')  # 'estivo' (Estate Ragazzi) o 'invernale' (Oratorio Invernale)
    animatore_referente_nome = db.Column(db.String(120), nullable=True)
    animatore_cf = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='SET NULL'), nullable=True)
    animatore_utente_id = db.Column(db.Integer, db.ForeignKey('utente.id', ondelete='SET NULL'), nullable=True)
    giorni_orari = db.Column(db.String(100), nullable=True)
    aula = db.Column(db.String(50), nullable=True)
    note = db.Column(db.Text, nullable=True)
    stato = db.Column(db.String(20), default='pubblico')  # 'pubblico', 'bozza', 'chiuso'
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relazioni
    ragazzi = db.relationship('Persona', secondary=gruppo_oratorio_persona, backref='gruppi_oratorio')
    animatori = db.relationship('Utente', secondary=gruppo_oratorio_animatori, backref='gruppi_oratorio_assegnati')
    animatore = db.relationship('Persona', foreign_keys=[animatore_cf])
    animatore_utente = db.relationship('Utente', foreign_keys=[animatore_utente_id])
    attivita = db.relationship('Attivita')

    def to_dict(self, include_ragazzi=True):
        animatori_list = []
        if self.animatori:
            for u in self.animatori:
                animatori_list.append({
                    'id': u.id,
                    'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                    'email': u.email,
                    'telefono': u.persona.telefono if u.persona else ''
                })
        elif self.animatore_utente:
            u = self.animatore_utente
            animatori_list.append({
                'id': u.id,
                'nominativo': u.persona.nominativo if u.persona else u.email.split('@')[0],
                'email': u.email,
                'telefono': u.persona.telefono if u.persona else ''
            })

        nomi_animatori = ", ".join([a['nominativo'] for a in animatori_list]) if animatori_list else (self.animatore_referente_nome or (self.animatore.nominativo if self.animatore else 'Da assegnare'))

        d = {
            'id': self.id,
            'nome': self.nome,
            'anno_pastorale': self.anno_pastorale or '2026/2027',
            'tipo_oratorio': self.tipo_oratorio or 'estivo',
            'animatore_referente_nome': nomi_animatori,
            'animatori_nomi': nomi_animatori,
            'animatore_cf': self.animatore_cf or '',
            'animatore_utente_id': self.animatore_utente_id,
            'animatori': animatori_list,
            'animatori_ids': [a['id'] for a in animatori_list],
            'giorni_orari': self.giorni_orari or '',
            'orario_incontri': self.giorni_orari or '',
            'aula': self.aula or '',
            'luogo': self.aula or 'Oratorio Sacro Cuore',
            'note': self.note or '',
            'stato': self.stato or 'pubblico',
            'attivita_id': self.attivita_id,
            'attivita_titolo': self.attivita.titolo if self.attivita else '',
            'totale_ragazzi': len(self.ragazzi)
        }
        if include_ragazzi:
            d['ragazzi'] = [r.to_dict(include_family=True) for r in self.ragazzi]
        return d


class Presenza(db.Model):
    __tablename__ = 'presenza'

    id = db.Column(db.Integer, primary_key=True)
    attivita_id = db.Column(db.Integer, db.ForeignKey('attivita.id', ondelete='CASCADE'), nullable=False)
    codice_fiscale_persona = db.Column(db.String(16), db.ForeignKey('persona.codice_fiscale', ondelete='CASCADE'), nullable=False)
    data = db.Column(db.Date, default=date.today, nullable=False)
    presente = db.Column(db.Boolean, default=True)
    concorre_percentuale = db.Column(db.Boolean, default=True)  # True se l'incontro fa media presenze
    titolo_incontro = db.Column(db.String(100), nullable=True)  # es. "Festa Parrocchiale" o "Incontro Ordinario"
    note = db.Column(db.String(255), nullable=True)

    persona = db.relationship('Persona')
    attivita = db.relationship('Attivita')

    def to_dict(self):
        return {
            'id': self.id,
            'attivita_id': self.attivita_id,
            'codice_fiscale_persona': self.codice_fiscale_persona,
            'data': self.data.isoformat(),
            'presente': self.presente,
            'concorre_percentuale': self.concorre_percentuale if self.concorre_percentuale is not None else True,
            'titolo_incontro': self.titolo_incontro or '',
            'note': self.note or '',
            'nominativo': self.persona.nominativo if self.persona else ''
        }


class NotiziaEvento(db.Model):
    __tablename__ = 'notizia_evento'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(50), default='avviso')  # 'evento', 'avviso', 'oratorio', 'catechismo'
    contenuto = db.Column(db.Text, nullable=False)
    data_evento = db.Column(db.Date, nullable=True)
    in_evidenza = db.Column(db.Boolean, default=True)
    is_pubblicato = db.Column(db.Boolean, default=True)  # True = Pubblicato, False = Bozza
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'titolo': self.titolo,
            'categoria': self.categoria,
            'contenuto': self.contenuto,
            'data_evento': self.data_evento.strftime('%d/%m/%Y') if self.data_evento else None,
            'in_evidenza': self.in_evidenza,
            'is_pubblicato': self.is_pubblicato
        }


class ImpostazioniSito(db.Model):
    __tablename__ = 'impostazioni_sito'

    id = db.Column(db.Integer, primary_key=True)
    mostra_orari_messe = db.Column(db.Boolean, default=True)
    mostra_attivita = db.Column(db.Boolean, default=True)
    mostra_avvisi = db.Column(db.Boolean, default=True)
    mostra_contatti = db.Column(db.Boolean, default=True)
    mostra_banner = db.Column(db.Boolean, default=False)
    testo_banner = db.Column(db.String(255), default='Iscrizioni parrocchiali aperte!')
    titolo_hero = db.Column(db.String(200), default='Parrocchia Sacro Cuore di Gesù')
    sottotitolo_hero = db.Column(db.String(255), default='Diocesi di Asti · Via Pier Santi Mattarella 2')
    testo_benvenuto = db.Column(db.Text, default='Benvenuti nello spazio dedicato alla comunità parrocchiale del Sacro Cuore di Asti. Gestisci le iscrizioni all\'Estate Ragazzi, al catechismo e ai campi estivi in modo semplice e sicuro.')
    
    # Campi personalizzabili Segreteria & Recapiti Homepage
    segreteria_titolo = db.Column(db.String(150), default='Segreteria & Recapiti')
    segreteria_sottotitolo = db.Column(db.String(255), default='Siamo a tua disposizione per informazioni su catechesi, certificati e attività parrocchiali')
    segreteria_indirizzo = db.Column(db.Text, default='Parrocchia Sacro Cuore di Gesù\nVia Pier Santi Mattarella 2\n14100 Asti (AT) · Diocesi di Asti')
    segreteria_telefono = db.Column(db.String(100), default='0141 355150')
    segreteria_email = db.Column(db.String(120), default='sacrocuoreasti@gmail.com')
    segreteria_orari = db.Column(db.Text, default='Martedì e Giovedì: 16:00 - 18:30\nSabato mattina: 09:30 - 11:30\nDomenica: dopo le Sante Messe')
    
    # Donazioni & Offerte Parrocchiali
    iban = db.Column(db.String(50), default='IT60X0542811101000000123456')
    satispay_url = db.Column(db.String(300), default='https://tag.satispay.com/sacrocuoreasti')
    intestatario_offerte = db.Column(db.String(150), default='Parrocchia Sacro Cuore di Gesù - Asti')
    causale_predefinita_offerte = db.Column(db.String(150), default='Offerta liberale per le attività parrocchiali')
    
    init_defaults_completed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'mostra_orari_messe': self.mostra_orari_messe,
            'mostra_attivita': self.mostra_attivita,
            'mostra_avvisi': self.mostra_avvisi,
            'mostra_contatti': self.mostra_contatti,
            'mostra_banner': self.mostra_banner,
            'testo_banner': self.testo_banner or '',
            'titolo_hero': self.titolo_hero or 'Parrocchia Sacro Cuore di Gesù',
            'sottotitolo_hero': self.sottotitolo_hero or 'Diocesi di Asti · Via Pier Santi Mattarella 2',
            'testo_benvenuto': self.testo_benvenuto or '',
            'segreteria_titolo': self.segreteria_titolo or 'Segreteria & Recapiti',
            'segreteria_sottotitolo': self.segreteria_sottotitolo or 'Siamo a tua disposizione per informazioni su catechesi, certificati e attività parrocchiali',
            'segreteria_indirizzo': self.segreteria_indirizzo or 'Parrocchia Sacro Cuore di Gesù\nVia Pier Santi Mattarella 2\n14100 Asti (AT) · Diocesi di Asti',
            'segreteria_telefono': self.segreteria_telefono or '0141 355150',
            'segreteria_email': self.segreteria_email or 'sacrocuoreasti@gmail.com',
            'segreteria_orari': self.segreteria_orari or 'Martedì e Giovedì: 16:00 - 18:30\nSabato mattina: 09:30 - 11:30\nDomenica: dopo le Sante Messe',
            'iban': self.iban or 'IT60X0542811101000000123456',
            'satispay_url': self.satispay_url or 'https://tag.satispay.com/sacrocuoreasti',
            'intestatario_offerte': self.intestatario_offerte or 'Parrocchia Sacro Cuore di Gesù - Asti',
            'causale_predefinita_offerte': self.causale_predefinita_offerte or 'Offerta liberale per le attività parrocchiali'
        }


# ================= CONFIGURAZIONI SEGRETERIA =================
class CategoriaAttivita(db.Model):
    __tablename__ = 'categoria_attivita'

    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    icona = db.Column(db.String(30), default='✦')
    is_attiva = db.Column(db.Boolean, default=True)
    ordine = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'codice': self.codice,
            'nome': self.nome,
            'icona': self.icona or '✦',
            'is_attiva': self.is_attiva,
            'ordine': self.ordine
        }


class AllergiaConfig(db.Model):
    __tablename__ = 'allergia_config'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    categoria = db.Column(db.String(50), default='alimentare')  # 'alimentare', 'ambientale', 'medica', 'altro'
    is_attiva = db.Column(db.Boolean, default=True)
    ordine = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'categoria': self.categoria,
            'is_attiva': self.is_attiva,
            'ordine': self.ordine
        }


class ClausolaIscrizione(db.Model):
    __tablename__ = 'clausola_iscrizione'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(150), nullable=False)
    testo = db.Column(db.Text, nullable=False)
    is_obbligatoria = db.Column(db.Boolean, default=True)
    is_attiva = db.Column(db.Boolean, default=True)
    ordine = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'titolo': self.titolo,
            'testo': self.testo,
            'is_obbligatoria': self.is_obbligatoria,
            'is_attiva': self.is_attiva,
            'ordine': self.ordine
        }


class CampoPersonalizzato(db.Model):
    __tablename__ = 'campo_personalizzato'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)      # Etichetta visibile, es. "Professione"
    chiave = db.Column(db.String(50), unique=True, nullable=False)  # es. "professione"
    tipo = db.Column(db.String(30), default='testo')      # 'testo', 'numero', 'data', 'checkbox', 'select'
    obbligatorio = db.Column(db.Boolean, default=False)
    opzioni = db.Column(db.Text, nullable=True)           # opzioni separate da virgola per select
    is_attivo = db.Column(db.Boolean, default=True)
    ordine = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'chiave': self.chiave,
            'tipo': self.tipo,
            'obbligatorio': self.obbligatorio,
            'opzioni': self.opzioni or '',
            'is_attivo': self.is_attivo,
            'ordine': self.ordine
        }


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_token'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    codice = db.Column(db.String(10), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Celebrazione(db.Model):
    __tablename__ = 'celebrazione'

    id = db.Column(db.Integer, primary_key=True)
    sezione = db.Column(db.String(30), nullable=False, default='messe')  # 'messe', 'liturgia', 'avvenimenti'
    titolo = db.Column(db.String(150), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    giorno = db.Column(db.String(100), nullable=True)    # es. "Lunedì - Venerdì", "Domenica e Festivi"
    orario = db.Column(db.String(100), nullable=True)    # es. "ore 18:00", "ore 09:00 e 11:00"
    luogo = db.Column(db.String(120), default='Chiesa Parrocchiale')
    ordine = db.Column(db.Integer, default=0)
    is_attivo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sezione': self.sezione,
            'titolo': self.titolo,
            'descrizione': self.descrizione or '',
            'giorno': self.giorno or '',
            'orario': self.orario or '',
            'luogo': self.luogo or 'Chiesa Parrocchiale',
            'ordine': self.ordine,
            'is_attivo': self.is_attivo
        }


class CalendarioComunita(db.Model):
    __tablename__ = 'calendario_comunita'

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(150), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    google_calendar_url = db.Column(db.String(500), nullable=False)
    colore = db.Column(db.String(30), default='#8B1E1E')
    icona = db.Column(db.String(30), default='📅')
    categoria = db.Column(db.String(50), default='parrocchia')  # 'parrocchia', 'catechismo', 'oratorio', 'giovani', 'liturgia'
    is_pubblico = db.Column(db.Boolean, default=True)
    ordine = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'titolo': self.titolo,
            'descrizione': self.descrizione or '',
            'google_calendar_url': self.google_calendar_url,
            'colore': self.colore or '#8B1E1E',
            'icona': self.icona or '📅',
            'categoria': self.categoria or 'parrocchia',
            'is_pubblico': self.is_pubblico,
            'ordine': self.ordine
        }


def init_default_configurazioni():
    """Inizializza categorie, allergie, clausole, celebrazioni e campi account se non presenti."""
    try:
        # Crea eventuali nuove tabelle
        db.create_all()

        # Verifica ed aggiunta colonne mancanti per SQLite
        from sqlalchemy import text
        col_checks = [
            ('persona', 'certificato_battesimo_path', 'VARCHAR(255)'),
            ('persona', 'foto_profilo_url', 'VARCHAR(500)'),
            ('utente', 'campi_extra', 'TEXT DEFAULT "{}"'),
            ('attivita', 'locandina_path', 'VARCHAR(255)'),
            ('attivita', 'campi_extra', 'TEXT DEFAULT "{}"'),
            ('attivita', 'campi_personalizzati', 'TEXT DEFAULT "[]"'),
            ('iscrizione', 'clausole_accettate', 'TEXT DEFAULT "{}"'),
            ('iscrizione', 'campi_personalizzati', 'TEXT DEFAULT "{}"'),
            ('lista', 'icona', 'VARCHAR(30) DEFAULT "🏅"'),
            ('lista', 'categoria', 'VARCHAR(50) DEFAULT "badge"'),
            ('gruppo_catechismo', 'catechista_utente_id', 'INTEGER'),
            ('gruppo_catechismo', 'stato', 'VARCHAR(20) DEFAULT "pubblico"'),
            ('gruppo_catechismo', 'google_calendar_url', 'VARCHAR(500)'),
            ('gruppo_doposcuola', 'stato', 'VARCHAR(20) DEFAULT "pubblico"'),
            ('gruppo_oratorio', 'stato', 'VARCHAR(20) DEFAULT "pubblico"'),
            ('presenza', 'concorre_percentuale', 'BOOLEAN DEFAULT 1'),
            ('presenza', 'titolo_incontro', 'VARCHAR(100)'),
            ('impostazioni_sito', 'segreteria_titolo', 'VARCHAR(150) DEFAULT "Segreteria & Recapiti"'),
            ('impostazioni_sito', 'segreteria_sottotitolo', 'VARCHAR(255) DEFAULT "Siamo a tua disposizione per informazioni su catechesi, certificati e attività parrocchiali"'),
            ('impostazioni_sito', 'segreteria_indirizzo', 'TEXT'),
            ('impostazioni_sito', 'segreteria_telefono', 'VARCHAR(100) DEFAULT "0141 355150"'),
            ('impostazioni_sito', 'segreteria_email', 'VARCHAR(120) DEFAULT "sacrocuoreasti@gmail.com"'),
            ('impostazioni_sito', 'segreteria_orari', 'TEXT'),
            ('impostazioni_sito', 'iban', 'VARCHAR(50) DEFAULT "IT60X0542811101000000123456"'),
            ('impostazioni_sito', 'satispay_url', 'VARCHAR(300) DEFAULT "https://tag.satispay.com/sacrocuoreasti"'),
            ('impostazioni_sito', 'intestatario_offerte', 'VARCHAR(150) DEFAULT "Parrocchia Sacro Cuore di Gesù - Asti"'),
            ('impostazioni_sito', 'causale_predefinita_offerte', 'VARCHAR(150) DEFAULT "Offerta liberale per le attività parrocchiali"'),
            ('impostazioni_sito', 'init_defaults_completed', 'BOOLEAN DEFAULT 0')
        ]
        for table, col, col_type in col_checks:
            try:
                res = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing_cols = [r[1] for r in res]
                if col not in existing_cols:
                    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    db.session.commit()
            except Exception:
                db.session.rollback()

        imp = ImpostazioniSito.query.first()
        if not imp:
            imp = ImpostazioniSito(init_defaults_completed=False)
            db.session.add(imp)
            db.session.commit()

        already_initialized = bool(getattr(imp, 'init_defaults_completed', False))

        if not already_initialized:
            # 1. Categorie attività parrocchiali
            if CategoriaAttivita.query.count() == 0:
                cats = [
                    CategoriaAttivita(codice='oratorio', nome='Estate Ragazzi / Oratorio', icona='🏓', ordine=1),
                    CategoriaAttivita(codice='catechismo', nome='Catechismo & Iniziazione', icona='📖', ordine=2),
                    CategoriaAttivita(codice='campo_estivo', nome='Campi Scuola Estivi', icona='🏕️', ordine=3),
                    CategoriaAttivita(codice='doposcuola', nome='Doposcuola & Studio', icona='✏️', ordine=4),
                    CategoriaAttivita(codice='famiglie', nome='Incontri Famiglie & Adulti', icona='👨‍👩‍👧‍👦', ordine=5),
                    CategoriaAttivita(codice='pellegrinaggio', nome='Gite & Pellegrinaggi', icona='🚶', ordine=6),
                    CategoriaAttivita(codice='evento', nome='Feste e Momenti Comunitari', icona='🎈', ordine=7)
                ]
                db.session.add_all(cats)

            # 2. Allergie ed intolleranze suggerite
            if AllergiaConfig.query.count() == 0:
                allergie = [
                    AllergiaConfig(nome='Lattosio', categoria='alimentare', ordine=1),
                    AllergiaConfig(nome='Glutine (Celiachia)', categoria='alimentare', ordine=2),
                    AllergiaConfig(nome='Epistassi', categoria='medica', ordine=3),
                    AllergiaConfig(nome='Graminacee', categoria='ambientale', ordine=4),
                    AllergiaConfig(nome='Acari', categoria='ambientale', ordine=5),
                    AllergiaConfig(nome='Arachidi e Frutta Secca', categoria='alimentare', ordine=6),
                    AllergiaConfig(nome='Favismo (G6PD)', categoria='alimentare', ordine=7),
                    AllergiaConfig(nome='Punture di Insetti (Api/Vespe)', categoria='medica', ordine=8),
                ]
                db.session.add_all(allergie)

            # 3. Clausole per l'iscrizione
            if ClausolaIscrizione.query.count() == 0:
                clausole = [
                    ClausolaIscrizione(
                        titolo='Informativa e Trattamento Dati Personali (GDPR)',
                        testo='Dichiaro di aver preso visione dell\'informativa privacy (Reg. UE 2016/679) e acconsento al trattamento dei dati anagrafici e sanitari per le finalità organizzative e pastorali della parrocchia.',
                        is_obbligatoria=True,
                        ordine=1
                    ),
                    ClausolaIscrizione(
                        titolo='Autorizzazione Uscite a Piedi nel Territorio Parrocchiale',
                        testo='Autorizzo i sacerdoti, catechisti ed animatori ad accompagnare il partecipante nelle uscite e camminate a piedi nei dintorni della parrocchia.',
                        is_obbligatoria=True,
                        ordine=2
                    ),
                    ClausolaIscrizione(
                        titolo='Consenso Riprese Foto e Video per la Comunità',
                        testo='Autorizzo la pubblicazione di fotografie o riprese di gruppo delle attività comunitarie sulla bacheca dell\'oratorio e sul giornalino parrocchiale ad esclusivo uso della comunità.',
                        is_obbligatoria=False,
                        ordine=3
                    ),
                    ClausolaIscrizione(
                        titolo='Regolamento e Patto Educativo di Corresponsabilità',
                        testo='Mi impegno al rispetto degli orari, delle strutture parrocchiali e dello spirito educativo comunitario che anima le attività parrocchiali.',
                        is_obbligatoria=True,
                        ordine=4
                    )
                ]
                db.session.add_all(clausole)

            # 4. Campi personalizzati utente/account
            if CampoPersonalizzato.query.count() == 0:
                campi = [
                    CampoPersonalizzato(nome='Professione', chiave='professione', tipo='testo', obbligatorio=False, ordine=1),
                    CampoPersonalizzato(nome='Parrocchia di Provenienza', chiave='parrocchia_provenienza', tipo='testo', obbligatorio=False, ordine=2),
                    CampoPersonalizzato(nome='Disponibilità come Volontario/a', chiave='disponibilita_volontario', tipo='checkbox', obbligatorio=False, ordine=3),
                ]
                db.session.add_all(campi)

            # 5. Celebrazioni parrocchiali
            if Celebrazione.query.count() == 0:
                default_celebrazioni = [
                    # MESSE
                    Celebrazione(sezione='messe', titolo='Santa Messa Feriale', giorno='Lunedì - Venerdì', orario='ore 18:00', descrizione='Santa Messa serale comunitaria feriale', ordine=1),
                    Celebrazione(sezione='messe', titolo='Santa Messa Prefestiva', giorno='Sabato e Prefestivi', orario='ore 18:00', descrizione='Celebrazione vespertina prefestiva', ordine=2),
                    Celebrazione(sezione='messe', titolo='Santa Messa del Mattino', giorno='Domenica e Festivi', orario='ore 09:00', descrizione='Prima celebrazione festiva della domenica', ordine=3),
                    Celebrazione(sezione='messe', titolo='Santa Messa delle Famiglie', giorno='Domenica e Festivi', orario='ore 11:00', descrizione='Con animazione ragazzi, fanciulli del catechismo e cori', ordine=4),
                    Celebrazione(sezione='messe', titolo='Santa Messa della Sera', giorno='Domenica e Festivi', orario='ore 18:00', descrizione='Celebrazione vespertina domenicale', ordine=5),
                    # LITURGIA
                    Celebrazione(sezione='liturgia', titolo='Adorazione Eucaristica', giorno='Ogni Giovedì', orario='ore 17:00 - 18:00', descrizione='Adorazione silenziosa e preghiera comunitaria guidata', ordine=1),
                    Celebrazione(sezione='liturgia', titolo='Confessioni & Sacramento del Perdono', giorno='Sabato pomeriggio o su richiesta', orario='ore 16:30 - 18:00', descrizione='Disponibilità dei sacerdoti per le confessioni', ordine=2),
                    Celebrazione(sezione='liturgia', titolo='Santo Rosario Comunitario', giorno='Lunedì - Sabato', orario='ore 17:30', descrizione='Preghiera mariana comunitaria prima della Messa serale', ordine=3),
                    Celebrazione(sezione='liturgia', titolo='Lodi Mattutine', giorno='Giorni Feriali', orario='ore 08:30', descrizione='Preghiera della liturgia delle ore del mattino', ordine=4),
                    # AVVENIMENTI
                    Celebrazione(sezione='avvenimenti', titolo='Festa Patronale del Sacro Cuore di Gesù', giorno='Mese di Giugno', orario='Vedi avvisi dedicati', descrizione='Solenne concelebrazione e festa comunitaria parrocchiale', ordine=1),
                    Celebrazione(sezione='avvenimenti', titolo='Battesimi Comunitari', giorno='Seconda Domenica del mese', orario='ore 15:30', descrizione='Celebrazione del sacramento del Battesimo per i nuovi nati', ordine=2),
                    Celebrazione(sezione='avvenimenti', titolo='Prime Comunioni e Sante Cresime', giorno='Maggio e Ottobre', orario='Domenica ore 10:30', descrizione='Celebrazione dei sacramenti per i fanciulli della catechesi', ordine=3)
                ]
                db.session.add_all(default_celebrazioni)

            imp.init_defaults_completed = True

        # Calendari Comunitari Google (se non presenti)
        if CalendarioComunita.query.count() == 0:
            default_cal = [
                CalendarioComunita(
                    titolo='Eventi & Feste Parrocchiali',
                    descrizione='Calendario generale delle celebrazioni comunitarie, feste patronali ed eventi parrocchiali.',
                    google_calendar_url='https://calendar.google.com/calendar/u/0/r',
                    colore='#8B1E1E',
                    icona='⛪',
                    categoria='parrocchia',
                    is_pubblico=True,
                    ordine=1
                ),
                CalendarioComunita(
                    titolo='Catechismo & Iniziazione Cristiana',
                    descrizione='Date degli incontri di catechismo, ritiri spirituali e messe dei fanciulli.',
                    google_calendar_url='https://calendar.google.com/calendar/u/0/r',
                    colore='#0284c7',
                    icona='📖',
                    categoria='catechismo',
                    is_pubblico=True,
                    ordine=2
                ),
                CalendarioComunita(
                    titolo='Oratorio & Gruppi Giovani',
                    descrizione='Attività pomeridiane, tornei, Estate Ragazzi e uscite del gruppo oratorio.',
                    google_calendar_url='https://calendar.google.com/calendar/u/0/r',
                    colore='#16a34a',
                    icona='🏓',
                    categoria='oratorio',
                    is_pubblico=True,
                    ordine=3
                )
            ]
            db.session.add_all(default_cal)

        # Gruppi Oratorio di default (Estivo e Invernale)
        gruppi_oratorio_count = GruppoOratorio.query.count()
        if gruppi_oratorio_count == 0:
            g_estivo = GruppoOratorio(
                nome='Estate Ragazzi 2026/2027',
                anno_pastorale='2026/2027',
                tipo_oratorio='estivo',
                giorni_orari='Lunedì - Venerdì 08:30 - 17:00',
                aula='Campi sportivi e cortile oratorio',
                animatore_referente_nome='Equipe Animatori Oratorio',
                stato='pubblico'
            )
            g_invernale = GruppoOratorio(
                nome='Oratorio Invernale - Sabato Insieme',
                anno_pastorale='2026/2027',
                tipo_oratorio='invernale',
                giorni_orari='Sabato 15:00 - 18:30',
                aula='Salone don Bosco e campetti',
                animatore_referente_nome='Animatori Sabato Oratorio',
                stato='pubblico'
            )
            db.session.add_all([g_estivo, g_invernale])
        else:
            # Se tutti i gruppi oratorio esistenti risultano chiusi, apri quelli disponibili
            aperti = GruppoOratorio.query.filter(GruppoOratorio.stato != 'chiuso').count()
            if aperti == 0:
                for g in GruppoOratorio.query.all():
                    g.stato = 'pubblico'

        # Account di sistema garantiti in memoria e database
        default_accounts = [
            ('admin@sacrocuoreasti.com', 'Admin123', 'admin', '["admin", "parroco", "segreteria", "catechista", "oratorio"]'),
            ('oratorio@sacrocuoreasti.com', 'orat123', 'oratorio', '["oratorio"]'),
            ('catechismo@sacrocuoreasti.com', 'cate123', 'catechista', '["catechista"]')
        ]
        for acc_email, acc_pw, acc_role, acc_extra in default_accounts:
            user = Utente.query.filter_by(email=acc_email).first()
            if not user:
                user = Utente(
                    email=acc_email,
                    ruolo=acc_role,
                    privilegi_extra=acc_extra,
                    is_attivo=True
                )
                user.set_password(acc_pw)
                db.session.add(user)
            else:
                user.ruolo = acc_role
                user.privilegi_extra = acc_extra
                user.is_attivo = True
                if not user.check_password(acc_pw):
                    user.set_password(acc_pw)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print('Nota su init_default_configurazioni:', e)

