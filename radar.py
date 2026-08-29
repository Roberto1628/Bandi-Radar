import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIGURAZIONE
# ============================================================

URL = "https://www.invitalia.it/wizard-risultati-incentivi"
SHEET_ID = "1uL7mE-0hmDygO9ffBR3Rb0eDq5xG4VBgwMYNVSNcFoE"
FOGLIO_NOME = "BANDI"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; BandiRadar/1.0)"
}

# ============================================================
# CONNESSIONE A GOOGLE SHEETS
# ============================================================

def connetti_sheet():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).worksheet(FOGLIO_NOME)
    return sheet


def leggi_link_esistenti(sheet):
    """Legge la colonna D (Link ufficiale) per evitare duplicati."""
    valori = sheet.col_values(4)  # colonna D
    return set(valori[1:])  # salta l'intestazione


# ============================================================
# SCRAPING
# ============================================================

def cerca_opportunita():
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.find_all("h3")
    risultati = []
    link_visti = set()

    for titolo in cards:
        nome = titolo.get_text(" ", strip=True)
        link = titolo.find("a")
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        url = urljoin(URL, href)

        if url in link_visti:
            continue
        link_visti.add(url)

        contenitore = titolo.parent
        testo = contenitore.get_text(" ", strip=True)

        risultati.append({
            "nome": nome,
            "url": url,
            "testo": testo
        })

    return risultati


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("BANDI RADAR")
    print("=" * 60)
    print("Fonte: Invitalia")
    print(f"Controllo: {datetime.now()}")
    print()

    try:
        sheet = connetti_sheet()
        print("Connessione a Google Sheets riuscita.")
    except Exception as e:
        print("ERRORE nella connessione a Google Sheets:")
        print(type(e).__name__, e)
        return

    try:
        link_esistenti = leggi_link_esistenti(sheet)
        print(f"Link già presenti nel foglio: {len(link_esistenti)}")
    except Exception as e:
        print("ERRORE nella lettura del foglio:")
        print(type(e).__name__, e)
        return

    try:
        risultati = cerca_opportunita()
        print(f"Opportunità trovate sulla pagina: {len(risultati)}")
    except Exception as e:
        print("ERRORE nello scraping:")
        print(type(e).__name__, e)
        return

    nuove = [r for r in risultati if r["url"] not in link_esistenti]
    print(f"Nuove opportunità da aggiungere: {len(nuove)}")
    print()

    righe_da_scrivere = []
    for r in nuove:
        riga = [
            "",                                          # A: ID (vuoto per ora)
            r["nome"],                                    # B: Titolo
            "Invitalia",                                   # C: Ente
            r["url"],                                       # D: Link ufficiale
            "",                                             # E: Data pubblicazione
            "",                                             # F: Scadenza
            r["testo"][:500],                                # G: Sintesi requisiti (grezza, max 500 char)
            "",                                              # H: Stato Sportee
            "",                                              # I: Motivazione Sportee
            "",                                              # J: Stato Futura Impresa
            "",                                              # K: Motivazione Futura Impresa
            datetime.now().strftime("%Y-%m-%d %H:%M"),      # L: Data ultima verifica
            "Invitalia (scraping automatico)",              # M: Fonte
            "",                                              # N: Note
        ]
        righe_da_scrivere.append(riga)

    if righe_da_scrivere:
        sheet.append_rows(righe_da_scrivere)
        for r in nuove:
            print(f"Aggiunto: {r['nome']}")
    else:
        print("Nessuna nuova opportunità da aggiungere.")

    print()
    print("Completato.")


if __name__ == "__main__":
    main()
