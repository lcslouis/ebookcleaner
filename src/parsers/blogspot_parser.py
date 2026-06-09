"""
Blogspot / Blogger parser.
Handles *.blogspot.* domains as well as a curated list of custom-domain
translation blogs that are powered by Blogger.
"""
import re
from urllib.parse import urljoin
from .base_parser import BaseParser

# Custom-domain Blogger/WordPress translation blogs
_DOMAINS = [
    "sousetsuka.com",
    "ziru.worksapce.com",
    "isohungrytls.com",
    "rebirth.online",
    "insanitycave.com",
    "penultimate-word.com",
    "oniichanyamete.wordpress.com",
    "lazybastardkun.com",
    "lnmtl.com",
]


class BlogspotParser(BaseParser):
    site_name = "Blogspot / Blogger"
    url_patterns = []

    def can_handle(self, url: str) -> bool:
        if "blogspot." in url or "blogger.com" in url:
            return True
        return any(d in url for d in _DOMAINS)

    def get_book_info(self, url: str, soup) -> dict:
        title = (
            self.og_meta(soup, "title") or
            self.first_text(soup, "h3.post-title", "h1.entry-title", "h1.title", "h1")
        )
        author = self.first_text(soup, "span.post-author a", "a.fn", ".post-author")
        description = self.og_meta(soup, "description") or ""
        cover_url = self.og_meta(soup, "image") or self._find_cover(soup, url)

        chapters = self._find_chapter_links(url, soup)

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        for sel in ["div.post-body", "div.entry-content", "article.post", "div.post"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                # Upgrade image URLs to full size (Blogspot compresses by default)
                for img in el.select("img[src*='blogspot.com']"):
                    src = img.get("src", "")
                    # Remove size constraint like /s400/ -> /s0/
                    src = re.sub(r"/s\d{2,4}/", "/s0/", src)
                    img["src"] = src
                return self.element_to_text(el)
        return self.element_to_text(soup.find("body"))

    # ------------------------------------------------------------------ helpers

    def _find_chapter_links(self, base_url: str, soup) -> list:
        # Look for a post with "index" or "table of contents" in title
        chapters = []
        seen = set()

        # Try structured ToC selectors first
        for sel in ["div.post-body a", "div.entry-content a"]:
            links = soup.select(sel)
            chapter_links = [
                a for a in links
                if re.search(r"chapter|ch[-\.\s]?\d|\bpart\s*\d|\bep\s*\d",
                             (a.get("href") or "") + " " + a.get_text(),
                             re.IGNORECASE)
            ]
            if len(chapter_links) >= 2:
                for a in chapter_links:
                    href = a.get("href", "")
                    if href and href not in seen and not href.startswith("#"):
                        seen.add(href)
                        chapters.append({
                            "url": self.absolute_url(base_url, href),
                            "title": a.get_text(strip=True) or "Chapter",
                        })
                if chapters:
                    return chapters

        return chapters

    def _find_cover(self, soup, base_url: str) -> str:
        img = soup.select_one("div.post-body img:first-of-type")
        if img:
            src = img.get("src") or img.get("data-src") or ""
            if src:
                return self.absolute_url(base_url, src)
        return ""
