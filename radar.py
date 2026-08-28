import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://www.invitalia.it/cosa-facciamo/rafforziamo-le-imprese/incentivi-e-strumenti"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; BandiRadar/1.0)"
}

print("=" * 50)
print("BANDI RADAR")
print("=" * 50)
print(f"Controllo fonte: Invitalia")
print(f"Data: {datetime.now()}")
print()

try:
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print("Connessione riuscita.")
    print()
    print("Titoli/opportunità individuate:")
    print("-" * 50)

    links = soup.find_all("a")

    trovati = 0

    for link in links:
        testo = link.get_text(" ", strip=True)
        href = link.get("href")

        if testo and href and len(testo) > 10:
            if "incentiv" in testo.lower() or "finanzi" in testo.lower() or "imprese" in testo.lower():
                if href.startswith("/"):
                    href = "https://www.invitalia.it" + href

                print(f"- {testo}")
                print(f"  {href}")
                print()

                trovati += 1

    print("-" * 50)
    print(f"Totale elementi individuati: {trovati}")

except Exception as e:
    print("ERRORE:")
    print(e)
