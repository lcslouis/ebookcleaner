"""
Config-driven parser: one class handles all sites defined in site_configs.py.
"""
from .base_parser import BaseParser
from .site_configs import SITE_CONFIGS, SiteConfig


class ConfigParser(BaseParser):
    def __init__(self, config: SiteConfig):
        self._config = config
        self.site_name = config.site_name

    def can_handle(self, url: str) -> bool:
        return any(d in url for d in self._config.domains)

    # ------------------------------------------------------------------ BaseParser impl

    def get_book_info(self, url: str, soup) -> dict:
        cfg = self._config
        return {
            "title": self._first_text(soup, cfg.title_selectors),
            "author": self._first_text(soup, cfg.author_selectors),
            "description": self._first_text(soup, cfg.description_selectors),
            "cover_url": self._find_cover(soup, cfg.cover_selectors, url),
            "tags": "",
            "chapters": self._find_chapters(soup, cfg.toc_selectors, url),
        }

    def get_chapter_content(self, url: str, soup) -> str:
        for sel in self._config.content_selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 100:
                return self.element_to_text(el)
        # Fallback: largest text block
        return self.element_to_text(soup.find("body"))

    # ------------------------------------------------------------------ helpers

    def _first_text(self, soup, selectors) -> str:
        for sel in (selectors or []):
            el = soup.select_one(sel)
            if el:
                # meta tags expose content attribute
                if el.name == "meta":
                    val = el.get("content") or ""
                else:
                    val = el.get_text(strip=True)
                if val:
                    return val
        return ""

    def _find_cover(self, soup, selectors, base_url: str) -> str:
        for sel in (selectors or []):
            el = soup.select_one(sel)
            if not el:
                continue
            if el.name == "meta":
                val = el.get("content") or ""
            else:
                val = (el.get("src") or el.get("data-src") or
                       el.get("data-lazy-src") or el.get("data-original") or "")
            if val:
                return self.absolute_url(base_url, val)
        return ""

    def _find_chapters(self, soup, selectors, base_url: str) -> list:
        for sel in (selectors or []):
            links = soup.select(sel)
            if len(links) >= 1:
                result = []
                seen = set()
                for a in links:
                    href = a.get("href", "")
                    if not href or href.startswith("#"):
                        continue
                    full = self.absolute_url(base_url, href)
                    if full in seen:
                        continue
                    seen.add(full)
                    result.append({
                        "url": full,
                        "title": a.get_text(strip=True) or "Chapter",
                    })
                if result:
                    return result
        return []


# ------------------------------------------------------------------ factory

def get_config_parsers() -> list:
    """Return one ConfigParser instance per site config."""
    return [ConfigParser(cfg) for cfg in SITE_CONFIGS]
