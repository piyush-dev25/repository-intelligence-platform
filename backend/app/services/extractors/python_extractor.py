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

        entities = []
        for pattern_index, match in cursor.matches(tree.root_node):
            if "function.def" in match:
                def_node = match["function.def"][0]
                name_node = match["function.name"][0]
                is_method = (
                    def_node.parent is not None
                    and def_node.parent.parent is not None
                    and def_node.parent.parent.type == "class_definition"
                )
                entities.append({
                    "name": name_node.text.decode("utf-8"),
                    "kind": "method" if is_method else "function",
                    "start_line": def_node.start_point[0] + 1,
                    "end_line": def_node.end_point[0] + 1,
                })
            elif "class.name" in match:
                name_node = match["class.name"][0]
                class_node = name_node.parent
                entities.append({
                    "name": name_node.text.decode("utf-8"),
                    "kind": "class",
                    "start_line": class_node.start_point[0] + 1,
                    "end_line": class_node.end_point[0] + 1,
                })

        imports = []
        for pattern_index, match in cursor.matches(tree.root_node):
            if "import.statement" in match:
                imports.append(match["import.statement"][0].text.decode("utf-8"))

        return {"language": "python", "entities": entities, "imports": imports}

