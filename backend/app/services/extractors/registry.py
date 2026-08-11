from pathlib import Path

from app.services.extractors.base_extractor import BaseExtractor
from app.services.extractors.python_extractor import PythonExtractor
from app.services.extractors.javascript_extractor import JavaScriptExtractor
from app.services.extractors.typescript_extractor import TypeScriptExtractor

# One shared instance per extractor, same reasoning as llm_service's shared
# client - each extractor just wraps a Parser, no per-file state to reset,
# so reusing one instance across every file of that language is safe.
_EXTENSION_TO_EXTRACTOR: dict[str, BaseExtractor] = {
    ".py": PythonExtractor(),
    ".js": JavaScriptExtractor(),
    ".ts": TypeScriptExtractor(),
}


def get_extractor(file_path: str) -> BaseExtractor | None:
    """
    Looks up the right extractor for a file based on its extension.
    Returns None for unsupported extensions - callers decide what that
    means (skip the file, log it, etc.), this function just answers
    "do we support this file type," not "what happens if we don't."
    """
    extension = Path(file_path).suffix
    return _EXTENSION_TO_EXTRACTOR.get(extension)