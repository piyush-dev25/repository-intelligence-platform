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
                imports.extend(_parse_python_import(match["import.statement"][0]))

        imports.sort(key=lambda entry: entry["line"])
        return {"language": "python", "entities": entities, "imports": imports}


# Turns one Python import statement into structured entries:
#   import os, sys            -> two entries, names []
#   from ..models import A, B -> module "..models" (dots kept), names ["A", "B"]
#   from x import *           -> names ["*"]
# Aliases are dropped - names are what the module actually exports.
def _parse_python_import(node) -> list[dict]:
    line = node.start_point[0] + 1

    if node.type == "import_statement":
        return [
            _make_python_import(_original_name(name_node), [], line)
            for name_node in node.children_by_field_name("name")
        ]

    module = node.child_by_field_name("module_name").text.decode("utf-8")
    if any(child.type == "wildcard_import" for child in node.children):
        names = ["*"]
    else:
        names = [_original_name(name_node) for name_node in node.children_by_field_name("name")]
    return [_make_python_import(module, names, line)]


# The real name behind a possibly-aliased import: "B" for `B as Bee`.
def _original_name(name_node) -> str:
    if name_node.type == "aliased_import":
        name_node = name_node.child_by_field_name("name")
    return name_node.text.decode("utf-8")


# Assembles one import dict. Relative = starts with "." (from . / from ..x).
def _make_python_import(module: str, names: list[str], line: int) -> dict:
    return {
        "module": module,
        "names": names,
        "is_relative": module.startswith("."),
        "line": line,
    }

