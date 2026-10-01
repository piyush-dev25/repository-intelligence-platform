import time

from groq import Groq
from groq import RateLimitError, APIError

from app.core.config import GROQ_API_KEY, GROQ_MODEL


class DailyLimitReached(Exception):
    """Raised when the LLM provider's daily quota is exhausted - distinct
    from a per-minute rate limit, which is worth retrying/waiting for."""
    pass


class LLMService:
    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    def generate(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.choices[0].message.content
            except RateLimitError as exc:
                if "per day" in str(exc).lower() or "rpd" in str(exc).lower():
                    raise DailyLimitReached(str(exc)) from exc
                if attempt == max_retries - 1:
                    raise RuntimeError(f"LLM request failed after {max_retries} attempts: {exc}") from exc
                time.sleep(2 ** attempt)
            except APIError as exc:
                raise RuntimeError(f"LLM request failed: {exc}") from exc


llm_service = LLMService()