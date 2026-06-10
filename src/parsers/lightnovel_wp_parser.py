"""
Parser for WordPress sites running the "lightnovel" theme (and similar
variants like Tsuki-Manga/WPManga). These sites are NOT Fictioneer —
they have a distinct structure: .eplister chapter lists, .epcontent for
chapter body, and div.bigcontent/.infox for series metadata.

Detection is HTML-signature based so it covers any domain running the theme.
"""
from .base_parser import BaseParser


class LightNovelWPParser(BaseParser):
    site_name = "LightNovel WP Theme"
    url_patterns = []  # detected by can_handle_soup()

    def can_handle(self, url: str) -> bool:
        return False  # URL-only detection not possible; rely on can_handle_soup

    def can_handle_soup(self, soup) -> bool:
        return bool(
            soup.select_one("div.eplister") or
            soup.select_one("div.epcontent") or
            soup.select_one("div.bigcontent div.infox")
        )

    # ------------------------------------------------------------------ ToC

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(
            soup,
            "h1.entry-title",
            "h1.series-title",
            "h1",
        )
        # Author appears as: <span class="author vcard"><b>Posted by:</b> <i class="fn">Name</i></span>
        author = ""
        author_el = soup.select_one("span.author.vcard i.fn")
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            author = self.first_text(
                soup,
                ".infox .spe span a",
                "a[rel='author']",
                ".author",
            )

        description = self.first_text(
            soup,
            "div.entry-content",
            "div.summary__content",
            "div.desc",
        )

        cover_url = ""
        for sel in ["div.thumb img.ts-post-image", "div.thumb img.wp-post-image",
                    "div.thumbook img", "img.ts-post-image", "img.wp-post-image"]:
            el = soup.select_one(sel)
            if el:
                src = el.get("src") or el.get("data-src") or ""
                if src:
                    cover_url = self.absolute_url(url, src)
                    break

        chapters = []
        seen = set()
        for a in soup.select("div.eplister li a"):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            # Prefer the .epl-title div for the chapter title
            title_el = a.select_one(".epl-title") or a.select_one(".epl-num")
            ch_title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            chapters.append({
                "url": self.absolute_url(url, href),
                "title": ch_title or "Chapter",
            })

        # Chapters are listed newest-first on this theme — reverse to reading order
        chapters = list(reversed(chapters))

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
        for sel in ["div.epcontent", "div.entry-content", "#content"]:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                return self.element_to_text(el)
        return self.element_to_text(soup.find("body"))
