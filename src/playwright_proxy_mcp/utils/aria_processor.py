"""
ARIA Snapshot Processor

Processes ARIA snapshots: parsing, querying, and formatting.
"""

import json
from typing import Any

import yaml

from aria_snapshot_parser import AriaSnapshotParser, AriaSnapshotSerializer

from .jmespath_extensions import search_with_custom_functions


def parse_aria_snapshot(yaml_text: str) -> tuple[Any, list[str]]:
    """
    Parse ARIA YAML snapshot to JSON.

    Args:
        yaml_text: ARIA snapshot in YAML format

    Returns:
        Tuple of (json_data, error_messages)
        - json_data: Parsed snapshot as JSON-serializable data, or None if parse failed
        - error_messages: List of error messages (empty if successful)
    """
    try:
        parser = AriaSnapshotParser()
        tree, errors = parser.parse(yaml_text)

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


def format_output(data: Any, output_format: str) -> str:
    """
    Format data as JSON or YAML.

    Args:
        data: Data to format
        output_format: 'json' or 'yaml'

    Returns:
        Formatted string
    """
    if output_format.lower() == "yaml":
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:  # json
        return json.dumps(data, indent=2, ensure_ascii=False)
