from app.services.extractors.registry import get_extractor
from app.services.extractors.python_extractor import PythonExtractor
from app.services.extractors.javascript_extractor import JavaScriptExtractor
from app.services.extractors.typescript_extractor import TypeScriptExtractor


def test_python_extension_returns_python_extractor():
    extractor = get_extractor("foo.py")
    assert isinstance(extractor, PythonExtractor)


def test_javascript_extension_returns_javascript_extractor():
    extractor = get_extractor("bar.js")
    assert isinstance(extractor, JavaScriptExtractor)


def test_typescript_extension_returns_typescript_extractor():
    extractor = get_extractor("baz.ts")
    assert isinstance(extractor, TypeScriptExtractor)


def test_unsupported_extension_returns_none():
    extractor = get_extractor("script.rb")
    assert extractor is None


def test_path_with_directories_still_resolves_correctly():
    # Confirms get_extractor cares about the extension, not just a bare
    # filename - Path(...).suffix should handle nested paths correctly.
    extractor = get_extractor("app/services/some_module.py")
    assert isinstance(extractor, PythonExtractor)