import time

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI    = "gemini"
PROVIDER_GROQ      = "groq"
PROVIDER_OLLAMA    = "ollama"

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
GEMINI_MODEL    = "gemini-1.5-flash"
GROQ_MODEL      = "llama-3.3-70b-versatile"

MAX_CHUNK = 80_000
OVERLAP   = 500

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
    def __init__(self, provider: str = PROVIDER_ANTHROPIC, api_key: str = "",
                 ollama_host: str = "http://localhost:11434",
                 ollama_model: str = "llama3.1"):
        self.provider     = provider
        self.api_key      = api_key
        self.ollama_host  = ollama_host.rstrip("/")
        self.ollama_model = ollama_model
        self._client      = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if self.provider == PROVIDER_ANTHROPIC:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)

        elif self.provider == PROVIDER_GEMINI:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)

        elif self.provider == PROVIDER_GROQ:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1",
            )

        elif self.provider == PROVIDER_OLLAMA:
            from openai import OpenAI
            self._client = OpenAI(
                api_key="ollama",
                base_url=f"{self.ollama_host}/v1",
            )

        return self._client

    def is_configured(self) -> bool:
        if self.provider == PROVIDER_OLLAMA:
            return True
        return bool(self.api_key and self.api_key.strip())

    def test_connection(self) -> tuple:
        """Returns (success: bool, error_message: str)."""
        try:
            client = self._get_client()

            if self.provider == PROVIDER_ANTHROPIC:
                client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}],
                )

            elif self.provider == PROVIDER_GEMINI:
                from google.genai import types as _gtypes
                client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents="Hi",
                    config=_gtypes.GenerateContentConfig(max_output_tokens=10),
                )

            elif self.provider in (PROVIDER_GROQ, PROVIDER_OLLAMA):
                model = GROQ_MODEL if self.provider == PROVIDER_GROQ else self.ollama_model
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=10,
                )

            return True, ""
        except Exception as e:
            return False, str(e)

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
                results[-1] = results[-1][:-OVERLAP // 2]
            results.append(result)

        return "".join(results)

    def _call_api(self, text: str, system: str, retries: int = 3) -> str:
        client = self._get_client()
        for attempt in range(retries):
            try:
                if self.provider == PROVIDER_ANTHROPIC:
                    response = client.messages.create(
                        model=ANTHROPIC_MODEL,
                        max_tokens=8192,
                        system=system,
                        messages=[{"role": "user", "content": text}],
                    )
                    return response.content[0].text

                elif self.provider == PROVIDER_GEMINI:
                    from google.genai import types as _gtypes
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=text,
                        config=_gtypes.GenerateContentConfig(
                            system_instruction=system,
                            max_output_tokens=8192,
                        ),
                    )
                    return response.text

                elif self.provider in (PROVIDER_GROQ, PROVIDER_OLLAMA):
                    model = GROQ_MODEL if self.provider == PROVIDER_GROQ else self.ollama_model
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user",   "content": text},
                        ],
                        max_tokens=8192,
                    )
                    return response.choices[0].message.content

            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise

        return text
