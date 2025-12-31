"""
Unit tests for ARIA snapshot processor utilities.
"""

from typing import Any
import pytest

from playwright_proxy_mcp.utils.aria_processor import (
    _extract_yaml_from_markdown,
    apply_jmespath_query,
    flatten_aria_tree,
    format_output,
    parse_aria_snapshot,
)

def test_extract_yaml_with_header():
    """Test stripping preamble text before ARIA snapshot."""
    yaml_with_preamble = """Page URL: https://example.com
Title: Example Domain

- Page title: Example Domain
  - heading "Example Domain" [ref=e1]
  - paragraph "This domain is for use in illustrative examples" [ref=e2]"""

    expected = """- Page title: Example Domain
  - heading "Example Domain" [ref=e1]
  - paragraph "This domain is for use in illustrative examples" [ref=e2]"""

    result = _extract_yaml_from_markdown(yaml_with_preamble)
    assert result == expected


def test_extract_yaml_with_markdown_fence():
    """Test extracting YAML from markdown code fence."""
    yaml_with_fence = """```yaml
- button "Submit" [ref=e1]
- link "Home" [ref=e2]
```"""

    expected = """- button "Submit" [ref=e1]
- link "Home" [ref=e2]"""

    result = _extract_yaml_from_markdown(yaml_with_fence)
    assert result == expected


def test_extract_yaml_with_header_and_fence():
    """Test extracting YAML from markdown with both header and fence."""
    yaml_complex = """Page URL: https://example.com

```yaml
- button "Submit" [ref=e1]
- link "Home" [ref=e2]
```"""

    expected = """- button "Submit" [ref=e1]
- link "Home" [ref=e2]"""

    result = _extract_yaml_from_markdown(yaml_complex)
    assert result == expected


def test_extract_yaml_plain_text():
    """Test that plain YAML without markdown is unchanged."""
    yaml_plain = """- Page title: Example
  - heading "Example" [ref=e1]"""

    result = _extract_yaml_from_markdown(yaml_plain)
    assert result == yaml_plain


def test_extract_yaml_empty():
    """Test handling of empty string."""
    result = _extract_yaml_from_markdown("")
    assert result == ""


def test_extract_yaml_no_list():
    """Test handling of text with no ARIA list."""
    text_without_list = "Just some random text\nNo ARIA snapshot here"

    result = _extract_yaml_from_markdown(text_without_list)
    assert result == text_without_list  # Returns original if no list found


def test_extract_yaml_unnamed_code_block():
    """Test extracting from code block without language specifier."""
    yaml_unnamed = """```
- button "Submit" [ref=e1]
- link "Home" [ref=e2]
```"""

    expected = """- button "Submit" [ref=e1]
- link "Home" [ref=e2]"""

    result = _extract_yaml_from_markdown(yaml_unnamed)
    assert result == expected


def test_parse_aria_snapshot_with_preamble():
    """Test parsing ARIA snapshot that has preamble text."""
    yaml_with_preamble = """Page URL: https://www.lcsc.com/product-detail/C107107.html

- button "Submit" [ref=e1]
- link "Home" [ref=e2]"""

    json_data, errors = parse_aria_snapshot(yaml_with_preamble)

    assert errors == [], f"Should parse without errors, got: {errors}"
    assert json_data is not None
    assert isinstance(json_data, list)
    assert len(json_data) == 2
    assert json_data[0]["role"] == "button"
    assert json_data[1]["role"] == "link"


def test_parse_aria_snapshot_without_preamble():
    """Test parsing ARIA snapshot without preamble."""
    yaml_without_preamble = """- button "Submit" [ref=e1]
- link "Home" [ref=e2]"""

    json_data, errors = parse_aria_snapshot(yaml_without_preamble)

    assert errors == [], f"Should parse without errors, got: {errors}"
    assert json_data is not None
    assert isinstance(json_data, list)
    assert len(json_data) == 2


def test_apply_jmespath_query_filter():
    """Test JMESPath query filtering."""
    data = [
        {"role": "button", "name": {"value": "Submit"}},
        {"role": "link", "name": {"value": "Home"}},
        {"role": "button", "name": {"value": "Cancel"}},
    ]

    result, error = apply_jmespath_query(data, '[?role == `button`]')

    assert error is None
    assert len(result) == 2
    assert all(item["role"] == "button" for item in result)

def test_apply_jmespath_query_projection():
    """Test JMESPath query projection."""
    data = [
        {"role": "button", "name": {"value": "Submit"}},
        {"role": "link", "name": {"value": "Home"}},
    ]

    result, error = apply_jmespath_query(data, '[].name.value')

    assert error is None
    assert result == ["Submit", "Home"]

def test_apply_jmespath_query_invalid():
    """Test JMESPath query with invalid syntax."""
    data = [{"role": "button"}]

    result, error = apply_jmespath_query(data, '[?invalid syntax')

    assert error is not None
    assert "Invalid JMESPath query" in error
    assert result == []

def test_format_output_json():
    """Test JSON output formatting."""
    data = [{"role": "button", "name": "Submit"}]

    result = format_output(data, "json")

    assert isinstance(result, list)


def test_format_output_yaml():
    """Test YAML output formatting."""
    data = [{"role": "button", "name": "Submit"}]

    result = format_output(data, "yaml")

    assert isinstance(result, str)
    import yaml
    parsed = yaml.safe_load(result)
    assert parsed == data

def test_format_output_default_yaml():
    """Test that default format is YAML."""
    data = [{"role": "button"}]

    result_yaml = format_output(data, "yaml")
    result_other = format_output(data, "anything")

    # Both should be YAML formatted
    import yaml
    assert yaml.safe_load(result_yaml) == data
    assert yaml.safe_load(result_other) == data


