import re
from .base_parser import BaseParser


class FanFictionParser(BaseParser):
    site_name = "FanFiction.net"
    url_patterns = [r"fanfiction\.net/s/"]

    def get_book_info(self, url: str, soup) -> dict:
        profile = soup.select_one("div#profile_top")

        title = ""
        author = ""
        description = ""
        if profile:
            b = profile.find("b")
            title = b.get_text(strip=True) if b else ""
            a_tag = profile.find("a", href=re.compile(r"^/u/"))
            author = a_tag.get_text(strip=True) if a_tag else ""
            desc_el = profile.select_one("div.xcontrast_txt")
            description = desc_el.get_text(strip=True) if desc_el else ""

        # Cover image
        cover_url = ""
        img = soup.select_one("div#img_large img")
        if img:
            cover_url = img.get("data-original") or img.get("src") or ""
        elif profile:
            img2 = profile.find("img")
            if img2:
                cover_url = img2.get("src") or ""
        if cover_url:
            cover_url = self.absolute_url(url, cover_url)

        # Chapter list from select dropdown
        story_id = re.search(r"/s/(\d+)/", url)
        story_id = story_id.group(1) if story_id else ""

        chapters = []
        select = soup.select_one("select#chap_select")
        if select and story_id:
            for opt in select.find_all("option"):
                ch_num = opt.get("value", "")
                ch_title = opt.get_text(strip=True)
                if ch_num:
                    ch_url = f"https://www.fanfiction.net/s/{story_id}/{ch_num}/"
                    chapters.append({"url": ch_url, "title": ch_title or f"Chapter {ch_num}"})
        else:
            # Single chapter
            chapters = [{"url": url, "title": title or "Chapter 1"}]

        return {
            "title": title,
            "author": author,
            "description": description,
            "cover_url": cover_url,
            "tags": "",
            "chapters": chapters,
        }

    def get_chapter_content(self, url: str, soup) -> str:
        el = soup.select_one("div#storytext") or soup.select_one("div.storytext")
        return self.element_to_text(el)
