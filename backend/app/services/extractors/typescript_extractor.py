from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_typescript as tstypescript

from app.services.extractors.base_extractor import BaseExtractor

# tree_sitter_typescript exposes two grammars - plain TS and TSX.
# We want plain TS here; TSX is tracked separately (not built yet).
TS_LANGUAGE = Language(tstypescript.language_typescript())

# Same query proven out on sample.ts earlier. Two TS-specific differences
# from the JS query: class/interface names use type_identifier (not
# identifier), and interfaces get their own capture since they're not
# functions/classes/methods - see interface_declaration below.
TYPESCRIPT_QUERY = Query(TS_LANGUAGE, """
(function_declaration
  name: (identifier) @function.name) @function.def

(method_definition
  name: (property_identifier) @method.name) @method.def

(class_declaration
  name: (type_identifier) @class.name) @class.def

(variable_declarator
  name: (identifier) @arrow.name
  value: (arrow_function)) @arrow.def

(interface_declaration
  name: (type_identifier) @interface.name) @interface.def

(import_statement) @import.statement
""")


class TypeScriptExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(TS_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(TYPESCRIPT_QUERY)
        captures = cursor.captures(tree.root_node)

        entities = []
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
        entities += self._build_entities(
            captures.get("interface.def", []), captures.get("interface.name", []), "interface"
        )

        imports = [
            node.text.decode("utf-8")
            for node in captures.get("import.statement", [])
        ]

        return {
            "language": "typescript",
            "entities": entities,
            "imports": imports,
        }

    def _build_entities(self, def_nodes: list, name_nodes: list, kind: str) -> list:
        entities = []
        for def_node, name_node in zip(def_nodes, name_nodes):
            entities.append({
                "name": name_node.text.decode("utf-8"),
                "kind": kind,
                "start_line": def_node.start_point[0] + 1,
                "end_line": def_node.end_point[0] + 1,
            })
        return entities

