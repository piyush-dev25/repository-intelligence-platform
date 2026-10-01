from app.services.extractors.python_extractor import PythonExtractor


def test_python_extractor():
    extractor = PythonExtractor()
    with open("tests/fixtures/sample.py", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "python"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        ("LLMService", "class"),
        ("__init__", "method"),
        ("generate", "method"),
    }
    assert result["imports"] == []