from app.services.extractors.css_extractor import CssExtractor
from app.services.extractors.html_extractor import HtmlExtractor
from app.services.extractors.javascript_extractor import JavaScriptExtractor
from app.services.extractors.python_extractor import PythonExtractor
from app.services.extractors.tsx_extractor import TsxExtractor
from app.services.extractors.typescript_extractor import TypeScriptExtractor


# Shorthand for one expected import entry.
def imp(module, names, is_relative, line):
    return {"module": module, "names": names, "is_relative": is_relative, "line": line}


# Runs an extractor on a fixture from tests/fixtures/imports/ and returns its imports.
def imports_of(extractor, fixture_name):
    with open(f"tests/fixtures/imports/{fixture_name}", "rb") as f:
        return extractor.extract(f.read())["imports"]


def test_python_imports():
    assert imports_of(PythonExtractor(), "sample.py") == [
        imp("os", [], False, 1),               # import os, sys -> two entries
        imp("sys", [], False, 1),
        imp("a.b", [], False, 2),              # alias dropped, names stay empty
        imp(".", ["sibling"], True, 3),        # leading dots kept as written
        imp("..models", ["User", "Repo"], True, 4),  # original name, not alias "R"
        imp(".utils", ["helper"], True, 5),
        imp("x", ["*"], False, 6),
        imp("json", [], False, 10),            # import inside a function
    ]


def test_javascript_imports():
    assert imports_of(JavaScriptExtractor(), "sample.js") == [
        imp("react", ["default"], False, 1),
        imp("fs", ["readFile", "writeFile"], False, 2),  # original name, not alias "wf"
        imp("path", ["*"], False, 3),
        imp("./polyfill", [], True, 4),                  # side-effect import
        imp("../lib/thing", ["default", "named"], True, 5),
        imp("lodash", [], False, 6),                     # CommonJS require
        imp("./helpers", ["helper"], True, 7),           # re-export
        imp("./all", ["*"], True, 8),                    # export * from
        imp("./local", [], True, 11),                    # require inside a function
        # NOT captured: require(name), import("./dynamic"), export { lazy }
    ]


TS_EXPECTED = [
    imp("./types", ["User"], True, 1),                   # import type
    imp("@/components/button", ["Button"], False, 2),    # alias - not relative, resolved in 5.4
    imp("./render", ["Props", "render"], True, 3),       # inline `type` keyword ignored
    imp("fs", [], False, 4),                             # TS import x = require("y")
    imp("./config", ["Config"], True, 5),                # export type { } from
    imp("/abs/path", [], True, 6),                       # require with absolute path
]


def test_typescript_imports():
    assert imports_of(TypeScriptExtractor(), "sample.ts") == TS_EXPECTED


def test_tsx_uses_same_import_logic():
    assert imports_of(TsxExtractor(), "sample.ts") == TS_EXPECTED


def test_html_imports():
    assert imports_of(HtmlExtractor(), "sample.html") == [
        imp("css/site.css", [], True, 4),
        imp("https://cdn.example.com/lib.css", [], False, 5),     # self-closing <link />
        imp("//cdn.example.com/favicon.ico", [], False, 6),       # protocol-relative
        imp("data:,", [], False, 7),
        imp("js/app.js", [], True, 10),
        imp("http://cdn.example.com/lib.js", [], False, 11),
        # NOT captured: inline <script> with no src
    ]


def test_css_imports():
    assert imports_of(CssExtractor(), "sample.css") == [
        imp("base.css", [], True, 1),                             # @import "x"
        imp("theme/dark.css", [], True, 2),                       # @import url("x")
        imp("print.css", [], True, 3),                            # @import url(x) unquoted
        imp("https://fonts.example.com/font.css", [], False, 4),
    ]
