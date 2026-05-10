import time
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import httpx

from notebooklm_tools.core.auth import get_auth_manager
from notebooklm_tools.core.client import NotebookLMClient


def notebook_id_from_ref(notebook_ref: str) -> str:
    parsed = urlparse(notebook_ref)
    if not parsed.scheme:
        return notebook_ref

    path_parts = [part for part in parsed.path.split("/") if part]
    try:
        notebook_index = path_parts.index("notebook")
    except ValueError as exc:
        raise ValueError(f"Notebook URL does not contain a notebook id: {notebook_ref}") from exc

    try:
        return path_parts[notebook_index + 1]
    except IndexError as exc:
        raise ValueError(f"Notebook URL does not contain a notebook id: {notebook_ref}") from exc


def get_client(profile: str | None = None) -> NotebookLMClient:
    manager = get_auth_manager(profile)
    if not manager.profile_exists():
        profile_name = manager.profile_name
        raise RuntimeError(
            f"NotebookLM auth profile '{profile_name}' was not found. "
            "Run `uv run nlm login` before uploading sources."
        )

    auth_profile = manager.load_profile()
    return NotebookLMClient(
        cookies=auth_profile.cookies,
        csrf_token=auth_profile.csrf_token or "",
        session_id=auth_profile.session_id or "",
        build_label=auth_profile.build_label or "",
    )


def list_uploaded(client: NotebookLMClient, notebook_id: str) -> dict[str, list[str]]:
    sources_by_title: dict[str, list[str]] = {}

    for source in client.get_notebook_sources_with_types(notebook_id):
        title = source.get("title")
        source_id = source.get("id")
        if isinstance(title, str) and isinstance(source_id, str):
            sources_by_title.setdefault(title, []).append(source_id)

    return sources_by_title


def upload_sources(
    notebook_ref: str,
    files: list[Path | str],
    *,
    profile: str | None = None,
    wait: bool = True,
    wait_timeout: float = 600.0,
    replace: bool = False,
    converter: Callable[[Path], bytes] | None = None,
) -> None:
    if not files:
        return

    notebook_id = notebook_id_from_ref(notebook_ref)
    files = [Path(file) for file in files]

    with get_client(profile) as client:
        uploaded_source_ids_by_title = list_uploaded(client, notebook_id)

        if replace:
            files_to_upload = files
        else:
            files_to_upload = [
                file for file in files
                if file.name not in uploaded_source_ids_by_title
            ]

        skipped = len(files) - len(files_to_upload)
        if skipped and not replace:
            print(f"Skipping {skipped} already uploaded file(s)")

        for file in files_to_upload:
            print(f"Uploading {file.name}")
            old_source_ids = uploaded_source_ids_by_title.get(file.name, [])
            if converter is not None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    path = Path(tmpdir) / file.name
                    path.write_bytes(converter(file))
                    client.add_file(notebook_id, path, wait=wait or replace, wait_timeout=wait_timeout)
            else:
                client.add_file(notebook_id, file, wait=wait or replace, wait_timeout=wait_timeout)
            if replace and old_source_ids:
                print(f"Deleting {len(old_source_ids)} replaced source(s) for {file.name}")
                for attempt in range(1, 4):
                    try:
                        client.delete_sources(old_source_ids)
                        break
                    except httpx.ReadTimeout:
                        if attempt == 3:
                            raise
                        print(f"Delete timed out, retrying ({attempt}/3)...")
                        time.sleep(2 ** attempt)

    if files_to_upload:
        print(f"Uploaded {len(files_to_upload)} file(s)")
