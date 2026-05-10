import fnmatch
import itertools

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def path_matches(href: str, pattern: str) -> bool:
    n = pattern.count("/") + 1
    segments = urlparse(href).path.strip("/").split("/")
    if len(segments) < n:
        return False
    return fnmatch.fnmatchcase("/".join(segments[-n:]), pattern)


def collect_links(
    page_url: str,
    path_patterns: list[str],
    include_text: list[str] | None = None,
    exclude_text: list[str] | None = None,
    visited: set[str] | None = None,
) -> set[str]:
    html = requests.get(page_url, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")
    matches = set()

    for a in soup.select("a[href]"):
        href = urljoin(page_url, a["href"])

        if urlparse(href).netloc != urlparse(page_url).netloc:
            continue

        if visited and href in visited:
            continue

        text = a.get_text(strip=True)
        path_match = any(path_matches(href, p) for p in path_patterns)
        text_match = any(fnmatch.fnmatchcase(text, p) for p in (include_text or []))

        if not (path_match or text_match):
            continue

        if any(fnmatch.fnmatchcase(text, p) for p in (exclude_text or [])):
            continue

        matches.add(href)

    return matches


def collect_indexed_pages(base_url: str, pattern: str) -> set[str]:
    pages = set()
    for i in itertools.count(1):
        url = urljoin(base_url.rstrip("/") + "/", pattern.replace("{n}", str(i)))
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            break
        pages.add(url)
    return pages
