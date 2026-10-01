from app.services.extractors.tsx_extractor import TsxExtractor


def test_tsx_extractor():
    extractor = TsxExtractor()
    with open("tests/fixtures/sample.tsx", "rb") as f:
        result = extractor.extract(f.read())

    assert result["language"] == "tsx"

    names_and_kinds = {(e["name"], e["kind"]) for e in result["entities"]}
    assert names_and_kinds == {
        ("GreetingProps", "interface"),
        ("Greeting", "function"),
        ("Farewell", "function"),
    }
    assert result["imports"] == ['import React from "react";']