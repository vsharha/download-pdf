import argparse
from pathlib import Path

from notebooklm_sources.mapping import CourseConfig, SourcesConfig, load_mapping
from notebooklm_sources.pdf_page import collect_links, collect_indexed_pages
from notebooklm_sources.pdf import download_pdfs_from_pages
from notebooklm_sources.upload_sources import upload_sources


def resolve_pages(sources: SourcesConfig) -> set[str]:
    visited = {str(sources.url)}
    pages = set()
    for pattern_path in sources.patterns:
        steps = pattern_path.split("/")
        current = {str(sources.url)}
        for i, step in enumerate(steps):
            is_last = i == len(steps) - 1
            text_patterns = sources.link_text_patterns if is_last else None
            next_level = set()
            for page in current:
                if "{n}" in step:
                    next_level |= collect_indexed_pages(page, step)
                else:
                    next_level |= collect_links(page, step, text_patterns, visited)
            next_level -= visited
            visited |= next_level
            current = next_level
        pages |= current
    pages |= {str(page) for page in sources.extra_pages}
    return pages


def process_course(course_name: str, config: CourseConfig, *, no_upload: bool, dry_run: bool):
    print(f"\n{'=' * 40}")
    print(f"Processing: {course_name}")
    print(f"{'=' * 40}")

    pages = resolve_pages(config.sources)
    print(f"Found {len(pages)} page(s)")

    if dry_run:
        for page in sorted(pages):
            print(f"  {page}")
        return

    download_pdfs_from_pages(pages, subdir=course_name)

    if no_upload:
        return

    notebook_id = config.notebook_id
    if not notebook_id:
        print("No notebook ID configured; nothing was uploaded.")
        return

    image_dir = Path("courses") / course_name / "pdf" / "image"
    if not image_dir.exists():
        print(f"No image PDFs found in {image_dir}")
        return

    image_pdfs = sorted(p for p in image_dir.iterdir() if p.suffix.lower() == ".pdf")
    if not image_pdfs:
        print(f"No image PDFs found in {image_dir}")
        return

    print(f"Found {len(image_pdfs)} image PDF(s) to upload")
    upload_sources(notebook_id, image_pdfs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Download sources but skip NotebookLM upload")
    parser.add_argument("--dry-run", action="store_true", help="Resolve sources and print them without downloading")
    args = parser.parse_args()

    for course_name, config in load_mapping().items():
        process_course(course_name, config, no_upload=args.no_upload, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
