import argparse
from pathlib import Path

from notebooklm_sources.mapping import CourseConfig, SourcesConfig, load_mapping
from notebooklm_sources.pdf_page import collect_links, collect_indexed_pages
from notebooklm_sources.pdf import download_pdfs_from_pages, convert_to_image_bytes
from notebooklm_sources.upload_sources import upload_sources
from notebooklm_sources.echo360 import download_transcripts


def resolve_pages(sources: SourcesConfig) -> set[str]:
    base = str(sources.url) if sources.url else None
    visited = {base} if base else set()
    current = {base} if base else set()

    for step in sources.traverse:
        next_level = set()
        for page in current:
            if "{n}" in step:
                next_level |= collect_indexed_pages(page, step)
            else:
                next_level |= collect_links(page, [step], visited=visited)
        next_level -= visited
        visited |= next_level
        current = next_level

    pages = set()
    for page in current:
        pages |= collect_links(
            page,
            sources.collect,
            include_text=sources.include_text,
            exclude_text=sources.exclude_text,
            visited=visited,
        )

    pages |= {str(page) for page in sources.pages}
    return pages


def process_course(course_name: str, config: CourseConfig, *, no_upload: bool, dry_run: bool, replace: bool):
    print(f"\n{'=' * 40}")
    print(f"Processing: {course_name}")
    print(f"{'=' * 40}")

    pages = resolve_pages(config.sources)
    print(f"Found {len(pages)} page(s)")

    if dry_run:
        for page in sorted(pages):
            print(f"  {page}")
        return

    download_pdfs_from_pages(pages, subdir=course_name, exclude_files=config.exclude_files)

    if config.echo360:
        download_transcripts(config.echo360.section_id, course_name, Path("courses"))

    if no_upload:
        return

    notebook_id = config.notebook_id
    if not notebook_id:
        print("No notebook ID configured; nothing was uploaded.")
        return

    pdf_dir = Path("courses") / course_name / "pdf"
    transcript_dir = Path("courses") / course_name / "transcripts"

    pdfs = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []
    transcripts = sorted(transcript_dir.glob("*.txt")) if transcript_dir.exists() else []

    if not pdfs and not transcripts:
        print("No files to upload.")
        return

    if pdfs:
        converter = None if config.upload_original else lambda p: convert_to_image_bytes(p, config.pdf_quality)
        print(f"Found {len(pdfs)} PDF(s) to upload")
        upload_sources(notebook_id, pdfs, converter=converter, replace=replace)

    if transcripts:
        print(f"Found {len(transcripts)} transcript(s) to upload")
        upload_sources(notebook_id, transcripts, replace=replace)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Download sources but skip NotebookLM upload")
    parser.add_argument("--dry-run", action="store_true", help="Resolve sources and print them without downloading")
    parser.add_argument("--replace", action="store_true", help="Re-upload files that already exist in NotebookLM, replacing the old versions")
    args = parser.parse_args()

    if args.replace and args.no_upload:
        parser.error("--replace has no effect with --no-upload")
    if args.replace and args.dry_run:
        parser.error("--replace has no effect with --dry-run")

    for course_name, config in load_mapping().items():
        process_course(course_name, config, no_upload=args.no_upload, dry_run=args.dry_run, replace=args.replace)


if __name__ == "__main__":
    main()
