"""
Wattpad parser.
Wattpad renders content via React so the HTML has no readable text.
We use their public JSON API instead:
  Story metadata + chapter list: /api/v3/stories/{storyId}
  Chapter text:                   /apiv2/storytext?id={partId}
"""
import re
import requests
from .base_parser import BaseParser

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_API_BASE = "https://www.wattpad.com"


class WattpadParser(BaseParser):
    site_name = "Wattpad"
    url_patterns = [r"wattpad\.com"]

    def get_book_info(self, url: str, soup) -> dict:
        story_id = self._extract_story_id(url, soup)
        if not story_id:
            # Best-effort HTML fallback for unsupported URL shapes
            return self._html_fallback(url, soup)

        try:
            data = self._api_get(
                f"/api/v3/stories/{story_id}",
                fields="id,title,user(name),description,cover,mainCategory,tags,parts(id,title,url)",
            )
        except Exception as exc:
            return self._html_fallback(url, soup)

        parts = data.get("parts") or []
        chapters = [
            {
                "url": p.get("url") or f"{_API_BASE}/{p['id']}",
                "title": p.get("title") or f"Chapter {i + 1}",
                "_part_id": str(p["id"]),
            }
            for i, p in enumerate(parts)
            if p.get("id")
        ]

        tags = ", ".join(t.get("name", "") for t in (data.get("tags") or []))
        user = data.get("user") or {}

        return {
            "title": data.get("title") or "",
            "author": user.get("name") or "",
            "description": data.get("description") or "",
            "cover_url": data.get("cover") or "",
            "tags": tags,
            "chapters": chapters,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        # Extract part id from URL or _part_id injected by get_book_info
        part_id = self._extract_part_id(url)
        if part_id:
            try:
                return self._fetch_part_text(part_id)
            except Exception:
                pass
        # HTML fallback
        el = soup.select_one("pre.style-scope.h-reader-text") or \
             soup.select_one("p.text-raw") or \
             soup.find("body")
        return self.element_to_text(el)

    # ------------------------------------------------------------------ helpers

    def _extract_story_id(self, url: str, soup) -> str:
        # https://www.wattpad.com/story/123456-title
        m = re.search(r"/story/(\d+)", url)
        if m:
            return m.group(1)
        # Try _sharedData JSON embedded in page
        script = soup.find("script", string=re.compile(r"_sharedData"))
        if script:
            m2 = re.search(r'"id"\s*:\s*"?(\d+)"?', script.string or "")
            if m2:
                return m2.group(1)
        # Try window.__reactRouterInitialState
        for sc in soup.find_all("script"):
            text = sc.string or ""
            m3 = re.search(r'"storyId"\s*:\s*"?(\d+)"?', text)
            if m3:
                return m3.group(1)
        return ""

    def _extract_part_id(self, url: str) -> str:
        # https://www.wattpad.com/123456789-chapter-title
        m = re.search(r"wattpad\.com/(\d+)(?:-|$)", url)
        return m.group(1) if m else ""

    def _api_get(self, path: str, **params) -> dict:
        resp = requests.get(
            f"{_API_BASE}{path}",
            params=params,
            headers=_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    def _fetch_part_text(self, part_id: str) -> str:
        # Wattpad legacy API - returns HTML
        resp = requests.get(
            f"{_API_BASE}/apiv2/storytext",
            params={"id": part_id},
            headers={**_HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=20,
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        return self.element_to_text(soup.find("body") or soup)

    def _html_fallback(self, url: str, soup) -> dict:
        title = self.og_meta(soup, "title") or self.first_text(soup, "h1")
        author = self.first_text(soup, "a[href*='/user/']")
        cover = self.og_meta(soup, "image")
        return {
            "title": title,
            "author": author,
            "description": "",
            "cover_url": cover,
            "tags": "",
            "chapters": [],
        }
