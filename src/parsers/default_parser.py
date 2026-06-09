import re
from urllib.parse import urljoin, urlparse
from .base_parser import BaseParser


# Ordered list of selectors tried to locate main chapter/article content
CONTENT_SELECTORS = [
    "div.chapter-content",
    "div#chapter-content",
    "div.chapter-inner",
    "div#storytext",
    "div.storytext",
    "div.chp_raw",
    "div.entry-content",
    "div#content-area",
    "div.post-body",
    "div.story-content",
    "div#story",
    "article.post-content",
    "article",
    "main article",
    "main",
    "div[class*='chapter']",
    "div[id*='chapter']",
    "div[class*='content']",
]

# Selectors for chapter list links on a ToC page
TOC_SELECTORS = [
    "table#chapters tbody tr td a",
    "div.chapter-list a",
    "ul.chapter-list li a",
    "ol.chapter-list li a",
    "div.toc a",
    "#toc a",
    ".table-of-contents a",
    "div[class*='toc'] a",
    "div[id*='toc'] a",
    "ul[class*='chapter'] li a",
    "ol[class*='chapter'] li a",
]


class DefaultParser(BaseParser):
    site_name = "Generic"
    url_patterns = [".*"]

    def __init__(self, content_selector: str = ""):
        self._custom_selector = content_selector

    def get_book_info(self, url: str, soup) -> dict:
        title = (
            self.og_meta(soup, "title") or
            self.first_text(soup, "h1") or
            (soup.find("title").get_text(strip=True) if soup.find("title") else "")
        )
        author = (
            self.og_meta(soup, "author") or
            self.first_text(soup, "a[rel='author']", ".author", "#author", "span.author")
        )
        description = self.og_meta(soup, "description") or ""
        cover_url = self.og_meta(soup, "image") or self._find_cover(soup)
        if cover_url:
            cover_url = self.absolute_url(url, cover_url)

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
        # User-supplied selector takes priority
        if self._custom_selector:
            el = soup.select_one(self._custom_selector)
            if el:
                return self.element_to_text(el)

        for selector in CONTENT_SELECTORS:
            el = soup.select_one(selector)
            if el and len(el.get_text(strip=True)) > 150:
                return self.element_to_text(el)

        return self._extract_by_density(soup)

    # ------------------------------------------------------------------ private

    def _find_chapter_links(self, base_url: str, soup) -> list:
        for selector in TOC_SELECTORS:
            links = soup.select(selector)
            if len(links) >= 2:
                return self._links_to_chapters(base_url, links)

        # Fallback: collect all links that look like chapters
        all_links = soup.find_all("a", href=True)
        chapter_links = [
            a for a in all_links
            if re.search(r"chapter|ch[-\.\s]?\d|part[-\.\s]?\d|\bep\b|\bchap\b",
                         (a.get("href") or "") + " " + a.get_text(), re.IGNORECASE)
        ]
        if len(chapter_links) >= 2:
            return self._links_to_chapters(base_url, chapter_links)

        # If nothing found — treat this URL itself as a single chapter
        return []

    def _links_to_chapters(self, base_url: str, link_els) -> list:
        chapters = []
        seen = set()
        for a in link_els:
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue
            full_url = self.absolute_url(base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)
            chapters.append({"url": full_url, "title": a.get_text(strip=True) or "Chapter"})
        return chapters

    def _extract_by_density(self, soup) -> str:
        best_el = None
        best_score = 0
        for el in soup.find_all(["div", "section", "article"]):
            text = el.get_text(strip=True)
            if len(text) < 300:
                continue
            link_text = " ".join(a.get_text(strip=True) for a in el.find_all("a"))
            score = len(text) - len(link_text) * 3
            if score > best_score:
                best_score = score
                best_el = el
        if best_el:
            return self.element_to_text(best_el)
        return soup.body.get_text(separator="\n", strip=True) if soup.body else ""

    def _find_cover(self, soup) -> str:
        for sel in ["img.cover", "img.book-cover", "img.thumbnail", ".cover img", "img[class*='cover']"]:
            el = soup.select_one(sel)
            if el:
                return el.get("src") or el.get("data-src") or ""
        return ""
