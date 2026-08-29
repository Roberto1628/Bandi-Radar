import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

URL = "https://www.invitalia.it/wizard-risultati-incentivi"

headers = {
    "User-Agent": "Mozilla/5.0 (compatible; BandiRadar/1.0)"
}

print("=" * 60)
print("BANDI RADAR")
print("=" * 60)
print("Fonte: Invitalia")
print(f"Controllo: {datetime.now()}")
print()

try:
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print("Connessione riuscita.")
    print()

    # Cerchiamo i titoli delle opportunità.
    # Nella pagina Invitalia sono presenti come titoli H3.
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

        # Evita duplicati
        if url in link_visti:
            continue

        link_visti.add(url)

        # Cerchiamo il contenitore dell'opportunità
        contenitore = titolo.parent

        testo = contenitore.get_text(" ", strip=True)

        risultati.append({
            "nome": nome,
            "url": url,
            "testo": testo
        })

    print("=" * 60)
    print(f"OPPORTUNITÀ INDIVIDUATE: {len(risultati)}")
    print("=" * 60)
    print()

    for i, risultato in enumerate(risultati, start=1):

        print(f"[{i}] {risultato['nome']}")
        print(f"URL: {risultato['url']}")
        print(f"Informazioni: {risultato['testo']}")
        print("-" * 60)

except Exception as e:
    print("ERRORE:")
    print(type(e).__name__)
    print(e)
