from difflib import SequenceMatcher


TITLE_MATCH_THRESHOLD = 0.75
CONTENT_MATCH_THRESHOLD = 0.85


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _content_fingerprint(text: str) -> str:
    """Return first 500 chars of text, normalized."""
    return " ".join(text.split())[:500]


class ChapterMerger:
    def analyze(self, existing_chapters: list, new_chapters: list) -> dict:
        """
        Compare existing chapters against a newly imported set.
        Returns dict with keys:
          - 'new': chapters in new_chapters with no match in existing
          - 'updated': chapters that appear modified
          - 'unchanged': chapters that match existing
        Each entry is the chapter dict from new_chapters, plus an 'existing_id' key
        for updated/unchanged items.
        """
        new_list = []
        updated_list = []
        unchanged_list = []

        for new_ch in new_chapters:
            match = self._find_match(new_ch, existing_chapters)
            if match is None:
                new_list.append(new_ch)
            else:
                existing = match
                content_sim = _similarity(
                    _content_fingerprint(new_ch["content"]),
                    _content_fingerprint(existing.get("original_content", "")),
                )
                entry = dict(new_ch)
                entry["existing_id"] = existing["id"]
                entry["existing_chapter_number"] = existing["chapter_number"]
                if content_sim >= CONTENT_MATCH_THRESHOLD:
                    unchanged_list.append(entry)
                else:
                    updated_list.append(entry)

        return {"new": new_list, "updated": updated_list, "unchanged": unchanged_list}

    def _find_match(self, new_ch: dict, existing_chapters: list):
        best_score = 0
        best_match = None
        for ex in existing_chapters:
            title_sim = _similarity(new_ch.get("title", ""), ex.get("title", ""))
            if title_sim > best_score:
                best_score = title_sim
                best_match = ex
        if best_score >= TITLE_MATCH_THRESHOLD:
            return best_match
        # Fallback: compare chapter numbers
        for ex in existing_chapters:
            if ex.get("chapter_number") == new_ch.get("number"):
                return ex
        return None

    def merge(self, book_id: int, analysis: dict, db, include_updated: bool = True):
        """
        Actually write merged chapters to the database.
        - 'new' chapters are appended after the last existing chapter.
        - 'updated' chapters replace existing content (original_content only; preserves cleaned/rewritten).
        """
        max_num = db.get_max_chapter_number(book_id)

        for ch in analysis["new"]:
            max_num += 1
            db.add_chapter(book_id, max_num, ch["title"], ch["content"])

        if include_updated:
            for ch in analysis["updated"]:
                db.update_chapter(
                    ch["existing_id"],
                    original_content=ch["content"],
                    title=ch["title"],
                    status="original",
                )
