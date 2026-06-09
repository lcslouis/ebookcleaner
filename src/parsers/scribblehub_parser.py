import re
import json
from .base_parser import BaseParser


class ScribbleHubParser(BaseParser):
    site_name = "ScribbleHub"
    url_patterns = [r"scribblehub\.com/series/"]

    AJAX_URL = "https://www.scribblehub.com/wp-admin/admin-ajax.php"

    def get_book_info(self, url: str, soup) -> dict:
        title = self.first_text(soup, "div.fic_title", "h1.title", "h1")
        author = self.first_text(soup, "span.auth_name_fic", "a.auth_name_fic")
        description = self.first_text(soup, "div.wi_fic_desc", "div.fic-desc")

        cover_el = soup.select_one("div.fic_image img") or soup.select_one("img.lazy")
        cover_url = ""
        if cover_el:
            cover_url = cover_el.get("src") or cover_el.get("data-src") or ""
            cover_url = self.absolute_url(url, cover_url)

        tags = [t.get_text(strip=True) for t in soup.select("a.stag")]

        # Get post ID for AJAX call
        post_id = self._extract_post_id(soup, url)

        # Chapters will be fetched via AJAX — signal to web_fetcher
        chapters_placeholder = []
        if post_id:
            chapters_placeholder = [{"url": f"__scribblehub_toc__{post_id}", "title": "__fetch_toc__"}]

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": ", ".join(tags),
            "chapters": chapters_placeholder,
            "_post_id": post_id,
        }

    def _extract_post_id(self, soup, url) -> str:
        # Try to find post ID in page source
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or ""
            m = re.search(r"var\s+toc_id\s*=\s*(\d+)", text)
            if m:
                return m.group(1)
            m = re.search(r'"postid"\s*:\s*"?(\d+)"?', text)
            if m:
                return m.group(1)

        # Try URL-based extraction: /series/12345/
        m = re.search(r"/series/(\d+)/", url)
        if m:
            return m.group(1)
        return ""

    def fetch_chapter_list(self, post_id: str, session) -> list:
        """Call ScribbleHub AJAX to get full chapter list. Uses requests session."""
        chapters = []
        page = 1
        while True:
            data = {
                "action": "wi_gettoc",
                "postid": post_id,
                "pagenum": str(page),
                "order": "0",
            }
            try:
                resp = session.post(self.AJAX_URL, data=data, timeout=15)
                resp.raise_for_status()
                body = resp.json()
            except Exception:
                break

            items = body.get("data", [])
            if not items:
                break
            for item in items:
                ch_url = item.get("chapter_link") or item.get("url") or ""
                ch_title = item.get("chapter_title") or item.get("title") or ""
                if ch_url:
                    chapters.append({"url": ch_url, "title": ch_title})
            if len(items) < 100:
                break
            page += 1

        return chapters

    def get_chapter_content(self, url: str, soup) -> str:
        el = soup.select_one("div.chp_raw") or \
             soup.select_one("div.chapter-content") or \
             soup.select_one("div#chapter-content")
        return self.element_to_text(el)
