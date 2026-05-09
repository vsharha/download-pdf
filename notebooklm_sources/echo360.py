from __future__ import annotations

import http.cookiejar
import re
from pathlib import Path

import requests

COOKIES_PATH = Path(__file__).resolve().parents[1] / "cookies.txt"
ECHO_HOST = "https://echo360.org.uk"


def build_session(cookies_path: Path = COOKIES_PATH) -> requests.Session:
    jar = http.cookiejar.MozillaCookieJar()
    jar.load(str(cookies_path), ignore_discard=True, ignore_expires=True)
    session = requests.Session()
    for cookie in jar:
        session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })
    return session


def get_lessons(session: requests.Session, section_id: str) -> list[dict]:
    r = session.get(f"{ECHO_HOST}/section/{section_id}/syllabus")
    r.raise_for_status()
    return r.json()["data"]


def get_transcript(session: requests.Session, lesson_id: str, media_id: str) -> list[dict] | None:
    url = f"{ECHO_HOST}/api/ui/echoplayer/lessons/{lesson_id}/medias/{media_id}/transcript"
    r = session.get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    cues = r.json()["data"]["contentJSON"]["cues"]
    return cues if isinstance(cues, list) else None


def safe_filename(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def cues_to_text(cues: list[dict]) -> str:
    return "\n".join(cue["content"] for cue in cues)


def download_transcripts(section_id: str, course_name: str, out_root: Path) -> None:
    session = build_session()
    out_dir = out_root / course_name / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    lessons = get_lessons(session, section_id)
    skipped = 0
    for item in lessons:
        if item.get("type") != "SyllabusLessonType":
            continue

        lesson_data = item["lesson"]["lesson"]
        lesson_id = lesson_data["id"]
        name = lesson_data.get("displayName") or lesson_data.get("name", lesson_id)
        start = lesson_data.get("timing", {}).get("start", "")[:10]

        medias = item["lesson"].get("medias", [])
        if not medias or not item["lesson"].get("hasContent"):
            continue

        media_id = medias[0]["id"]
        filename = out_dir / f"{start}_{safe_filename(name)}.txt"

        if filename.exists():
            skipped += 1
            continue

        cues = get_transcript(session, lesson_id, media_id)
        if cues is None:
            print(f"  No transcript: {name}")
            continue

        filename.write_text(cues_to_text(cues), encoding="utf-8")
        print(f"  Downloaded: {filename.name}")

    if skipped:
        print(f"Skipped {skipped} already downloaded transcript(s)")
