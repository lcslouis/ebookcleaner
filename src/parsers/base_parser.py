import re
from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse


class BaseParser(ABC):
    site_name = "Unknown"
    url_patterns = []

    def can_handle(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE) for p in self.url_patterns)

    @abstractmethod
    def get_book_info(self, url: str, soup) -> dict:
        """
        Return dict:
          title, author, description, cover_url,
          chapters: [{url, title}]
        """

    @abstractmethod
    def get_chapter_content(self, url: str, soup) -> str:
        """Return plain text content for a single chapter page."""

    # ------------------------------------------------------------------ helpers

    def element_to_text(self, el) -> str:
        if el is None:
            return ""
        for tag in el.find_all(
            ["script", "style", "nav", "header", "footer",
             "iframe", "noscript", "aside", "form", "button"]
        ):
            tag.decompose()
        lines = []
        for line in el.get_text(separator="\n").split("\n"):
            lines.append(line.strip())
        result = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank and result:
                    result.append("")
                prev_blank = True
            else:
                result.append(line)
                prev_blank = False
        return "\n".join(result).strip()

    def absolute_url(self, base: str, href: str) -> str:
        if not href:
            return ""
        return urljoin(base, href)

    def og_meta(self, soup, prop: str) -> str:
        tag = soup.find("meta", {"property": f"og:{prop}"}) or \
              soup.find("meta", {"name": prop})
        return (tag.get("content") or "").strip() if tag else ""

    def first_text(self, soup, *selectors) -> str:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""
