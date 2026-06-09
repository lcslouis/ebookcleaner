import uuid
import re
from pathlib import Path
from ebooklib import epub


# ------------------------------------------------------------------ text→XHTML

def _esc(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _text_to_xhtml(text: str, title: str) -> str:
    paragraphs_html = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        # Short lines without a period at end → treat as heading
        if len(para) < 80 and not para.endswith((".", "!", "?", ",", ";")):
            paragraphs_html.append(f"<h3>{_esc(para)}</h3>")
        else:
            inner = "<br/>".join(_esc(line) for line in para.split("\n") if line.strip())
            if inner:
                paragraphs_html.append(f"<p>{inner}</p>")

    body = "\n".join(paragraphs_html) or f"<p></p>"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f'<head><title>{_esc(title)}</title>\n'
        '<link rel="stylesheet" type="text/css" href="../Styles/style.css"/>\n'
        "</head>\n<body>\n"
        f"<h1 class=\"chapter-title\">{_esc(title)}</h1>\n"
        f"{body}\n"
        "</body>\n</html>"
    )


# ------------------------------------------------------------------ stylesheet

STYLESHEET = """
body {
    font-family: Georgia, serif;
    font-size: 1em;
    line-height: 1.6;
    margin: 1em 1.5em;
    color: #1a1a1a;
}
h1.chapter-title {
    font-size: 1.4em;
    margin-bottom: 1em;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.3em;
}
h3 {
    font-size: 1.1em;
    margin-top: 1em;
}
p {
    margin: 0.5em 0;
    text-indent: 1.5em;
}
p:first-of-type {
    text-indent: 0;
}
"""


# ------------------------------------------------------------------ exporter

class EpubExporter:
    def export(
        self,
        book_id: int,
        db,
        output_path: str,
        content_version: str = "cleaned",
        cover_data: bytes = None,
        cover_mime: str = "image/jpeg",
    ) -> int:
        """
        Export book to EPUB. Returns number of chapters written.
        content_version: 'original' | 'cleaned' | 'rewritten'
        """
        book_data = db.get_book(book_id)
        if not book_data:
            raise ValueError(f"Book {book_id} not found")

        chapters = db.get_chapters(book_id)
        if not chapters:
            raise ValueError("No chapters to export")

        eb = epub.EpubBook()
        eb.set_identifier(str(uuid.uuid4()))
        eb.set_title(book_data["title"] or "Untitled")
        eb.set_language("en")
        eb.add_author(book_data["author"] or "Unknown Author")
        if book_data.get("description"):
            eb.add_metadata("DC", "description", book_data["description"])
        if book_data.get("source_url"):
            eb.add_metadata("DC", "source", book_data["source_url"])

        # Stylesheet
        css_item = epub.EpubItem(
            uid="style",
            file_name="Styles/style.css",
            media_type="text/css",
            content=STYLESHEET.encode("utf-8"),
        )
        eb.add_item(css_item)

        # Cover image
        if cover_data:
            ext = "jpg" if "jpeg" in cover_mime else cover_mime.split("/")[-1]
            cover_item = epub.EpubItem(
                uid="cover-image",
                file_name=f"Images/cover.{ext}",
                media_type=cover_mime,
                content=cover_data,
            )
            eb.add_item(cover_item)
            eb.set_cover(f"Images/cover.{ext}", cover_data)

        # Chapters
        epub_chapters = []
        for ch in chapters:
            content = (
                ch.get(f"{content_version}_content") or
                ch.get("cleaned_content") or
                ch.get("original_content") or
                ""
            ).strip()
            if not content:
                continue

            ch_title = ch["title"] or f"Chapter {ch['chapter_number']}"
            xhtml = _text_to_xhtml(content, ch_title)
            filename = f"Text/chapter{ch['chapter_number']:04d}.xhtml"

            epub_ch = epub.EpubHtml(
                uid=f"chapter{ch['chapter_number']}",
                title=ch_title,
                file_name=filename,
                lang="en",
            )
            epub_ch.content = xhtml.encode("utf-8")
            epub_ch.add_item(css_item)
            eb.add_item(epub_ch)
            epub_chapters.append(epub_ch)

        if not epub_chapters:
            raise ValueError("No content to export — run cleaning or check chapter content")

        # TOC and spine
        eb.toc = [epub.Link(c.file_name, c.title, c.uid) for c in epub_chapters]
        eb.add_item(epub.EpubNcx())
        eb.add_item(epub.EpubNav())
        eb.spine = ["nav"] + epub_chapters

        epub.write_epub(output_path, eb, {})
        return len(epub_chapters)
