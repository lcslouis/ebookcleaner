import re
import os
from html.parser import HTMLParser


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip_tags = {"script", "style", "head"}
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
        if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def get_text(self):
        return "".join(self._parts)


def strip_html(html_content):
    parser = _HTMLStripper()
    try:
        parser.feed(html_content)
    except Exception:
        return html_content
    return parser.get_text()


class EbookParser:
    def parse(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".epub":
            return self._parse_epub(file_path)
        elif ext == ".txt":
            return self._parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_epub(self, file_path):
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise ImportError("ebooklib is required: pip install ebooklib")

        book = epub.read_epub(file_path)

        title = book.get_metadata("DC", "title")
        title = title[0][0] if title else os.path.splitext(os.path.basename(file_path))[0]

        author = book.get_metadata("DC", "creator")
        author = author[0][0] if author else ""

        description = book.get_metadata("DC", "description")
        description = description[0][0] if description else ""

        chapters = []
        chapter_num = 1

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content_bytes = item.get_content()
            try:
                html = content_bytes.decode("utf-8", errors="replace")
            except Exception:
                html = str(content_bytes)

            text = strip_html(html)
            text = self._clean_whitespace(text)

            if len(text.strip()) < 50:
                continue

            chapter_title = self._extract_heading(html) or f"Chapter {chapter_num}"

            chapters.append({
                "number": chapter_num,
                "title": chapter_title,
                "content": text.strip(),
            })
            chapter_num += 1

        return {
            "title": title,
            "author": author,
            "description": description,
            "chapters": chapters,
        }

    def _parse_txt(self, file_path):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        title = os.path.splitext(os.path.basename(file_path))[0]

        # Split on chapter headings
        chapter_pattern = re.compile(
            r"(?:^|\n)((?:chapter|ch\.?|part|book|section|prologue|epilogue|introduction|preface)"
            r"[\s\.\-]*(?:\d+|\w+)?[^\n]*)\n",
            re.IGNORECASE
        )

        matches = list(chapter_pattern.finditer(raw))

        if not matches:
            # No headings — split on double newlines into reasonable chunks
            return self._parse_txt_by_blocks(raw, title)

        chapters = []
        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            content = raw[start:end].strip()
            if len(content) < 50:
                continue
            chapters.append({
                "number": i + 1,
                "title": heading,
                "content": content,
            })

        if not chapters:
            return self._parse_txt_by_blocks(raw, title)

        return {"title": title, "author": "", "description": "", "chapters": chapters}

    def _parse_txt_by_blocks(self, raw, title):
        paragraphs = re.split(r"\n{3,}", raw)
        chapters = []
        chapter_size = max(1, len(paragraphs) // 20)  # aim for ~20 chapters max

        for i in range(0, len(paragraphs), chapter_size):
            block = "\n\n".join(paragraphs[i:i + chapter_size]).strip()
            if len(block) < 50:
                continue
            num = len(chapters) + 1
            first_line = block.split("\n")[0][:60].strip()
            chapters.append({
                "number": num,
                "title": first_line or f"Section {num}",
                "content": block,
            })

        if not chapters:
            chapters = [{"number": 1, "title": "Full Text", "content": raw.strip()}]

        return {"title": title, "author": "", "description": "", "chapters": chapters}

    def _extract_heading(self, html):
        m = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.IGNORECASE | re.DOTALL)
        if m:
            return strip_html(m.group(1)).strip()
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if m:
            text = strip_html(m.group(1)).strip()
            if text and text.lower() not in ("untitled", ""):
                return text
        return None

    def _clean_whitespace(self, text):
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text
