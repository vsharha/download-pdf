import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
from pdf2image import convert_from_path
import gc

PDF_DIR = "pdfs"

def download_pdfs(url: str) -> None:
    out = Path(PDF_DIR)
    out.mkdir(exist_ok=True)

    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    for i, a in enumerate(soup.select("a[href$='.pdf']")):
        pdf_url = urljoin(url, a["href"])
        print(f"Downloading {pdf_url}")
        name = f"{i+1}_{pdf_url.split('/')[-1]}"
        data = requests.get(pdf_url).content
        (out / name).write_bytes(data)

def convert_image_pdfs(input_dir: str | Path, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    input_dir = Path(input_dir)

    for pdf_path in input_dir.iterdir():
        if pdf_path.suffix.lower() != ".pdf":
            continue

        print(f"Converting {pdf_path}")

        try:
            pages = convert_from_path(
                pdf_path,
                dpi=150,
                fmt="jpeg",
                thread_count=1
            )

            pages = [p.convert("RGB") for p in pages]

            output_pdf = output_dir / pdf_path.name

            pages[0].save(
                output_pdf,
                save_all=True,
                append_images=pages[1:],
                quality=70,
                subsampling=2,
                optimize=True
            )

        except Exception as e:
            print(f"FAILED: {pdf_path} → {e}")

        finally:
            # CRITICAL cleanup
            del pages
            gc.collect()

def main():
    url: str = str(input("Enter url > "))

    pdf_dir = Path(PDF_DIR)
    output_dir = pdf_dir / "image"

    download_pdfs(url)
    convert_image_pdfs(pdf_dir, output_dir)

if __name__ == "__main__":
    main()