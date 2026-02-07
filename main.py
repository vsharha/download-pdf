import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re
from pdf2image import convert_from_path
import gc

PDF_DIR = "pdfs"


def glob_to_regex(pattern: str) -> re.Pattern:
    regex = re.escape(pattern)
    regex = regex.replace(r"\*", "[^/]+")
    return re.compile("^" + regex + "$")


def same_domain(base: str, url: str) -> bool:
    return urlparse(base).netloc == urlparse(url).netloc


def collect_links(page_url: str, path_pattern: str) -> set[str]:
    rx = glob_to_regex(path_pattern)

    html = requests.get(page_url).text
    soup = BeautifulSoup(html, "html.parser")

    matches = set()

    for a in soup.select("a[href]"):
        href = urljoin(page_url, a["href"])

        if urlparse(href).netloc != urlparse(page_url).netloc:
            continue

        path = urlparse(href).path.lstrip("/")

        # Absolute path pattern
        if path_pattern.startswith("/"):
            if rx.match("/" + path):
                matches.add(href)
        # Relative (suffix) pattern
        else:
            if rx.match(path.split("/")[-1]):
                matches.add(href)

    return matches


def download_pdfs_from_pages(pages: set[str], subdir: str = "", image: bool = True):
    out = Path(PDF_DIR) / subdir
    out.mkdir(parents=True, exist_ok=True)

    existing = {p.name for p in out.iterdir() if p.suffix.lower() == ".pdf"}

    seen = set()
    i = 1

    for page in sorted(pages):
        html = requests.get(page).text
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.select("a[href$='.pdf']"):
            pdf_url = urljoin(page, a["href"])

            if pdf_url in seen:
                continue

            seen.add(pdf_url)
            name = f"{i}_{pdf_url.split('/')[-1]}"

            if name in existing:
                print(f"Skipping (already downloaded) {name}")
            else:
                print(f"Downloading {pdf_url}")
                (out / name).write_bytes(requests.get(pdf_url).content)

            i += 1

    if image:
        convert_image_pdfs(out, out / "image")


def convert_image_pdfs(input_dir: str | Path, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    already_converted = {p.name for p in output_dir.iterdir()} if output_dir.exists() else set()

    for pdf_path in Path(input_dir).iterdir():
        if pdf_path.suffix.lower() != ".pdf":
            continue

        if pdf_path.name in already_converted:
            print(f"Skipping (already converted) {pdf_path.name}")
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
            if "pages" in locals():
                del pages
            gc.collect()


def main():
    start_url = input("Enter course page URL > ").strip()

    week_path = input(
        "Enter week path pattern (empty = use start page only) > "
    ).strip()

    lecture_path = input(
        "Enter lecture path pattern (empty = use week pages directly) > "
    ).strip()

    # Original behavior
    if not week_path:
        pages = {start_url}

    # Week pages only
    elif week_path and not lecture_path:
        pages = collect_links(start_url, week_path)

    # Week → lecture
    else:
        weeks = collect_links(start_url, week_path)
        pages = set()
        for week in weeks:
            pages |= collect_links(week, lecture_path)

    subdir = input("Enter subdirectory name (empty = none) > ").strip()

    print(f"Using {len(pages)} page(s)")
    download_pdfs_from_pages(pages, subdir=subdir)


if __name__ == "__main__":
    main()