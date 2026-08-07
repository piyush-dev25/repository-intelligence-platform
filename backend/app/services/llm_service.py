from google import genai
from google.genai.errors import ClientError

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL


# Wraps our LLM provider (currently Gemini) behind one simple interface.
# Every part of the app that needs an LLM call goes through this class,
# not the provider's SDK directly - so swapping providers later means
# changing this one file, not every call site.
class LLMService:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        except ClientError as exc:
            # Don't let Gemini-specific errors leak to callers - they
            # should only ever need to catch RuntimeError, regardless
            # of which provider is actually behind this class.
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        return response.text


# One shared instance, created once when this module is first imported -
# every caller reuses this same client instead of creating a new one
# per call.
llm_service = LLMService()