# Tests for flatten_aria_tree()

def test_flatten_aria_tree_simple():
    """Test flattening a simple 2-level tree."""
    tree = [
        {
            "role": "document",
            "children": [
                {"role": "button", "name": {"value": "Submit"}},
                {"role": "link", "name": {"value": "Home"}},
            ]
        }
    ]

    result = flatten_aria_tree(tree)

    assert len(result) == 3
    # Check root element
    assert result[0]["role"] == "document"
    assert result[0]["_depth"] == 0
    assert result[0]["_parent_role"] is None
    assert result[0]["_index"] == 0
    assert "children" not in result[0]
    # Check children
    assert result[1]["role"] == "button"
    assert result[1]["_depth"] == 1
    assert result[1]["_parent_role"] == "document"
    assert result[1]["_index"] == 1
    assert result[2]["role"] == "link"
    assert result[2]["_depth"] == 1
    assert result[2]["_parent_role"] == "document"
    assert result[2]["_index"] == 2


def test_flatten_aria_tree_deep_nesting():
    """Test flattening a deeply nested tree (4 levels)."""
    tree = [
        {
            "role": "document",
            "children": [
                {
                    "role": "banner",
                    "children": [
                        {
                            "role": "navigation",
                            "children": [
                                {"role": "link", "name": {"value": "Home"}}
                            ]
                        }
                    ]
                }
            ]
        }
    ]

    result = flatten_aria_tree(tree)

    assert len(result) == 4
    assert result[0]["role"] == "document"
    assert result[0]["_depth"] == 0
    assert result[1]["role"] == "banner"
    assert result[1]["_depth"] == 1
    assert result[1]["_parent_role"] == "document"
    assert result[2]["role"] == "navigation"
    assert result[2]["_depth"] == 2
    assert result[2]["_parent_role"] == "banner"
    assert result[3]["role"] == "link"
    assert result[3]["_depth"] == 3
    assert result[3]["_parent_role"] == "navigation"


def test_flatten_aria_tree_multiple_siblings():
    """Test flattening tree with multiple siblings at each level."""
    tree = [
        {
            "role": "document",
            "children": [
                {
                    "role": "banner",
                    "children": [
                        {"role": "heading", "name": {"value": "Welcome"}},
                        {"role": "navigation"}
                    ]
                },
                {
                    "role": "main",
                    "children": [
                        {"role": "heading", "name": {"value": "Content"}},
                        {"role": "paragraph"}
                    ]
                }
            ]
        }
    ]

    result = flatten_aria_tree(tree)

    # Should have: document, banner, heading, navigation, main, heading, paragraph = 7 nodes
    assert len(result) == 7
    # Verify depth-first order
    assert result[0]["role"] == "document"
    assert result[1]["role"] == "banner"
    assert result[2]["role"] == "heading"
    assert result[3]["role"] == "navigation"
    assert result[4]["role"] == "main"
    assert result[5]["role"] == "heading"
    assert result[6]["role"] == "paragraph"
    # Verify indices are sequential
    assert [node["_index"] for node in result] == list(range(7))


def test_flatten_aria_tree_single_node():
    """Test flattening a tree with a single node (no children)."""
    tree = [{"role": "button", "name": {"value": "Click me"}}]

    result = flatten_aria_tree(tree)

    assert len(result) == 1
    assert result[0]["role"] == "button"
    assert result[0]["_depth"] == 0
    assert result[0]["_parent_role"] is None
    assert result[0]["_index"] == 0


def test_flatten_aria_tree_empty_children():
    """Test flattening a node with empty children array."""
    tree = [{"role": "document", "children": []}]

    result = flatten_aria_tree(tree)

    assert len(result) == 1
    assert result[0]["role"] == "document"
    assert "children" not in result[0]


def test_flatten_aria_tree_preserves_attributes():
    """Test that flattening preserves all node attributes."""
    tree = [
        {
            "role": "button",
            "name": {"value": "Submit", "is_regex": False},
            "disabled": False,
            "ref": "e1",
            "children": [
                {"type": "text", "value": "Submit"}
            ]
        }
    ]

    result = flatten_aria_tree(tree)

    assert len(result) == 2
    # Check button attributes are preserved
    assert result[0]["role"] == "button"
    assert result[0]["name"] == {"value": "Submit", "is_regex": False}
    assert result[0]["disabled"] is False
    assert result[0]["ref"] == "e1"
    # Check text child
    assert result[1]["type"] == "text"
    assert result[1]["value"] == "Submit"


def test_flatten_aria_tree_multiple_root_elements():
    """Test flattening when root array has multiple elements."""
    tree = [
        {"role": "button", "name": {"value": "Submit"}},
        {"role": "link", "name": {"value": "Home"}},
        {"role": "textbox", "ref": "e1"}
    ]

    result = flatten_aria_tree(tree)

    assert len(result) == 3
    assert all(node["_depth"] == 0 for node in result)
    assert all(node["_parent_role"] is None for node in result)
    assert [node["_index"] for node in result] == [0, 1, 2]


def test_flatten_aria_tree_empty_list():
    """Test flattening an empty list."""
    tree = []

    result = flatten_aria_tree(tree)

    assert result == []


def test_flatten_aria_tree_text_nodes():
    """Test flattening tree containing text nodes."""
    tree = [
        {
            "role": "paragraph",
            "ref": "e1",
            "children": [
                {"type": "text", "value": "This is some text."}
            ]
        }
    ]

    result = flatten_aria_tree(tree)

    assert len(result) == 2
    assert result[0]["role"] == "paragraph"
    assert result[1]["type"] == "text"
    assert result[1]["value"] == "This is some text."
    assert result[1]["_depth"] == 1
    assert result[1]["_parent_role"] == "paragraph"
