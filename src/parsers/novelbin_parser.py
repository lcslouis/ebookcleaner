"""
NovelBin parser (novelbin.com and mirror domains).

Chapter URL pattern:  /b/{novel-slug}/{chapter-slug}
ToC URL pattern:      /b/{novel-slug}   (chapters in #tab-chapters-title tab)

The chapter list tab is populated via AJAX after page load, so the static
HTML typically has no <a> links for chapters. Strategy:
  1. Try static HTML selectors in #tab-chapters-title (sometimes present).
  2. Extract the numeric novel ID from the page, then call the AJAX archive
     endpoint: GET /ajax/chapter-archive?novelId={id}
     which returns an HTML fragment of <li><a href=...> entries.
  3. Fall back to any /b/{slug}/chapter-* links found in the page.

Chapter content lives in div#chr-content. Ads and navigation injected inside
that div are stripped before returning text.
"""
import re
import requests
from .base_parser import BaseParser

_DOMAINS = [
    "novelbin.com", "novelbin.net", "novelbin.me",
    "novelbin.org", "novelbin.cc",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://novelbin.com/",
    "X-Requested-With": "XMLHttpRequest",
}


class NovelBinParser(BaseParser):
    site_name = "NovelBin"
    url_patterns = []

    def can_handle(self, url: str) -> bool:
        return any(d in url for d in _DOMAINS)

    # ------------------------------------------------------------------ ToC

    def get_book_info(self, url: str, soup) -> dict:
        # Normalise: strip fragment (#tab-chapters-title etc.)
        base_url = url.split("#")[0].rstrip("/")

        title = self.first_text(
            soup,
            "div.book-info h3.title",
            "h3.title",
            "h1",
        )
        author = self.first_text(
            soup,
            "div.book-info a.info-author",
            "a.info-author",
            "span.author a",
        )
        description = self.first_text(
            soup,
            "div.desc-text",
            "div.book-intro p",
            "div.summary__content",
        )
        cover_url = ""
        for sel in ["div.book-img img", "div.book-image img", "img.cover"]:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src") or el.get("data-lazy-src") or ""
                if src:
                    cover_url = self.absolute_url(base_url, src)
                    break

        chapters = (
            self._chapters_from_static(soup, base_url) or
            self._chapters_from_ajax(soup, base_url)
        )

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    # ------------------------------------------------------------------ chapter content

    def get_chapter_content(self, url: str, soup) -> str:
        content = soup.select_one("div#chr-content") or soup.select_one("div.chr-c")
        if not content:
            content = soup.select_one("div#chapter-content") or soup.select_one("div.chapter-content")
        if not content:
            return self.element_to_text(soup.find("body"))

        # Strip injected ads, navigation banners, and inline script blocks
        for unwanted in content.select(
            "div.ads, div[id*='ads'], ins.adsbygoogle, "
            "div.chapter-nav, div.navigator, "
            "p.ad, div.ad-container, "
            "script, style, noscript"
        ):
            unwanted.decompose()

        # Remove lines that are purely navigation text
        _NAV_PATTERN = re.compile(
            r"^\s*(previous|next|chapter|prev|←|→|«|»)\s*$", re.IGNORECASE
        )
        for p in content.find_all(["p", "span"]):
            if p.string and _NAV_PATTERN.match(p.get_text(strip=True)):
                p.decompose()

        return self.element_to_text(content)

    # ------------------------------------------------------------------ helpers

    def _chapters_from_static(self, soup, base_url: str) -> list:
        """Try the #tab-chapters-title panel which may have static links."""
        tab = soup.select_one("#tab-chapters-title")
        if tab:
            links = tab.select("li a[href]")
            if links:
                return self._links_to_list(links, base_url)

        # Also try the generic list selectors in case tab isn't used
        for sel in ["ul.list-chapter li a", "#list-chapter li a", "ul.list-chapter a"]:
            links = soup.select(sel)
            if links:
                return self._links_to_list(links, base_url)

        return []

    def _chapters_from_ajax(self, soup, base_url: str) -> list:
        """
        Extract the numeric novel ID then call:
          GET {origin}/ajax/chapter-archive?novelId={id}
        Returns the HTML fragment, parse <li><a> from it.
        """
        novel_id = self._extract_novel_id(soup, base_url)
        if not novel_id:
            return []

        # Derive origin (https://novelbin.com)
        m = re.match(r"(https?://[^/]+)", base_url)
        origin = m.group(1) if m else "https://novelbin.com"
        ajax_url = f"{origin}/ajax/chapter-archive?novelId={novel_id}"

        try:
            resp = requests.get(ajax_url, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception:
            return []

        from bs4 import BeautifulSoup
        frag = BeautifulSoup(resp.text, "lxml")
        links = frag.select("li a[href]")
        if not links:
            # Some responses wrap differently
            links = frag.find_all("a", href=True)
        return self._links_to_list(links, base_url)

    def _extract_novel_id(self, soup, base_url: str) -> str:
        """Find the numeric novel ID that NovelBin needs for its AJAX endpoint."""

        # 1. data-novel-id / data-id on the chapter tab button or body
        for attr in ["data-novel-id", "data-id", "data-bookid"]:
            el = soup.select_one(f"[{attr}]")
            if el:
                val = el.get(attr, "").strip()
                if val.isdigit():
                    return val

        # 2. Hidden input field
        inp = soup.find("input", {"name": re.compile(r"novel[_-]?id", re.IGNORECASE)})
        if inp:
            val = (inp.get("value") or "").strip()
            if val.isdigit():
                return val

        # 3. JavaScript variable in inline <script> tags
        _JS_PATTERNS = [
            r'novel[_-]?id\s*[=:]\s*["\']?(\d+)',
            r'bookId\s*[=:]\s*["\']?(\d+)',
            r'"id"\s*:\s*"?(\d+)"?\s*,\s*"title"',
        ]
        for script in soup.find_all("script"):
            text = script.string or ""
            for pat in _JS_PATTERNS:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    return m.group(1)

        # 4. Canonical URL or og:url may encode the ID
        canonical = soup.find("link", {"rel": "canonical"})
        if canonical:
            m = re.search(r"/b/[^/]+-(\d+)(?:/|$)", canonical.get("href", ""))
            if m:
                return m.group(1)

        return ""

    def _links_to_list(self, link_els, base_url: str) -> list:
        chapters = []
        seen = set()
        for a in link_els:
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue
            # Only follow /b/{slug}/chapter-* paths
            if "/b/" not in href and not href.startswith("http"):
                continue
            full = self.absolute_url(base_url, href)
            if full in seen:
                continue
            seen.add(full)
            chapters.append({
                "url": full,
                "title": a.get_text(strip=True) or "Chapter",
            })
        return chapters
