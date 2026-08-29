import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai

# ============================================================
# CONFIGURAZIONE
# ============================================================

URL = "https://www.invitalia.it/wizard-risultati-incentivi"
SHEET_ID = "1uL7mE-0hmDygO9ffBR3Rb0eDq5xG4VBgwMYNVSNcFoE"
FOGLIO_BANDI = "BANDI"
FOGLIO_PROFILI = "PROFILI"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; BandiRadar/1.0)"
}

# Pausa tra una chiamata a Gemini e l'altra, per rispettare i limiti gratuiti
PAUSA_SECONDI_GEMINI = 5

# ============================================================
# CONNESSIONE A GOOGLE SHEETS
# ============================================================

def connetti_client():
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(creds_json)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def leggi_link_esistenti(sheet):
    """Legge la colonna D (Link ufficiale) per evitare duplicati."""
    valori = sheet.col_values(4)  # colonna D
    return set(valori[1:])  # salta l'intestazione


def leggi_profilo_sportee(client):
    """Legge il foglio PROFILI, colonna B (Sportee), e lo trasforma in testo."""
    foglio_profili = client.open_by_key(SHEET_ID).worksheet(FOGLIO_PROFILI)
    valori = foglio_profili.get_all_values()

    righe_profilo = []
    for riga in valori[1:]:  # salta l'intestazione
        if len(riga) < 2:
            continue
        campo = riga[0].strip()
        valore_sportee = riga[1].strip() if len(riga) > 1 else ""
        if campo and valore_sportee:
            righe_profilo.append(f"{campo}: {valore_sportee}")

    return "\n".join(righe_profilo)


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
# ANALISI CON GEMINI
# ============================================================

def configura_gemini():
    api_key = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


def costruisci_prompt(profilo_sportee, nome_bando, testo_bando):
    return f"""Sei un assistente che valuta se un bando/incentivo pubblico è potenzialmente interessante per un'azienda specifica.

PROFILO AZIENDA (Sportee):
{profilo_sportee}

BANDO DA VALUTARE:
Titolo: {nome_bando}
Testo/descrizione disponibile: {testo_bando}

ISTRUZIONI:
- Confronta le informazioni del bando con il profilo dell'azienda.
- Se il testo del bando non contiene abbastanza informazioni per decidere con certezza, usa lo stato "DA VERIFICARE".
- Non inventare requisiti che non sono scritti nel testo.
- Sii sintetico ma specifico nella motivazione (massimo 3-4 frasi).

Rispondi SOLO in questo formato esatto, senza altro testo prima o dopo:

STATO: [uno tra: INTERESSANTE, DA VERIFICARE, NON PERTINENTE]
MOTIVAZIONE: [la tua spiegazione sintetica]
"""


def analizza_bando(model, profilo_sportee, nome_bando, testo_bando):
    prompt = costruisci_prompt(profilo_sportee, nome_bando, testo_bando)

    try:
        response = model.generate_content(prompt)
        testo_risposta = response.text.strip()

        stato = "DA VERIFICARE"
        motivazione = testo_risposta  # fallback: tutto il testo se non riusciamo a parsare

        for riga in testo_risposta.split("\n"):
            riga = riga.strip()
            if riga.upper().startswith("STATO:"):
                stato = riga.split(":", 1)[1].strip()
            elif riga.upper().startswith("MOTIVAZIONE:"):
                motivazione = riga.split(":", 1)[1].strip()

        emoji = {
            "INTERESSANTE": "🟢 INTERESSANTE",
            "DA VERIFICARE": "🟡 DA VERIFICARE",
            "NON PERTINENTE": "🔴 NON PERTINENTE",
        }
        stato_finale = emoji.get(stato.upper(), f"🟡 DA VERIFICARE ({stato})")

        return stato_finale, motivazione

    except Exception as e:
        return "🟡 DA VERIFICARE", f"Errore durante l'analisi AI: {type(e).__name__}"


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
        client = connetti_client()
        sheet_bandi = client.open_by_key(SHEET_ID).worksheet(FOGLIO_BANDI)
        print("Connessione a Google Sheets riuscita.")
    except Exception as e:
        print("ERRORE nella connessione a Google Sheets:")
        print(type(e).__name__, e)
        return

    try:
        profilo_sportee = leggi_profilo_sportee(client)
        print("Profilo Sportee caricato:")
        print(profilo_sportee)
        print()
    except Exception as e:
        print("ERRORE nella lettura del profilo Sportee:")
        print(type(e).__name__, e)
        return

    try:
        model = configura_gemini()
        print("Gemini configurato correttamente.")
    except Exception as e:
        print("ERRORE nella configurazione di Gemini:")
        print(type(e).__name__, e)
        return

    try:
        link_esistenti = leggi_link_esistenti(sheet_bandi)
        print(f"Link già presenti nel foglio: {len(link_esistenti)}")
    except Exception as e:
        print("ERRORE nella lettura del foglio BANDI:")
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
    for i, r in enumerate(nuove, start=1):
        print(f"[{i}/{len(nuove)}] Analisi: {r['nome']}")

        stato, motivazione = analizza_bando(model, profilo_sportee, r["nome"], r["testo"])
        print(f"  -> {stato}")

        riga = [
            "",                                          # A: ID
            r["nome"],                                    # B: Titolo
            "Invitalia",                                   # C: Ente
            r["url"],                                       # D: Link ufficiale
            "",                                             # E: Data pubblicazione
            "",                                             # F: Scadenza
            r["testo"][:500],                                # G: Sintesi requisiti
            stato,                                            # H: Stato Sportee
            motivazione,                                       # I: Motivazione Sportee
            "",                                              # J: Stato Futura Impresa
            "",                                              # K: Motivazione Futura Impresa
            datetime.now().strftime("%Y-%m-%d %H:%M"),      # L: Data ultima verifica
            "Invitalia (scraping automatico)",              # M: Fonte
            "",                                              # N: Note
        ]
        righe_da_scrivere.append(riga)

        time.sleep(PAUSA_SECONDI_GEMINI)

    if righe_da_scrivere:
        sheet_bandi.append_rows(righe_da_scrivere)
        print()
        print(f"Aggiunte {len(righe_da_scrivere)} righe con analisi.")
    else:
        print("Nessuna nuova opportunità da aggiungere.")

    print()
    print("Completato.")


if __name__ == "__main__":
    main()
