from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_javascript as tsjavascript

from app.services.extractors.base_extractor import BaseExtractor

JS_LANGUAGE = Language(tsjavascript.language())

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

(import_statement) @import.statement
""")


class JavaScriptExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(JS_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(JAVASCRIPT_QUERY)
        captures = cursor.captures(tree.root_node)

        entities = []

        # Each kind follows the same pattern: pair up the "whole node"
        # capture with the "name" capture, using the whole node for line
        # numbers and the name node for the text.
        entities += self._build_entities(
            captures.get("function.def", []), captures.get("function.name", []), "function"
        )
        entities += self._build_entities(
            captures.get("method.def", []), captures.get("method.name", []), "method"
        )
        entities += self._build_entities(
            captures.get("class.def", []), captures.get("class.name", []), "class"
        )
        entities += self._build_entities(
            captures.get("arrow.def", []), captures.get("arrow.name", []), "function"
        )

        imports = [
            node.text.decode("utf-8")
            for node in captures.get("import.statement", [])
        ]

        return {
            "language": "javascript",
            "entities": entities,
            "imports": imports,
        }

    def _build_entities(self, def_nodes: list, name_nodes: list, kind: str) -> list:
        # Shared helper since all four entity kinds follow the identical
        # "pair whole-node with name-node" shape - avoids repeating this
        # four times with only the kind string changing.
        entities = []
        for def_node, name_node in zip(def_nodes, name_nodes):
            entities.append({
                "name": name_node.text.decode("utf-8"),
                "kind": kind,
                "start_line": def_node.start_point[0] + 1,
                "end_line": def_node.end_point[0] + 1,
            })
        return entities


if __name__ == "__main__":
    # Run with: cd backend && python -m app.services.extractors.javascript_extractor
    extractor = JavaScriptExtractor()
    with open("app/services/extractors/sample.js", "rb") as f:
        source_code = f.read()
    result = extractor.extract(source_code)

    print("Language:", result["language"])
    print("Entities:")
    for entity in result["entities"]:
        print(" ", entity)
    print("Imports:")
    for imp in result["imports"]:
        print(" ", imp)