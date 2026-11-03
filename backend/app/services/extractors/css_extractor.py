from tree_sitter import Language, Parser, Query, QueryCursor
from app.services.extractors.base_extractor import BaseExtractor
import tree_sitter_css as tscss

CSS_LANGUAGE = Language(tscss.language())

CSS_QUERY = Query(CSS_LANGUAGE, """
(rule_set
  (selectors) @selector.name) @selector.def

(import_statement) @import.statement
""")


class CssExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(CSS_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
        tree = self.parser.parse(source_code)
        cursor = QueryCursor(CSS_QUERY)

        entities = []
        for pattern_index, match in cursor.matches(tree.root_node):
            if "selector.def" in match:
                def_node = match["selector.def"][0]
                name_node = match["selector.name"][0]
                entities.append({
                    "name": name_node.text.decode("utf-8"),
                    "kind": "selector",
                    "start_line": def_node.start_point[0] + 1,
                    "end_line": def_node.end_point[0] + 1,
                })

        imports = []
        for pattern_index, match in cursor.matches(tree.root_node):
            if "import.statement" in match:
                statement = match["import.statement"][0]
                module = _import_target(statement)
                if module:
                    imports.append({
                        "module": module,
                        "names": [],
                        "is_relative": _is_relative_url(module),
                        "line": statement.start_point[0] + 1,
                    })

        imports.sort(key=lambda entry: entry["line"])
        return {"language": "css", "entities": entities, "imports": imports}


# Pulls just the path out of an @import, whichever form it's written in:
# @import "x.css";  @import url("x.css");  @import url(x.css);
# Returns None if the statement doesn't have a recognizable target.
def _import_target(statement) -> str | None:
    for child in statement.named_children:
        if child.type == "string_value":
            return _string_content(child)
        if child.type == "call_expression":
            arguments = next((c for c in child.named_children if c.type == "arguments"), None)
            if arguments is None:
                return None
            for argument in arguments.named_children:
                if argument.type == "string_value":
                    return _string_content(argument)
                if argument.type == "plain_value":
                    return argument.text.decode("utf-8")
    return None


# The text inside a quoted CSS string, without the quotes.
def _string_content(string_node) -> str:
    return string_node.text.decode("utf-8")[1:-1]


# An @import target is relative (a file in this repo) unless it's a full
# URL, a protocol-relative URL (//cdn...) or inline data: content.
def _is_relative_url(value: str) -> bool:
    return not value.startswith(("http://", "https://", "//", "data:"))
