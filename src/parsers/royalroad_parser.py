from .base_parser import BaseParser


class RoyalRoadParser(BaseParser):
    site_name = "Royal Road"
    url_patterns = [r"royalroad\.com", r"royalroadl\.com"]

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(
            soup,
            "div.fic-header div.col h1",
            "h1.font-white",
            "h1",
        )
        author = self.first_text(
            soup,
            "div.fic-header h4 span a",
            "div.fic-header h4 a",
        )
        description = self.first_text(
            soup,
            "div.fiction-info div.description",
            "div.summary",
        )
        cover_el = soup.select_one("img.thumbnail")
        cover_url = self.absolute_url(url, cover_el.get("src", "")) if cover_el else ""

        tags = [t.get_text(strip=True) for t in soup.select("div.fiction-info span.tags .label")]

        chapters = []
        for a in soup.select("table#chapters tbody tr td a[href*='/chapter/']"):
            href = a.get("href", "")
            if href:
                chapters.append({
                    "url": self.absolute_url(url, href),
                    "title": a.get_text(strip=True),
                })

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for ch in chapters:
            if ch["url"] not in seen:
                seen.add(ch["url"])
                unique.append(ch)

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": ", ".join(tags),
            "chapters": unique,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        # Content lives in div.chapter-inner inside div.portlet-body
        el = soup.select_one("div.chapter-inner") or \
             soup.select_one("div.portlet-body div.chapter-content") or \
             soup.select_one("div.chapter-content")
        return self.element_to_text(el)
