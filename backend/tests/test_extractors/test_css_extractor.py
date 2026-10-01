from app.services.extractors.css_extractor import CssExtractor


def test_css_extractor():
    extractor = CssExtractor()
    with open("tests/fixtures/sample.css", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "css"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        (".container", "selector"),
        ("#header", "selector"),
        ("button:hover", "selector"),
    }
    assert result["imports"] == ['@import url("reset.css");']