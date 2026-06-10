import re
from collections import Counter


class TextCleaner:
    """Rule-based text cleaner for ebook content."""

    def __init__(self, custom_rules: list = None):
        self._custom_rules = custom_rules or []

    def clean(self, text: str) -> str:
        text = self._fix_encoding(text)
        text = self._fix_broken_hyphenation(text)
        text = self._remove_page_numbers(text)
        text = self._remove_repeated_headers(text)
        text = self._remove_garbage_lines(text)
        text = self._fix_ocr_artifacts(text)
        text = self._normalize_whitespace(text)
        text = self._apply_custom_rules(text)
        return text.strip()

    def _apply_custom_rules(self, text: str) -> str:
        for rule in self._custom_rules:
            if not rule.get("enabled", True):
                continue
            pattern = rule.get("pattern", "")
            if not pattern:
                continue
            replacement = rule.get("replacement", "")
            try:
                if rule.get("is_regex"):
                    text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
                else:
                    text = text.replace(pattern, replacement)
            except re.error:
                pass
        return text

    def _fix_encoding(self, text: str) -> str:
        replacements = {
            "‘": "'", "’": "'",
            "“": '"', "”": '"',
            "–": "-", "—": "--",
            "…": "...",
            " ": " ",
            "�": "",
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)
        return text

    def _fix_broken_hyphenation(self, text: str) -> str:
        # "re-\njoined" -> "rejoined"
        text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
        # word\ncontinuation (no hyphen, just line break mid-paragraph)
        text = re.sub(r"([a-z,;])\n([a-z])", r"\1 \2", text)
        return text

    def _remove_page_numbers(self, text: str) -> str:
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Pure number line
            if re.fullmatch(r"\d+", stripped):
                continue
            # "Page X", "Page X of Y", "- X -"
            if re.fullmatch(r"(?:page\s+)?\d+(?:\s+of\s+\d+)?", stripped, re.IGNORECASE):
                continue
            if re.fullmatch(r"-\s*\d+\s*-", stripped):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _remove_repeated_headers(self, text: str) -> str:
        lines = text.split("\n")
        if len(lines) < 10:
            return text

        # Count occurrences of short lines (potential headers/footers)
        short_lines = [l.strip() for l in lines if 1 <= len(l.strip()) <= 80]
        freq = Counter(short_lines)

        # Lines appearing 3+ times and are short are likely headers/footers
        repeated = {line for line, count in freq.items() if count >= 3 and len(line) < 80}

        cleaned = []
        for line in lines:
            if line.strip() in repeated:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _remove_garbage_lines(self, text: str) -> str:
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                cleaned.append(line)
                continue
            # Line is mostly non-alphanumeric (e.g., "* * * * *", "--------")
            alnum_ratio = sum(c.isalnum() or c.isspace() for c in stripped) / len(stripped)
            if alnum_ratio < 0.4 and len(stripped) < 30:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _fix_ocr_artifacts(self, text: str) -> str:
        # Common OCR substitutions
        # "l" mistaken for "I" at word start before lowercase
        text = re.sub(r"\bl([a-z])", lambda m: "I" + m.group(1) if m.group(1).islower() else m.group(0), text)
        # "0" mistaken for "O" in all-alpha context — too risky to auto-fix broadly
        # Fix "rn" confused as "m"
        # Fix double spaces within words
        text = re.sub(r"(\w) {2,}(\w)", r"\1 \2", text)
        # Remove null bytes / control chars (except newline/tab)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        # Trim trailing whitespace per line
        lines = [l.rstrip() for l in text.split("\n")]
        text = "\n".join(lines)
        # Collapse 3+ consecutive blank lines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Normalize multiple spaces to single
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text
