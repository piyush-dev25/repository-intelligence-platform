from app.services.extractors.typescript_extractor import TypeScriptExtractor


def test_typescript_extractor():
    extractor = TypeScriptExtractor()
    with open("tests/fixtures/sample.ts", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "typescript"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        ("greet", "function"),
        ("add", "function"),
        ("User", "interface"),
        ("UserService", "class"),
        ("getUser", "method"),
    }
    assert len(result["imports"]) == 2

