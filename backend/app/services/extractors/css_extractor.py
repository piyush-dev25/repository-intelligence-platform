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
                imports.append(match["import.statement"][0].text.decode("utf-8"))

        return {"language": "css", "entities": entities, "imports": imports}
