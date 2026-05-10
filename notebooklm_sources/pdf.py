import fnmatch
import gc
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
from pdf2image import convert_from_path

COURSES_DIR = "courses"


def download_pdfs_from_pages(pages: set[str], subdir: str = "", exclude_files: list[str] | None = None):
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

            if exclude_files and any(fnmatch.fnmatch(name, pat) for pat in exclude_files):
                continue

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
                (out / name).write_bytes(resp.content)
                existing.add(name)

    if skipped:
        print(f"Skipped {skipped} already downloaded file(s)")


def convert_to_image_bytes(pdf_path: Path) -> bytes:
    pages = convert_from_path(pdf_path, dpi=200, fmt="jpeg", thread_count=1)
    try:
        pages = [p.convert("RGB") for p in pages]
        buf = io.BytesIO()
        pages[0].save(
            buf,
            format="PDF",
            save_all=True,
            append_images=pages[1:],
            quality=85,
            subsampling=0,
        )
        return buf.getvalue()
    finally:
        del pages
        gc.collect()
