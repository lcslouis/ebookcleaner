"""
NovelBin parser (novelbin.com and mirror domains).

Chapter URL pattern:  /b/{novel-slug}/{chapter-slug}
ToC URL pattern:      /b/{novel-slug}

The first ~30 chapters are embedded in a <template data-first-chapter-template>
element inside #chapter-archive.  The full list requires an AJAX call:

  GET /ajax/chapter-archive?novelId={slug}&_csrf={token}

where {slug} is the URL slug (NOT a numeric ID) and {token} is extracted
from an inline <script> const csrf = "...".

Chapter content lives in div#chr-content or div.chr-c.
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
        base_url = url.split("#")[0].rstrip("/")

        # Title: <h3 class="title" itemprop="name"> inside div.desc
        title = (
            self.first_text(soup, "h3.title[itemprop='name']", "h3.title", "h1.title", "h1")
        )

        # Author: og:novel:author meta tag is most reliable
        author_meta = soup.find("meta", {"property": "og:novel:author"})
        author = (author_meta.get("content", "").strip() if author_meta else "") or self.first_text(
            soup,
            "ul.info li a[href*='/a/']",
            "a.info-author",
            "span.author a",
        )

        # Description: div#novel-description-content (real id from HTML source)
        description = self.first_text(
            soup,
            "#novel-description-content",
            "div.desc-text",
            "div.book-intro p",
        )

        # Tags: og:novel:genre meta tag
        genre_meta = soup.find("meta", {"property": "og:novel:genre"})
        tags = genre_meta.get("content", "").strip() if genre_meta else ""

        # Cover: lazy-loaded <img class="lazy" data-src="..."> inside div.book
        cover_url = ""
        for sel in ["div.book img.lazy", "div.book-img img", "div.book-image img", "img.cover"]:
            el = soup.select_one(sel)
            if el:
                src = (
                    el.get("data-src") or el.get("data-lazy-src") or
                    el.get("src") or ""
                )
                if src:
                    cover_url = self.absolute_url(base_url, src)
                    break

        # AJAX returns the full chapter list; template only has the first ~30
        chapters = (
            self._chapters_from_ajax(soup, base_url) or
            self._chapters_from_template(soup, base_url)
        )

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": tags,
            "chapters": chapters,
        }

    # ------------------------------------------------------------------ chapter content

    def get_chapter_content(self, url: str, soup) -> str:
        content = soup.select_one("div#chr-content") or soup.select_one("div.chr-c")
        if not content:
            content = soup.select_one("div#chapter-content") or soup.select_one("div.chapter-content")
        if not content:
            return self.element_to_text(soup.find("body"))

        for unwanted in content.select(
            "div.ads, div[id*='ads'], ins.adsbygoogle, "
            "div.chapter-nav, div.navigator, "
            "p.ad, div.ad-container, "
            "script, style, noscript"
        ):
            unwanted.decompose()

        _NAV_PATTERN = re.compile(
            r"^\s*(previous|next|chapter|prev|←|→|«|»)\s*$", re.IGNORECASE
        )
        for p in content.find_all(["p", "span"]):
            if p.string and _NAV_PATTERN.match(p.get_text(strip=True)):
                p.decompose()

        return self.element_to_text(content)

    # ------------------------------------------------------------------ helpers

    def _chapters_from_template(self, soup, base_url: str) -> list:
        """
        Read the static chapter list embedded in:
          <template data-first-chapter-template>
            <li data-first-chapter-item><a href="/b/slug/chapter-...">
        BeautifulSoup with lxml treats <template> as a regular tag,
        so its children are directly accessible.
        """
        # Primary: template inside #chapter-archive
        template = soup.select_one("#chapter-archive template[data-first-chapter-template]")
        if not template:
            template = soup.select_one("template[data-first-chapter-template]")

        if template:
            links = template.select("li[data-first-chapter-item] a[href]")
            if not links:
                links = template.select("li a[href]")
            if links:
                return self._links_to_list(links, base_url)

        # Fallback: static list selectors (older site versions)
        for sel in ["#tab-chapters ul.list-chapter li a", "ul.list-chapter li a",
                    "#list-chapter li a"]:
            links = soup.select(sel)
            if links:
                return self._links_to_list(links, base_url)

        return []

    def _chapters_from_ajax(self, soup, base_url: str) -> list:
        """
        Call GET /ajax/chapter-archive?novelId={slug}&_csrf={token}
        The slug is the URL path segment after /b/.
        The CSRF token is extracted from an inline <script>.
        """
        slug = self._extract_slug(base_url)
        if not slug:
            return []

        csrf = self._extract_csrf(soup)
        m = re.match(r"(https?://[^/]+)", base_url)
        origin = m.group(1) if m else "https://novelbin.com"

        params = {"novelId": slug}
        if csrf:
            params["_csrf"] = csrf

        ajax_url = f"{origin}/ajax/chapter-archive"
        try:
            resp = requests.get(ajax_url, params=params, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception:
            return []

        from bs4 import BeautifulSoup
        frag = BeautifulSoup(resp.text, "lxml")

        # AJAX response may also use <template> or direct <li> elements
        template = frag.select_one("template[data-first-chapter-template]")
        if template:
            links = template.select("li a[href]")
        else:
            links = frag.select("li a[href]")
        if not links:
            links = frag.find_all("a", href=True)

        return self._links_to_list(links, base_url)

    def _extract_slug(self, base_url: str) -> str:
        """Extract the novel slug from the URL: /b/{slug} → slug."""
        m = re.search(r"/b/([^/?#]+)", base_url)
        return m.group(1) if m else ""

    def _extract_csrf(self, soup) -> str:
        """Find CSRF token from inline JS: const csrf = "..."."""
        for script in soup.find_all("script"):
            text = script.string or ""
            m = re.search(r'const\s+csrf\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1)
        # Also check data attribute on hidden input
        inp = soup.find("input", {"name": re.compile(r"_csrf|csrf", re.IGNORECASE)})
        if inp:
            return (inp.get("value") or "").strip()
        return ""

    def _links_to_list(self, link_els, base_url: str) -> list:
        chapters = []
        seen = set()
        for a in link_els:
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue
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
