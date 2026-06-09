"""
Fictioneer WordPress theme parser.
Fictioneer is a popular WP theme for web fiction. Multiple sites use it.
Registered domains are a curated list; can_handle also checks for the
theme's distinctive CSS class signatures.
"""
from .base_parser import BaseParser

# Known sites running the Fictioneer WordPress theme
_DOMAINS = [
    "cherrymist.cafe",
    "emberlib731.xyz",
    "flyonthewalls.blog",
    "novelib.com",
    "smeraldogarden.com",
    "springofromance.com",
    "storiesbytales.com",
    "grumpyoldbookworm.com",
]


class FictioneerParser(BaseParser):
    site_name = "Fictioneer (WordPress Theme)"
    url_patterns = []  # detected by can_handle()

    def can_handle(self, url: str) -> bool:
        if any(d in url for d in _DOMAINS):
            return True
        return False

    def can_handle_soup(self, soup) -> bool:
        """Secondary check: look for Fictioneer theme identifiers in page HTML."""
        return bool(
            soup.select_one("body.fictioneer") or
            soup.select_one("div#fictioneer-main") or
            soup.select_one("article.story")
        )

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(
            soup,
            ".story__identity-title",
            "h1.story_name",
            "h1.entry-title",
            "h1",
        )
        author = self.first_text(
            soup,
            "a.author",
            ".story__identity-meta a",
            "a[rel='author']",
        )
        description = self.first_text(
            soup,
            "div.story__summary",
            "div.entry-content p:first-of-type",
        )
        cover_url = ""
        for sel in [".wp-post-image", "figure.story__thumbnail img", "img.story-cover"]:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src") or ""
                if src:
                    cover_url = self.absolute_url(url, src)
                    break

        chapters = []
        seen = set()
        for a in soup.select(".chapter-group__list a, ul.story__chapters a, .chapters-list a"):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            # Skip locked/scheduled chapters (have a lock icon or .is-locked class)
            li = a.find_parent("li")
            if li and ("is-locked" in (li.get("class") or []) or li.select_one(".fa-lock")):
                continue
            chapters.append({
                "url": self.absolute_url(url, href),
                "title": a.get_text(strip=True) or "Chapter",
            })

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        for sel in [".chapter-formatting", "#chapter-content", "div.entry-content"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                return self.element_to_text(el)
        return self.element_to_text(soup.find("body"))
