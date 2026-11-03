import time

from groq import Groq
from groq import RateLimitError, APIError, AuthenticationError

from app.core.config import GROQ_API_KEY, GROQ_MODEL


class DailyLimitReached(Exception):
    """Raised when the LLM provider's daily quota is exhausted - distinct
    from a per-minute rate limit, which is worth retrying/waiting for."""
    pass


class LLMNotConfiguredError(Exception):
    """Raised when the LLM can't be used at all - missing or rejected API
    key. A setup problem, not a per-file one: callers should stop, not
    retry file by file."""
    pass


class LLMService:
    # Doesn't touch the API key yet - so the app and tests can start
    # without one. The key is checked on the first generate() call.
    def __init__(self) -> None:
        self.client: Groq | None = None
        self.model = GROQ_MODEL

    # Creates the Groq client on first use and reuses it after that.
    # Raises a clear setup error if the key is missing.
    def _get_client(self) -> Groq:
        if self.client is None:
            if not GROQ_API_KEY:
                raise LLMNotConfiguredError("GROQ_API_KEY is not configured. Add it to backend/.env.")
            self.client = Groq(api_key=GROQ_API_KEY)
        return self.client

    def generate(self, prompt: str, max_retries: int = 3) -> str:
        client = self._get_client()
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
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
            # Must come before APIError - AuthenticationError is a subclass of it.
            except AuthenticationError as exc:
                raise LLMNotConfiguredError(
                    "Groq rejected the API key (authentication failed). Check GROQ_API_KEY in backend/.env."
                ) from exc
            except APIError as exc:
                raise RuntimeError(f"LLM request failed: {exc}") from exc


llm_service = LLMService()