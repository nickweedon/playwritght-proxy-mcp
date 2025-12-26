"""
Unit tests for ARIA snapshot processor utilities.
"""

import pytest

from playwright_proxy_mcp.utils.aria_processor import (
    _extract_yaml_from_markdown,
    apply_jmespath_query,
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

    assert isinstance(result, str)
    import json
    parsed = json.loads(result)
    assert parsed == data


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
