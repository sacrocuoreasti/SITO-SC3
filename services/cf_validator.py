import re
from datetime import date

MONTH_MAP = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'H': 6,
    'L': 7, 'M': 8, 'P': 9, 'R': 10, 'S': 11, 'T': 12
}

ODD_VALUES = {
    '0': 1, '1': 0, '2': 5, '3': 7, '4': 9, '5': 13, '6': 15, '7': 17, '8': 19, '9': 21,
    'A': 1, 'B': 0, 'C': 5, 'D': 7, 'E': 9, 'F': 13, 'G': 15, 'H': 17, 'I': 19, 'J': 21,
    'K': 2, 'L': 4, 'M': 18, 'N': 20, 'O': 11, 'P': 3, 'Q': 6, 'R': 8, 'S': 12, 'T': 14,
    'U': 16, 'V': 10, 'W': 22, 'X': 25, 'Y': 24, 'Z': 23
}

EVEN_VALUES = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7, 'I': 8, 'J': 9,
    'K': 10, 'L': 11, 'M': 12, 'N': 13, 'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19,
    'U': 20, 'V': 21, 'W': 22, 'X': 23, 'Y': 24, 'Z': 25
}

def normalizza_cf(cf: str) -> str:
    """Rimuove spazi e caratteri speciali e restituisce CF in maiuscolo."""
    if not cf:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(cf)).upper().strip()

def valida_cf(cf: str) -> bool:
    """
    Verifica se il codice fiscale ha formato corretto (16 caratteri alfanumerici)
    e carattere di controllo valido secondo algoritmo ufficiale.
    """
    cf = normalizza_cf(cf)
    if len(cf) != 16:
        return False
        
    pattern = r'^[A-Z]{6}[0-9]{2}[A-EHLMPR-T][0-9]{2}[A-Z][0-9]{3}[A-Z]$'
    if not re.match(pattern, cf):
        return False
        
    try:
        soma = 0
        for i in range(15):
            char = cf[i]
            if (i + 1) % 2 != 0:  # Posizione dispari (1-based)
                soma += ODD_VALUES.get(char, 0)
            else:  # Posizione pari (1-based)
                soma += EVEN_VALUES.get(char, 0)
                
        control_char = chr(ord('A') + (soma % 26))
        return control_char == cf[15]
    except Exception:
        return False

def estrai_dati_cf(cf: str) -> dict:
    """
    Tenta di estrarre sesso (M/F) e data di nascita dal codice fiscale.
    """
    cf = normalizza_cf(cf)
    if len(cf) < 11:
        return {}
        
    try:
        anno_2d = int(cf[6:8])
        mese_char = cf[8]
        giorno_raw = int(cf[9:11])
        
        # Sesso e giorno
        if giorno_raw > 40:
            sesso = 'F'
            giorno = giorno_raw - 40
        else:
            sesso = 'M'
            giorno = giorno_raw
            
        mese = MONTH_MAP.get(mese_char, 1)
        
        # Anno: se due cifre > anno corrente assumiamo 1900, altrimenti 2000
        current_year_2d = date.today().year % 100
        if anno_2d > current_year_2d:
            anno = 1900 + anno_2d
        else:
            anno = 2000 + anno_2d
            
        data_nascita = date(anno, mese, giorno)
        
        return {
            'sesso': sesso,
            'data_nascita': data_nascita,
            'data_nascita_iso': data_nascita.isoformat(),
            'giorno': giorno,
            'mese': mese,
            'anno': anno
        }
    except Exception:
        return {}
