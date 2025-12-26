"""Tests for ARIA snapshot parser."""

import pytest

from aria_snapshot_parser import AriaSnapshotParser, parse
from aria_snapshot_parser.types import AriaTemplateNode, AriaTextValue


class TestAriaSnapshotParser:
    """Test ARIA snapshot parser."""

    def test_parse_simple_button(self):
        """Test parsing a simple button."""
        yaml_text = '- button "Submit"'
        tree, errors = parse(yaml_text)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 1
        assert isinstance(tree[0], AriaTemplateNode)
        assert tree[0].role == "button"
        assert tree[0].name is not None
        assert tree[0].name.value == "Submit"
        assert tree[0].name.is_regex is False

    def test_parse_simple_yaml(self, simple_yaml: str):
        """Test parsing simple YAML fixture."""
        tree, errors = parse(simple_yaml)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 2

        # Check button
        button = tree[0]
        assert button.role == "button"
        assert button.name.value == "Submit"
        assert button.ref == "e1"
        assert button.cursor == "pointer"

        # Check link
        link = tree[1]
        assert link.role == "link"
        assert link.name.value == "Home"
        assert link.ref == "e2"
        assert link.props["url"] == "https://example.com"

    def test_parse_attributes(self, attributes_yaml: str):
        """Test parsing all attribute types."""
        tree, errors = parse(attributes_yaml)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 9

        # Check checkbox with checked
        assert tree[0].role == "checkbox"
        assert tree[0].checked is True

        # Check checkbox with checked=mixed
        assert tree[1].role == "checkbox"
        assert tree[1].checked == "mixed"

        # Check disabled button
        assert tree[2].role == "button"
        assert tree[2].disabled is True

        # Check expanded details
        assert tree[3].role == "details"
        assert tree[3].expanded is True

        # Check active combobox
        assert tree[4].role == "combobox"
        assert tree[4].active is True

        # Check heading with level
        assert tree[5].role == "heading"
        assert tree[5].name.value == "Title"
        assert tree[5].level == 2

        # Check pressed button
        assert tree[6].role == "button"
        assert tree[6].pressed is True

        # Check pressed=mixed button
        assert tree[7].role == "button"
        assert tree[7].pressed == "mixed"

        # Check selected option
        assert tree[8].role == "option"
        assert tree[8].selected is True

    def test_parse_regex(self, regex_yaml: str):
        """Test parsing regex patterns."""
        tree, errors = parse(regex_yaml)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 2

        # Check button with regex
        button = tree[0]
        assert button.role == "button"
        assert button.name.is_regex is True
        assert button.name.value == "Submit.*"

        # Check link with regex
        link = tree[1]
        assert link.role == "link"
        assert link.name.is_regex is True
        assert link.name.value == "Home|About"
        assert link.props["url"] == "/https:.*/"

    def test_parse_google_example(self, google_yaml: str):
        """Test parsing real Google example."""
        tree, errors = parse(google_yaml)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 1

        # Check root generic
        root = tree[0]
        assert root.role == "generic"
        assert root.ref == "e2"

        # Check navigation exists
        assert len(root.children) > 0
        nav = root.children[0]
        assert isinstance(nav, AriaTemplateNode)
        assert nav.role == "navigation"
        assert nav.ref == "e3"

    def test_parse_empty_yaml(self):
        """Test parsing empty YAML."""
        tree, errors = parse("")

        assert tree is None
        assert len(errors) == 0

    def test_parse_text_node(self):
        """Test parsing text node."""
        yaml_text = """
- link "Images":
  - text: Search for Images
"""
        tree, errors = parse(yaml_text)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 1
        assert tree[0].role == "link"
        assert len(tree[0].children) == 1
        assert tree[0].children[0] == "Search for Images"

    def test_parse_example_domain(self, example_domain_yaml: str):
        """Test parsing example domain with nested structure and colon syntax."""
        tree, errors = parse(example_domain_yaml)

        assert len(errors) == 0
        assert tree is not None
        assert len(tree) == 1

        # Check root generic element
        generic = tree[0]
        assert generic.role == "generic"
        assert generic.ref == "e2"

        # Check children
        assert len(generic.children) == 2

        # Check heading child
        heading = generic.children[0]
        assert heading.role == "heading"
        assert heading.name.value == "Example Domain"
        assert heading.level == 1
        assert heading.ref == "e3"

        # Check paragraph child
        paragraph = generic.children[1]
        assert paragraph.role == "paragraph"
        assert paragraph.ref == "e4"
        assert paragraph.name.value == "This domain is for use in documentation examples without needing permission. Avoid use in operations."
