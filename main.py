import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

def download_pdfs(url: str) -> None:
    out = Path("pdfs")
    out.mkdir(exist_ok=True)

    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    for i, a in enumerate(soup.select("a[href$='.pdf']")):
        pdf_url = urljoin(url, a["href"])
        name = f"{i+1}_{pdf_url.split('/')[-1]}"
        data = requests.get(pdf_url).content
        (out / name).write_bytes(data)

def main():
    url: str = str(input("Enter url > "))

    download_pdfs(url)

if __name__ == "__main__":
    main()