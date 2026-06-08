import time


MODEL = "claude-haiku-4-5-20251001"
MAX_CHUNK = 80_000
OVERLAP = 500

CLEAN_SYSTEM = (
    "You are a professional copy editor. Your task is to improve the grammar, "
    "punctuation, and readability of the provided text without altering its meaning, "
    "story content, characters, or plot. Fix sentence structure, remove redundancy, "
    "improve flow between sentences, and ensure consistent tense. "
    "Return only the corrected text with no commentary or explanation."
)

REWRITE_SYSTEM = (
    "You are a skilled literary editor. Your task is to rewrite the provided text "
    "to significantly improve its clarity, engagement, and readability while "
    "preserving every plot point, character action, and story detail. "
    "Improve word choice, vary sentence length for rhythm, and ensure smooth transitions. "
    "Return only the rewritten text with no commentary or explanation."
)


class AIProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def test_connection(self) -> bool:
        try:
            client = self._get_client()
            client.messages.create(
                model=MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False

    def clean_chapter(self, text: str, progress_cb=None) -> str:
        return self._process(text, CLEAN_SYSTEM, progress_cb)

    def rewrite_chapter(self, text: str, style_notes: str = "", progress_cb=None) -> str:
        system = REWRITE_SYSTEM
        if style_notes:
            system += f"\n\nAdditional style guidance: {style_notes}"
        return self._process(text, system, progress_cb)

    def _process(self, text: str, system: str, progress_cb=None) -> str:
        if len(text) <= MAX_CHUNK:
            return self._call_api(text, system)

        # Split into overlapping chunks
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + MAX_CHUNK, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - OVERLAP

        results = []
        for i, chunk in enumerate(chunks):
            if progress_cb:
                progress_cb(i, len(chunks))
            result = self._call_api(chunk, system)
            if i > 0 and results:
                # Strip overlap from previous result's end
                results[-1] = results[-1][:-OVERLAP // 2]
            results.append(result)

        return "".join(results)

    def _call_api(self, text: str, system: str, retries: int = 3) -> str:
        client = self._get_client()
        for attempt in range(retries):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=8192,
                    system=system,
                    messages=[{"role": "user", "content": text}],
                )
                return response.content[0].text
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
        return text
