from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_python as tspython

from app.services.extractors.base_extractor import BaseExtractor

PY_LANGUAGE = Language(tspython.language())

# The query pattern proven out in earlier testing - one pattern per
# construct we care about, all run together in a single QueryCursor pass.
PYTHON_QUERY = Query(PY_LANGUAGE, """
(function_definition
  name: (identifier) @function.name) @function.def

(class_definition
  name: (identifier) @class.name)

(import_statement) @import.statement

(import_from_statement) @import.statement
""")


class PythonExtractor(BaseExtractor):
    def __init__(self) -> None:
        # Parser is created once per extractor instance, reused across
        # every extract() call - same reasoning as llm_service's shared client.
        self.parser = Parser(PY_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(PYTHON_QUERY)
        captures = cursor.captures(tree.root_node)

        entities = []

        # We capture both @function.def (whole node) and @function.name
        # (just the identifier) for the same function - we need the whole
        # node to run the parent-check, and the name node to get the text.
        function_defs = captures.get("function.def", [])
        function_names = captures.get("function.name", [])

        for def_node, name_node in zip(function_defs, function_names):
            # Python wraps class bodies in a generic "block" node before
            # class_definition - confirmed earlier by inspecting the tree.
            # So checking one level up (def_node.parent) always lands on
            # "block", regardless of whether it's a class or not. We have
            # to go up two levels to reach class_definition itself.
            is_method = (
                def_node.parent is not None
                and def_node.parent.parent is not None
                and def_node.parent.parent.type == "class_definition"
            )
            entities.append({
                "name": name_node.text.decode("utf-8"),
                "kind": "method" if is_method else "function",
                "start_line": def_node.start_point[0] + 1,  # tree-sitter is 0-indexed, files aren't
                "end_line": def_node.end_point[0] + 1,
            })

        for node in captures.get("class.name", []):
            # class.name only captures the identifier, not the whole
            # class_definition - we need the parent to get start/end lines
            # covering the whole class, not just its name token.
            class_node = node.parent
            entities.append({
                "name": node.text.decode("utf-8"),
                "kind": "class",
                "start_line": class_node.start_point[0] + 1,
                "end_line": class_node.end_point[0] + 1,
            })

        imports = [
            node.text.decode("utf-8")
            for node in captures.get("import.statement", [])
        ]

        return {
            "language": "python",
            "entities": entities,
            "imports": imports,
        }
