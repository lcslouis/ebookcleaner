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

    def fetch_toc_by_crawl(self, toc_url: str, first_chapter_url: str,
                           progress_cb=None) -> dict:
        """
        Build a chapter list by following next-chapter links starting from
        first_chapter_url.  Used when the TOC page doesn't list chapters in a
        parseable format (e.g. Imunify360-protected WordPress sites).

        Book metadata (title, author, description, cover) is fetched from
        toc_url if provided; falls back to whatever is on the first chapter page.
        progress_cb(n) is called after each chapter is discovered.
        """
        # Fetch book metadata from TOC page (best-effort)
        info = {"title": "", "author": "", "description": "", "cover_url": "", "chapters": []}
        if toc_url:
            try:
                html = self._get(toc_url)
                soup = BeautifulSoup(html, "lxml")
                parser = (get_parser_by_name(self._parser_override)
                          or get_parser(toc_url, self.content_selector, soup))
                meta = parser.get_book_info(toc_url, soup)
                for k in ("title", "author", "description", "cover_url"):
                    if meta.get(k):
                        info[k] = meta[k]
            except Exception:
                pass

        # Crawl chapter chain
        chapters = []
        visited = set()
        url = first_chapter_url
        limit = 2000

        while url and len(chapters) < limit:
            if url in visited:
                break
            visited.add(url)

            try:
                html = self._get(url)
            except Exception as e:
                if not chapters:
                    raise
                break

            soup = BeautifulSoup(html, "lxml")
            parser = (get_parser_by_name(self._parser_override)
                      or get_parser(url, self.content_selector, soup))

            # Extract chapter title from page
            title = self._extract_chapter_title(soup, len(chapters) + 1)
            chapters.append({"url": url, "title": title})
            if progress_cb:
                progress_cb(len(chapters))

            url = self._find_next_chapter_url(soup, url)

        info["chapters"] = self._normalize_chapter_titles(chapters)
        return info

    def _extract_chapter_title(self, soup, fallback_n: int) -> str:
        for sel in ("h1.entry-title", "h1.chapter-title", "h2.chapter-title",
                    ".chapter-title", "h1", "h2"):
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if text:
                    return text
        return f"Chapter {fallback_n}"

    def _find_next_chapter_url(self, soup, current_url: str):
        """Return the URL of the next chapter, or None if not found."""
        from urllib.parse import urlparse, urlunparse
        import re as _re

        # 1. <link rel="next"> in <head> (most reliable)
        for tag in soup.find_all("link"):
            rel = tag.get("rel") or []
            if isinstance(rel, str):
                rel = [rel]
            if "next" in rel and tag.get("href"):
                return urljoin(current_url, tag["href"])

        # 2. <a rel="next">
        for a in soup.find_all("a", href=True):
            rel = a.get("rel") or []
            if isinstance(rel, str):
                rel = [rel]
            if "next" in rel:
                return urljoin(current_url, a["href"])

        # 3. Containers with next-nav class/id — grab first link inside them
        next_containers = [
            ".nav-next", ".navigation-next", ".next-chapter", ".nextchap",
            ".btn-next", "#nav-next", ".chapter-nav-next",
            "[class*='next']",   # any element whose class contains "next"
        ]
        for sel in next_containers:
            try:
                el = soup.select_one(sel)
            except Exception:
                continue
            if el:
                a = el if el.name == "a" else el.find("a", href=True)
                if a and a.get("href"):
                    href = a["href"]
                    if not href.startswith("#") and not href.startswith("javascript"):
                        return urljoin(current_url, href)

        # 4. Anchor text patterns — broader matching with contains/startswith
        next_keywords = ("next chapter", "next chap", "next →", "next »",
                         "next >", "→", "»", ">>")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript"):
                continue
            text = a.get_text(strip=True).lower()
            if text in {"next", ">", ">>", "→", "»"}:
                return urljoin(current_url, href)
            if any(text.startswith(kw) or text.endswith(kw) or kw in text
                   for kw in next_keywords):
                return urljoin(current_url, href)

        # 5. Numeric URL increment fallback (e.g. chapter-7001 → chapter-7002)
        parsed = urlparse(current_url)
        path = parsed.path
        m = _re.search(r"(\d+)([^/]*)/?$", path)
        if m:
            num = int(m.group(1))
            suffix = m.group(2)
            new_path = path[:m.start()] + str(num + 1) + suffix + "/"
            candidate = urlunparse(parsed._replace(path=new_path))
            try:
                self._throttle()
                resp = self.session.head(candidate, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    return candidate
            except Exception:
                pass

        return None

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
