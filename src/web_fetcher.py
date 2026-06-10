import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from src.parsers.registry import get_parser, get_parser_by_name
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
    def __init__(self, delay: float = 1.5, content_selector: str = "",
                 cookies: list = None, parser_override: str = ""):
        self.delay = delay
        self.content_selector = content_selector
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request_time = 0.0
        self._parser_override = parser_override
        if cookies:
            for c in cookies:
                self.session.cookies.set(
                    c.get("name", ""),
                    c.get("value", ""),
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )

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
        parser = (
            get_parser_by_name(self._parser_override) or get_parser(url, self.content_selector, soup)
            if self._parser_override
            else get_parser(url, self.content_selector, soup)
        )
        info = parser.get_book_info(url, soup)

        # Resolve special placeholder chapters
        info["chapters"] = self._resolve_special_chapters(info["chapters"], parser)
        info["chapters"] = self._normalize_chapter_titles(info["chapters"])
        return info

    def fetch_chapter(self, url: str) -> str:
        """Fetch and return plain text content of a single chapter page."""
        html = self._get(url)
        soup = BeautifulSoup(html, "lxml")
        parser = (
            get_parser_by_name(self._parser_override) or get_parser(url, self.content_selector, soup)
            if self._parser_override
            else get_parser(url, self.content_selector, soup)
        )
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

    def _normalize_chapter_titles(self, chapters: list) -> list:
        """
        Give every chapter a meaningful title.
        Empty titles and bare 'Chapter' placeholders become 'Chapter N'.
        """
        result = []
        for i, ch in enumerate(chapters, start=1):
            title = (ch.get("title") or "").strip()
            if not title or title.lower() == "chapter":
                ch = dict(ch)   # don't mutate the original
                ch["title"] = f"Chapter {i}"
            result.append(ch)
        return result

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
            html = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            html = resp.text
        self._check_bot_challenge(html, url)
        return html

    @staticmethod
    def _check_bot_challenge(html: str, url: str) -> None:
        """Raise a descriptive error if the response is a bot-protection challenge."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # Imunify360 challenge ("One moment, please..." title + wsidchk cookie logic)
        if "wsidchk" in html and "One moment" in html:
            raise ValueError(
                f"Bot protection (Imunify360) is blocking automated access to {domain}.\n\n"
                f"To fix this:\n"
                f"1. Open Site Logins in the toolbar\n"
                f"2. Enter {url[:60]} and log in using the browser\n"
                f"3. Click '✓ Done — Save Login' to capture the session cookie\n"
                f"4. Try fetching again — the saved cookie will bypass the challenge."
            )
        # Cloudflare JS challenge / Under Attack Mode
        if "cf-browser-verification" in html or (
            "challenge-platform" in html and "cloudflare" in html.lower()
        ):
            raise ValueError(
                f"Cloudflare bot protection is blocking automated access to {domain}.\n\n"
                f"To fix this:\n"
                f"1. Open Site Logins and save your session cookies for {domain}\n"
                f"2. Try fetching again."
            )
