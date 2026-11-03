from app.services.extractors.html_extractor import HtmlExtractor


def test_html_extractor():
    extractor = HtmlExtractor()
    with open("tests/fixtures/sample.html", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "html"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        ("main-nav", "element"),
        ("toggle-btn", "element"),
        ("signup-form", "element"),
        ("main", "element"),
    }
    assert result["imports"] == [
        {"module": "styles.css", "names": [], "is_relative": True, "line": 4},
        {"module": "app.js", "names": [], "is_relative": True, "line": 15},
    ]