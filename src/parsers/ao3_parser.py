import re
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs, urljoin
from .base_parser import BaseParser


class AO3Parser(BaseParser):
    site_name = "Archive of Our Own"
    url_patterns = [r"archiveofourown\.org/works/"]

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(soup, "h2.title.heading", "h2.heading")
        author = self.first_text(soup, "a[rel='author']", "h3.byline a")
        description = self.first_text(soup, "div.summary blockquote", "blockquote.userstuff")

        tags = [t.get_text(strip=True) for t in soup.select(".meta .tags a")]

        cover_url = self.og_meta(soup, "image")

        # Navigate URL for chapter list
        work_id = re.search(r"/works/(\d+)", url)
        if not work_id:
            return {"title": title, "author": author, "description": description,
                    "cover_url": cover_url, "tags": ", ".join(tags), "chapters": []}

        wid = work_id.group(1)
        navigate_url = f"https://archiveofourown.org/works/{wid}/navigate"
        chapters = self._get_chapters_from_navigate(navigate_url, url, soup, wid)

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": ", ".join(tags),
            "chapters": chapters,
            "_navigate_url": navigate_url,
        }

    def _get_chapters_from_navigate(self, navigate_url, base_url, soup, work_id):
        # First try chapter list from the current page's nav
        chapters = []

        # Check for navigate page links already in DOM
        for a in soup.select("ol.chapter.index.group li a, #chapter_index a"):
            href = a.get("href", "")
            if href:
                ch_url = self.absolute_url(base_url, href)
                # Add adult bypass
                ch_url = self._add_adult_flag(ch_url)
                chapters.append({"url": ch_url, "title": a.get_text(strip=True)})

        if chapters:
            return chapters

        # Single-chapter work or need to fetch navigate page
        # Check if single chapter
        if not soup.select_one("li.chapter"):
            single_url = f"https://archiveofourown.org/works/{work_id}?view_adult=true"
            return [{"url": single_url, "title": "Full Work"}]

        # Return the navigate URL to be fetched by web fetcher
        return [{"url": f"__navigate__{navigate_url}", "title": "__fetch_nav__"}]

    def _add_adult_flag(self, url: str) -> str:
        if "view_adult" not in url:
            sep = "&" if "?" in url else "?"
            return url + sep + "view_adult=true"
        return url

    def get_chapter_content(self, url: str, soup) -> str:
        # Remove chapter metadata, keep userstuff
        for el in soup.select("div#feedback, div.feedback, div.chapter.preface.group"):
            el.decompose()
        content = soup.select_one("div#chapters div.userstuff") or \
                  soup.select_one("div.userstuff") or \
                  soup.select_one("div#chapters")
        return self.element_to_text(content)
