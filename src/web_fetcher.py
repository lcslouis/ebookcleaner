import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from src.parsers.registry import get_parser
from src.parsers.scribblehub_parser import ScribbleHubParser

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class WebFetcher:
    def __init__(self, delay: float = 1.5, content_selector: str = ""):
        self.delay = delay
        self.content_selector = content_selector
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request_time = 0.0

    # ------------------------------------------------------------------ public

    def detect_site(self, url: str) -> str:
        return get_parser(url, self.content_selector).site_name

    def fetch_toc(self, url: str) -> dict:
        """
        Fetch the table of contents page and return:
          {title, author, description, cover_url, tags, chapters: [{url, title}]}
        Resolves ScribbleHub AJAX and AO3 navigate pages automatically.
        """
        html = self._get(url)
        soup = BeautifulSoup(html, "lxml")
        parser = get_parser(url, self.content_selector)
        info = parser.get_book_info(url, soup)

        # Resolve special placeholder chapters
        info["chapters"] = self._resolve_special_chapters(info["chapters"], parser)

        return info

    def fetch_chapter(self, url: str) -> str:
        """Fetch and return plain text content of a single chapter page."""
        html = self._get(url)
        soup = BeautifulSoup(html, "lxml")
        parser = get_parser(url, self.content_selector)
        return parser.get_chapter_content(url, soup)

    def download_image(self, url: str) -> tuple:
        """
        Download an image and return (bytes, mime_type).
        Returns (None, None) on failure.
        """
        if not url:
            return None, None
        try:
            self._throttle()
            resp = self.session.get(url, timeout=20, stream=True)
            resp.raise_for_status()
            self._last_request_time = time.time()
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            return resp.content, mime
        except Exception:
            return None, None

    # ------------------------------------------------------------------ private

    def _resolve_special_chapters(self, chapters: list, parser) -> list:
        """Handle placeholder markers inserted by site-specific parsers."""
        if not chapters:
            return chapters

        resolved = []
        for ch in chapters:
            url = ch.get("url", "")

            # ScribbleHub: fetch via AJAX
            if url.startswith("__scribblehub_toc__") and isinstance(parser, ScribbleHubParser):
                post_id = url.replace("__scribblehub_toc__", "")
                try:
                    ajax_chapters = parser.fetch_chapter_list(post_id, self.session)
                    resolved.extend(ajax_chapters)
                except Exception:
                    pass
                continue

            # AO3: fetch navigate page
            if url.startswith("__navigate__"):
                nav_url = url.replace("__navigate__", "")
                try:
                    nav_chapters = self._fetch_ao3_navigate(nav_url)
                    resolved.extend(nav_chapters)
                except Exception:
                    pass
                continue

            resolved.append(ch)

        return resolved

    def _fetch_ao3_navigate(self, navigate_url: str) -> list:
        html = self._get(navigate_url)
        soup = BeautifulSoup(html, "lxml")
        chapters = []
        for a in soup.select("ol.chapter.index.group li a"):
            href = a.get("href", "")
            if href:
                full = urljoin(navigate_url, href)
                if "view_adult" not in full:
                    full += ("&" if "?" in full else "?") + "view_adult=true"
                chapters.append({"url": full, "title": a.get_text(strip=True)})
        return chapters

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _get(self, url: str) -> str:
        self._throttle()
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        self._last_request_time = time.time()
        # Prefer UTF-8 regardless of Content-Type header
        try:
            return resp.content.decode("utf-8")
        except UnicodeDecodeError:
            return resp.text
