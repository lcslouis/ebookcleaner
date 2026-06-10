"""
Generic WordPress parser.

Detects any WordPress site via the standard generator meta tag
(content="WordPress …") or wp-content links, then tries a broad set of
CSS selectors common across WP novel/fiction themes.

More specific parsers (Fictioneer, Blogspot, site configs, etc.) are
checked first in the registry, so this only runs for sites that didn't
match anything else.
"""
import re
from .base_parser import BaseParser

# Chapter list selectors, tried in order — covers Tsuki/lightnovel, Madara,
# WP-Manga, Genesis variants, and hand-rolled WP fiction themes.
_TOC_SELECTORS = [
    "div.eplister li a",        # lightnovel / Tsuki theme
    "ul.main.version-chap li a",  # Madara
    "li.wp-manga-chapter a",    # WP-Manga / Madara
    "div.listing-chapters_wrap a",
    "ul.sub-chap-list a",
    "ul.chapter-list li a",
    "#chapterlist li a",
    "ul.chapters li a",
    "table.chapters td.chapter-name a",
    ".chapter-list a",
    ".list-chapter a",
    ".tab-content a",
    "ul li a[href*='chapter']",  # broad fallback for WP chapter slugs
]

_CONTENT_SELECTORS = [
    "div.epcontent",            # lightnovel / Tsuki
    "div.reading-content",      # Madara / WP-Manga
    "div#chapter-content",
    "div.chapter-content",
    "div.entry-content",
    "div#content .post-content",
    "article.post .entry-content",
    "div.post-content",
    "div.text-left",
]

_TITLE_SELECTORS = [
    "h1.entry-title",
    "div.post-title h1",
    "h1.title",
    "h1",
]

_AUTHOR_SELECTORS = [
    "span.author.vcard i.fn",   # lightnovel / Tsuki
    ".author-content a",        # Madara
    "div.author-name-container a",
    ".manga-authors a",
    "a[rel='author']",
    "span.author a",
    ".infox .spe span a",
]

_DESCRIPTION_SELECTORS = [
    "div.summary__content",     # Madara
    "div.entry-content",
    ".description-summary",
    "div.manga-summary",
    ".post-content .summary",
    ".synopsis",
    ".desc",
]

_COVER_SELECTORS = [
    "div.thumb img.ts-post-image",
    "div.thumb img.wp-post-image",
    "div.summary_image img",    # Madara
    "div.thumbook img",
    "img.ts-post-image",
    "img.wp-post-image",
    "div.book-cover img",
    "figure.thumbnail img",
]


def _is_wordpress(soup) -> bool:
    """True if the page is served by WordPress.

    Checks in order of reliability:
    1. Standard generator meta tag (most sites have this)
    2. wp-content / wp-includes in any asset URL (catches sites that strip the meta)
    3. WordPress-specific links buried in the page (wp-login, wp-admin, wp-json, xmlrpc)
    4. Common WP body classes (home, page, single, blog, logged-in)
    """
    gen = soup.find("meta", attrs={"name": "generator"})
    if gen and re.search(r"wordpress", gen.get("content", ""), re.IGNORECASE):
        return True

    # Asset paths
    for tag in soup.find_all(["link", "script"], limit=50):
        src = tag.get("href") or tag.get("src") or ""
        if "wp-content" in src or "wp-includes" in src:
            return True

    # WordPress-specific URL patterns anywhere in the page
    page_text = str(soup)[:50_000]   # cap to avoid scanning huge pages
    if re.search(r'/(wp-login\.php|wp-admin/|wp-json/|xmlrpc\.php)["\'/]', page_text):
        return True

    # WP body classes — present on virtually every WP theme
    body = soup.find("body")
    if body:
        classes = " ".join(body.get("class") or [])
        if re.search(r"\b(home|single|page|archive|blog|logged-in|wp-)\b", classes):
            # Only treat as WP if at least one other WP-ish element is present
            if soup.find(attrs={"class": re.compile(r"^wp-")}):
                return True

    return False


class LightNovelWPParser(BaseParser):
    site_name = "WordPress"
    url_patterns = []  # detected by can_handle_soup() only

    def can_handle(self, url: str) -> bool:
        return False

    def can_handle_soup(self, soup) -> bool:
        return _is_wordpress(soup)

    # ------------------------------------------------------------------ ToC

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(soup, *_TITLE_SELECTORS)

        author = ""
        for sel in _AUTHOR_SELECTORS:
            el = soup.select_one(sel)
            if el:
                author = el.get_text(strip=True)
                if author:
                    break
        if not author:
            author = self.og_meta(soup, "author")

        description = self.first_text(soup, *_DESCRIPTION_SELECTORS)

        cover_url = ""
        for sel in _COVER_SELECTORS:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src") or el.get("data-lazy-src") or ""
                if src:
                    cover_url = self.absolute_url(url, src)
                    break
        if not cover_url:
            cover_url = self.og_meta(soup, "image")

        chapters = []
        seen = set()
        for sel in _TOC_SELECTORS:
            anchors = soup.select(sel)
            if not anchors:
                continue
            for a in anchors:
                href = a.get("href", "")
                if not href or href in seen:
                    continue
                seen.add(href)
                # Prefer a child title element over raw link text
                title_el = (
                    a.select_one(".epl-title") or
                    a.select_one(".chapter-name") or
                    a.select_one(".chapter-title")
                )
                ch_title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
                chapters.append({
                    "url": self.absolute_url(url, href),
                    "title": ch_title or "Chapter",
                })
            if chapters:
                break  # stop at first selector that produced results

        # Many WP themes list chapters newest-first — detect and reverse
        if len(chapters) >= 2:
            chapters = _ensure_ascending(chapters)

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    # ------------------------------------------------------------------ chapter

    def get_chapter_content(self, url: str, soup) -> str:
        for sel in _CONTENT_SELECTORS:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                return self.element_to_text(el)
        return self.element_to_text(soup.find("body"))


# ------------------------------------------------------------------ helpers

def _ensure_ascending(chapters: list) -> list:
    """
    Reverse the chapter list if it appears to be in descending order.
    Heuristic: compare the numeric suffix (if any) of the first and last title.
    """
    def _num(title: str):
        m = re.search(r"(\d+(?:\.\d+)?)\s*$", title)
        return float(m.group(1)) if m else None

    first_n = _num(chapters[0]["title"])
    last_n = _num(chapters[-1]["title"])
    if first_n is not None and last_n is not None and first_n > last_n:
        return list(reversed(chapters))
    return chapters
