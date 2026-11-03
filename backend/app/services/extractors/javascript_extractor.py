from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_javascript as tsjavascript

from app.services.extractors.base_extractor import BaseExtractor
from app.services.extractors.js_imports import build_js_import_query, extract_js_imports

JS_LANGUAGE = Language(tsjavascript.language())

# Shared import query (see js_imports.py), compiled for this grammar.
JS_IMPORT_QUERY = build_js_import_query(JS_LANGUAGE)

# Same query proven out on sample.js earlier. Unlike Python, JS's grammar
# already separates function/method/arrow-function by node type, so we
# don't need a parent-check here - just distinct capture labels per kind.
JAVASCRIPT_QUERY = Query(JS_LANGUAGE, """
(function_declaration
  name: (identifier) @function.name) @function.def

(method_definition
  name: (property_identifier) @method.name) @method.def

(class_declaration
  name: (identifier) @class.name) @class.def

(variable_declarator
  name: (identifier) @arrow.name
  value: (arrow_function)) @arrow.def
""")


class JavaScriptExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(JS_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(JAVASCRIPT_QUERY)

        kind_map = {
            "function.def": ("function.name", "function"),
            "method.def": ("method.name", "method"),
            "class.def": ("class.name", "class"),
            "arrow.def": ("arrow.name", "function"),
        }

        entities = []
        for pattern_index, match in cursor.matches(tree.root_node):
            for def_key, (name_key, kind) in kind_map.items():
                if def_key in match:
                    def_node = match[def_key][0]
                    name_node = match[name_key][0]
                    entities.append({
                        "name": name_node.text.decode("utf-8"),
                        "kind": kind,
                        "start_line": def_node.start_point[0] + 1,
                        "end_line": def_node.end_point[0] + 1,
                    })

        imports = extract_js_imports(tree.root_node, JS_IMPORT_QUERY)

        return {"language": "javascript", "entities": entities, "imports": imports}
