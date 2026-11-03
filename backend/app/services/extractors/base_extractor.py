from abc import ABC, abstractmethod


# The contract every language extractor must follow. Anything that
# calls an extractor (e.g. the file analysis pipeline in Phase 4)
# only needs to know about this interface - not which language
# it's actually dealing with under the hood.
class BaseExtractor(ABC):

    @abstractmethod

    def extract(self, source_code: bytes) -> dict:
        
        # Takes raw file bytes, returns a dict matching our locked shape:
        # {"language": str, "entities": [...], "imports": [...]}
        # Each import is {"module": str, "names": list[str],
        # "is_relative": bool, "line": int} - module exactly as written
        # in the source, line 1-based.
        # Every subclass must implement this - ABC + abstractmethod means
        # Python won't let BaseExtractor itself be instantiated directly.
        
        pass