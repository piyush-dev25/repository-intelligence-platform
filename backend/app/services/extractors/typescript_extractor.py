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

        return {"language": "typescript", "entities": entities, "imports": imports}

