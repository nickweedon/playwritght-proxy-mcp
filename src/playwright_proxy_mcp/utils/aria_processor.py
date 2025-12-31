"""
ARIA Snapshot Processor

Processes ARIA snapshots: parsing, querying, and formatting.
"""

import json
from typing import Any

import mistune
import yaml

from aria_snapshot_parser import AriaSnapshotParser, AriaSnapshotSerializer

from .jmespath_extensions import search_with_custom_functions


def parse_aria_snapshot(yaml_text: str) -> tuple[Any, list[str]]:
    """
    Parse ARIA YAML snapshot to JSON.

    Args:
        yaml_text: ARIA snapshot in YAML format (may be wrapped in markdown)

    Returns:
        Tuple of (json_data, error_messages)
        - json_data: Parsed snapshot as JSON-serializable data, or None if parse failed
        - error_messages: List of error messages (empty if successful)
    """
    try:
        # Extract YAML from markdown if wrapped in code fence
        cleaned_yaml = _extract_yaml_from_markdown(yaml_text)

        parser = AriaSnapshotParser()
        tree, errors = parser.parse(cleaned_yaml)

        if errors:
            error_messages = []
            for e in errors:
                if e.line is not None:
                    error_messages.append(f"Line {e.line}: {e.message}")
                else:
                    error_messages.append(e.message)
            return None, error_messages

        serializer = AriaSnapshotSerializer()
        json_data = serializer.to_dict(tree)
        return json_data, []

    except Exception as e:
        return None, [f"Failed to parse ARIA snapshot: {e}"]


def _extract_yaml_from_markdown(text: str) -> str:
    """
    Extract YAML content from markdown, handling code fences and plain text.

    Playwright-mcp may return ARIA snapshots in various formats:
    1. Plain YAML (starts with "- ")
    2. Markdown with code fence (```yaml ... ```)
    3. Markdown with metadata headers before YAML
    4. Text content followed by ARIA tree

    Args:
        text: Raw text that may contain markdown-wrapped YAML

    Returns:
        Cleaned YAML text ready for parsing
    """
    # Quick check: if text starts with "- ", it's plain YAML
    stripped_text = text.lstrip()
    if stripped_text.startswith('- '):
        return text

    # Try to extract from markdown code blocks
    try:
        markdown = mistune.create_markdown(renderer='ast')
        ast = markdown(text)

        # Look for code blocks with yaml/yml language
        for node in ast:
            if isinstance(node, dict) and node.get('type') == 'block_code':
                attrs = node.get('attrs', {})
                if isinstance(attrs, dict):
                    info = attrs.get('info', '').lower()
                    if info in ('yaml', 'yml', ''):
                        # Found a code block, return its raw content (strip trailing newline)
                        raw_content = node.get('raw', '')
                        if raw_content:
                            return raw_content.rstrip('\n')
    except Exception:
        # If markdown parsing fails, fall back to heuristic approach
        pass

    # Fallback: Look for YAML list starting with "- "
    # Skip any preamble text that doesn't start with "- "
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith('- '):
            # Found start of YAML, collect until we hit a closing fence or end
            yaml_lines = []
            for j in range(i, len(lines)):
                line_content = lines[j].strip()
                # Stop if we hit a closing fence
                if line_content == '```':
                    break
                # Stop if we encounter a line that doesn't look like YAML
                # (empty lines are OK, as are lines starting with "- " or indented content)
                if line_content and not (
                    line_content.startswith('- ') or
                    lines[j].startswith('  ') or  # indented (child element)
                    lines[j].startswith('\t')     # tab-indented
                ):
                    # Check if it's a continuation or if we've left the YAML block
                    # If the line doesn't start with whitespace and isn't a list item, we're done
                    if j > i:  # Only stop if we've collected at least one line
                        break
                yaml_lines.append(lines[j])
            if yaml_lines:
                return '\n'.join(yaml_lines)

    # If no YAML list found, return original (will likely fail parsing)
    return text


def apply_jmespath_query(data: Any, expression: str) -> tuple[Any, str | None]:
    """
    Apply JMESPath query with custom functions.

    Args:
        data: Data to query
        expression: JMESPath expression

    Returns:
        Tuple of (result, error_message)
        - result: Query result (or empty list on error)
        - error_message: Error message if query failed, None otherwise
    """
    try:
        result = search_with_custom_functions(expression, data)
        # Return empty list if result is None
        return (result if result is not None else [], None)
    except Exception as e:
        return ([], f"Invalid JMESPath query: {e}")


def flatten_aria_tree(
    node: dict | list,
    depth: int = 0,
    parent_role: str | None = None,
    index_counter: list[int] | None = None
) -> list[dict]:
    """
    Flatten ARIA tree to depth-first list of nodes.

    Converts hierarchical ARIA snapshot into a flat list where each node
    is a standalone dict with metadata about its position in the tree.

    Args:
        node: ARIA tree (dict) or root array (list)
        depth: Current nesting level (0 = root)
        parent_role: Role of parent node (for context)
        index_counter: Mutable list containing current index (internal use)

    Returns:
        Flat list of nodes with added metadata fields:
        - _depth: Nesting level (0 = root)
        - _parent_role: Role of parent node (None for root)
        - _index: Position in flattened list

    Example:
        >>> tree = [{"role": "document", "children": [{"role": "button"}]}]
        >>> flatten_aria_tree(tree)
        [
            {"role": "document", "_depth": 0, "_parent_role": None, "_index": 0},
            {"role": "button", "_depth": 1, "_parent_role": "document", "_index": 1}
        ]
    """
    if index_counter is None:
        index_counter = [0]

    result = []

    if isinstance(node, list):
        # Process array of nodes
        for item in node:
            result.extend(flatten_aria_tree(item, depth, parent_role, index_counter))

    elif isinstance(node, dict):
        # Create copy of current node without children
        node_copy = {**node}

        # Extract children before adding metadata
        children = node_copy.pop('children', None)

        # Add metadata
        node_copy['_depth'] = depth
        node_copy['_parent_role'] = parent_role
        node_copy['_index'] = index_counter[0]
        index_counter[0] += 1

        # Add current node to result
        result.append(node_copy)

        # Recursively flatten children
        if children:
            current_role = node.get('role')
            result.extend(flatten_aria_tree(children, depth + 1, current_role, index_counter))

    return result


def format_output(data: dict[str, Any], output_format: str) -> str | list[dict[str, Any]]:
    """
    Format data as JSON (raw) or YAML.

    Args:
        data: Data to format
        output_format: 'json' or 'yaml'

    Returns:
        Formatted string or raw data
    """
    if output_format.lower() == "json":
        return data
    else:  # yaml (default)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
