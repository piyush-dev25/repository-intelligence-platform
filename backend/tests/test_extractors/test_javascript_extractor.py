from app.services.extractors.javascript_extractor import JavaScriptExtractor


def test_javascript_extractor():
    extractor = JavaScriptExtractor()
    with open("tests/fixtures/sample.js", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "javascript"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        ("greet", "function"),
        ("add", "function"),
        ("UserService", "class"),
        ("getUser", "method"),
    }
    assert result["imports"] == ['import { readFile } from "fs";']