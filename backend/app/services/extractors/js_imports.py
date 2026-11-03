from tree_sitter import Language, Node, Query, QueryCursor

# Shared import extraction for JavaScript, TypeScript and TSX. All three
# grammars use the same node names for imports, so one query text and one
# set of rules covers them - each extractor just compiles the query
# against its own Language (a Query is tied to the Language it's built with).
#
# Three kinds of import-like constructs:
#   @import   - ES imports, incl. TS `import type` and `import x = require("y")`
#   @reexport - `export { a } from "./x"` / `export * from "./x"` (needs a source)
#   @require  - CommonJS require("x"), only when the single argument is a
#               plain string literal (the `.` anchors enforce "only child").
#               Dynamic import("x") never matches: its function is an
#               `import` node, not the identifier `require`.
JS_IMPORT_QUERY_SOURCE = """
(import_statement) @import

(export_statement
  source: (string)) @reexport

(call_expression
  function: (identifier) @require.fn
  arguments: (arguments . (string) @require.source .)
  (#eq? @require.fn "require")) @require
"""


# Compiles the shared import query for one grammar. Each extractor calls
# this once at module load and keeps the result as a constant.
def build_js_import_query(language: Language) -> Query:
    return Query(language, JS_IMPORT_QUERY_SOURCE)


# Finds every import / re-export / require() in a parsed JS/TS/TSX file
# and returns them as structured dicts, in source order:
# {"module": str, "names": list[str], "is_relative": bool, "line": int}
def extract_js_imports(root_node: Node, import_query: Query) -> list[dict]:
    imports = []
    for pattern_index, match in QueryCursor(import_query).matches(root_node):
        if "import" in match:
            entry = _from_import_statement(match["import"][0])
        elif "reexport" in match:
            entry = _from_reexport(match["reexport"][0])
        elif "require" in match:
            entry = _make_import(
                _string_text(match["require.source"][0]), [], match["require"][0],
            )
        else:
            entry = None

        if entry is not None and entry["module"]:
            imports.append(entry)

    return sorted(imports, key=lambda entry: entry["line"])


# Builds one ES import entry. Handles the normal `... from "x"` form
# (module in the statement's source field) and TS's `import x = require("x")`
# (module inside an import_require_clause). Returns None if there's no module.
def _from_import_statement(node: Node) -> dict | None:
    source = node.child_by_field_name("source")
    if source is None:
        for child in node.named_children:
            if child.type == "import_require_clause":
                source = child.child_by_field_name("source")
        if source is None:
            return None
        return _make_import(_string_text(source), [], node)

    names = []
    for child in node.named_children:
        if child.type == "import_clause":
            names = _import_clause_names(child)

    return _make_import(_string_text(source), names, node)


# Reads the imported names from an import clause:
# default import -> "default", named imports -> their original (not
# aliased) names, `* as ns` -> "*". A `type` keyword inside a specifier
# (`import { type A }`) isn't a named node, so it's naturally skipped.
def _import_clause_names(clause: Node) -> list[str]:
    names = []
    for child in clause.named_children:
        if child.type == "identifier":
            names.append("default")
        elif child.type == "namespace_import":
            names.append("*")
        elif child.type == "named_imports":
            for specifier in child.named_children:
                if specifier.type == "import_specifier":
                    names.append(specifier.child_by_field_name("name").text.decode("utf-8"))
    return names


# Builds one re-export entry: `export { a, b as c } from "./x"` -> ["a", "b"],
# `export * from "./x"` and `export * as ns from "./x"` -> ["*"].
def _from_reexport(node: Node) -> dict:
    names = []
    for child in node.children:
        if child.type == "*" or child.type == "namespace_export":
            names.append("*")
        elif child.type == "export_clause":
            for specifier in child.named_children:
                if specifier.type == "export_specifier":
                    names.append(specifier.child_by_field_name("name").text.decode("utf-8"))

    return _make_import(_string_text(node.child_by_field_name("source")), names, node)


# The text inside a string literal node, without its surrounding quotes.
def _string_text(string_node: Node) -> str:
    return string_node.text.decode("utf-8")[1:-1]


# Assembles the final dict. Relative = a path starting with ./ ../ or /;
# anything else ("react", "@/components/x") is a package or an alias,
# which the 5.4 resolver deals with.
def _make_import(module: str, names: list[str], node: Node) -> dict:
    return {
        "module": module,
        "names": names,
        "is_relative": module.startswith(("./", "../", "/")),
        "line": node.start_point[0] + 1,
    }
