from tree_sitter import Language, Parser, Query, QueryCursor
from app.services.extractors.base_extractor import BaseExtractor
import tree_sitter_html as tshtml

HTML_LANGUAGE = Language(tshtml.language())

HTML_QUERY = Query(HTML_LANGUAGE, """
(element
  (start_tag
    (tag_name) @element.tag
    (attribute
      (attribute_name) @id_attr.name
      (quoted_attribute_value (attribute_value) @element.id))
    (#eq? @id_attr.name "id"))) @element.def

(start_tag
  (tag_name) @semantic.name
  (#match? @semantic.name "^(nav|header|footer|main|section|button|form)$")) @semantic.def

(element
  (start_tag
    (tag_name) @link.tag
    (attribute
      (attribute_name) @href.name
      (quoted_attribute_value (attribute_value) @import.href))
    (#eq? @link.tag "link")
    (#eq? @href.name "href")))

(script_element
  (start_tag
    (attribute
      (attribute_name) @src.name
      (quoted_attribute_value (attribute_value) @import.src))
    (#eq? @src.name "src")))
""")


class HtmlExtractor(BaseExtractor):
    def __init__(self) -> None:
        self.parser = Parser(HTML_LANGUAGE)

    def extract(self, source_code: bytes) -> dict:
      tree = self.parser.parse(source_code)
      cursor = QueryCursor(HTML_QUERY)

      entities = []
      seen_start_bytes = set()

      # .matches() groups captures by which match they came from, so
      # element.def and element.id from the SAME match are guaranteed
      # correctly paired - unlike .captures(), which returns separate
      # flat lists that can silently misalign when a pattern matches
      # more than once (confirmed: this was a real bug, not theoretical).
      for pattern_index, match_captures in cursor.matches(tree.root_node):
          if "element.id" in match_captures:
              def_node = match_captures["element.def"][0]
              id_node = match_captures["element.id"][0]
              entities.append({
                  "name": id_node.text.decode("utf-8"),
                  "kind": "element",
                  "start_line": def_node.start_point[0] + 1,
                  "end_line": def_node.end_point[0] + 1,
              })
              seen_start_bytes.add(def_node.start_byte)

      for pattern_index, match_captures in cursor.matches(tree.root_node):
          if "semantic.def" in match_captures:
              tag_node = match_captures["semantic.def"][0]
              element_node = tag_node.parent
              if element_node.start_byte in seen_start_bytes:
                  continue
              entities.append({
                  "name": tag_node.text.decode("utf-8").strip("<>"),
                  "kind": "element",
                  "start_line": element_node.start_point[0] + 1,
                  "end_line": element_node.end_point[0] + 1,
              })

      imports = []
      for pattern_index, match_captures in cursor.matches(tree.root_node):
          if "import.href" in match_captures:
              imports.append(match_captures["import.href"][0].text.decode("utf-8"))
          if "import.src" in match_captures:
              imports.append(match_captures["import.src"][0].text.decode("utf-8"))

      return {
          "language": "html",
          "entities": entities,
          "imports": imports,
      }
