from tree_sitter import Language, Parser, QueryCursor, Query
from app.services.extractors.base_extractor import BaseExtractor
from app.services.extractors.typescript_extractor import TYPESCRIPT_QUERY
import tree_sitter_typescript as tstypescript

# TSX grammar - same query as plain TypeScript works unchanged (JSX
# nodes nest inside expressions, don't affect function/class/interface
# structure), but the underlying grammar differs, so parsing needs its
# own Language/Parser.
TSX_LANGUAGE = Language(tstypescript.language_tsx())

# Same query TEXT as plain TypeScript (proven to work identically on
# TSX's structure), but must be compiled fresh against TSX_LANGUAGE -
# a Query object is tied to the specific Language it's built with, even
# when node type names are identical across grammars.
TSX_QUERY = Query(TSX_LANGUAGE, """
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

class TsxExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(TSX_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(TSX_QUERY)

        kind_map = {
            "function.def": ("function.name", "function"),
            "method.def": ("method.name", "method"),
            "class.def": ("class.name", "class"),
            "arrow.def": ("arrow.name", "function"),
            "interface.def": ("interface.name", "interface"),
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

        imports = []
        for pattern_index, match in cursor.matches(tree.root_node):
            if "import.statement" in match:
                imports.append(match["import.statement"][0].text.decode("utf-8"))

        return {"language": "tsx", "entities": entities, "imports": imports}

