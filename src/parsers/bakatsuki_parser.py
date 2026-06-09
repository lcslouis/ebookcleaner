"""
Baka-Tsuki parser.
Baka-Tsuki is a MediaWiki site. The project page lists volumes/chapters as
links to wiki article pages. Each wiki article page contains the translated text.
"""
import re
from urllib.parse import urljoin, urlparse, parse_qs
from .base_parser import BaseParser


class BakaTsukiParser(BaseParser):
    site_name = "Baka-Tsuki"
    url_patterns = [r"baka-tsuki\.org"]

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(soup, "h1#firstHeading", "h1.firstHeading", "h1")
        author = ""  # Usually extracted from series infobox
        description = self.first_text(soup, "div.mw-content-ltr > p:first-of-type")
        cover_url = self._find_cover(soup, url)

        chapters = self._extract_chapters(soup, url)

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        # Remove navigation boxes, TOC, and edit links
        for el in soup.select(
            "div#toc, div.toc, div.noprint, span.mw-editsection, "
            "div.navbox, table.navbox, div.thumbcaption"
        ):
            el.decompose()
        content = (
            soup.select_one("div#mw-content-text div.mw-parser-output") or
            soup.select_one("div.mw-content-ltr") or
            soup.select_one("div#content")
        )
        return self.element_to_text(content)

    # ------------------------------------------------------------------ helpers

    def _extract_chapters(self, soup, base_url: str) -> list:
        content = (
            soup.select_one("div#mw-content-text") or
            soup.select_one("div.mw-content-ltr") or
            soup.find("body")
        )
        if not content:
            return []

        chapters = []
        seen = set()
        for a in content.select("a[href]"):
            href = a.get("href", "")
            if not href or href.startswith("#") or "action=" in href:
                continue
            # Only follow wiki article links (no File:, User:, Template:, etc.)
            if re.search(r":(File|User|Template|Category|Help|Special):", href, re.IGNORECASE):
                continue
            # Must be a /wiki/ path
            if "/wiki/" not in href and not href.startswith("/Baka"):
                continue
            full = urljoin(base_url, href)
            if full in seen:
                continue
            seen.add(full)
            text = a.get_text(strip=True)
            if text and len(text) > 1:
                chapters.append({"url": full, "title": text})

        return chapters

    def _find_cover(self, soup, base_url: str) -> str:
        # Look for the first image that could be a cover/illustration
        for img in soup.select("div.thumb img, div.floatright img, img.thumbimage"):
            src = img.get("src") or img.get("data-src") or ""
            if src and not src.endswith(".svg"):
                return self.absolute_url(base_url, src)
        return ""
