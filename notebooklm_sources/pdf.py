import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
from pdf2image import convert_from_path
import gc

COURSES_DIR = "courses"

def download_pdfs_from_pages(pages: set[str], subdir: str = "", image: bool = True):
    out = Path(COURSES_DIR) / subdir / "pdf"
    out.mkdir(parents=True, exist_ok=True)

    existing = {p.name for p in out.iterdir() if p.suffix.lower() == ".pdf"}

    seen = set()
    skipped = 0
    for page in sorted(pages):
        try:
            html = requests.get(page, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).text
        except requests.exceptions.Timeout:
            print(f"Timed out fetching page: {page}")
            continue
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.select("a[href$='.pdf']"):
            pdf_url = urljoin(page, a["href"])

            if pdf_url in seen:
                continue

            seen.add(pdf_url)
            name = pdf_url.split("/")[-1]

            if name in existing:
                skipped += 1
            else:
                try:
                    resp = requests.get(pdf_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                except requests.exceptions.Timeout:
                    print(f"  Timed out: {pdf_url}")
                    continue
                if resp.status_code != 200:
                    print(f"  Skipping (HTTP {resp.status_code}): {pdf_url}")
                    continue
                if not resp.content.startswith(b"%PDF"):
                    print(f"  Skipping (not a PDF): {pdf_url}")
                    continue
                print(f"Downloading {pdf_url}")
                data = resp.content
                (out / name).write_bytes(data)
                existing.add(name)

    if skipped:
        print(f"Skipped {skipped} already downloaded file(s)")

    if image:
        convert_image_pdfs(out, out / "image")


def convert_image_pdfs(input_dir: str | Path, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    already_converted = {p.name for p in output_dir.iterdir()} if output_dir.exists() else set()
    skipped = 0

    for pdf_path in Path(input_dir).iterdir():
        if pdf_path.suffix.lower() != ".pdf":
            continue

        if pdf_path.name in already_converted:
            skipped += 1
            continue

        print(f"Converting {pdf_path}")

        try:
            pages = convert_from_path(
                pdf_path,
                dpi=150,
                fmt="jpeg",
                thread_count=1,
            )

            pages = [p.convert("RGB") for p in pages]

            pages[0].save(
                output_dir / pdf_path.name,
                save_all=True,
                append_images=pages[1:],
                quality=70,
                subsampling=2,
                optimize=True,
            )

        except Exception as e:
            print(f"FAILED: {pdf_path} → {e}")

        finally:
            gc.collect()
            if "pages" in locals():
                del pages

    if skipped:
        print(f"Skipped {skipped} already converted file(s)")
