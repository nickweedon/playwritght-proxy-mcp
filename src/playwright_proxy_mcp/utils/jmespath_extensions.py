"""
JMESPath Custom Functions

Extends JMESPath with custom functions for enhanced querying capabilities.
Based on partsbox_mcp reference implementation.
"""

import re
from typing import Any

import jmespath
from jmespath import functions


class CustomFunctions(functions.Functions):
    """Custom JMESPath functions for ARIA snapshot queries."""

    @functions.signature(
        {"types": []},  # Accept any type for first arg
        {"types": []},  # Accept any type for second arg
    )
    def _func_nvl(self, value: Any, default: Any) -> Any:
        """
        Return default if value is null (None in Python).

        This is similar to Oracle's NVL function.
        Useful for safely filtering on nullable fields.

        Args:
            value: Value to check
            default: Default value to return if value is null

        Returns:
            value if not null, otherwise default
        """
        return default if value is None else value

    @functions.signature({"types": []})  # Accept any type
    def _func_int(self, value: Any) -> int | None:
        """
        Convert value to integer.

        Returns null if conversion fails.

        Args:
            value: Value to convert

        Returns:
            Integer value or None if conversion fails
        """
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @functions.signature({"types": []})  # Accept any type
    def _func_str(self, value: Any) -> str | None:
        """
        Convert value to string.

        Args:
            value: Value to convert

        Returns:
            String representation or None if value is null
        """
        if value is None:
            return None
        return str(value)

    @functions.signature(
        {"types": ["string"]}, {"types": ["string"]}, {"types": ["string", "null"]}
    )
    def _func_regex_replace(
        self, pattern: str, replacement: str, value: str | None
    ) -> str | None:
        """
        Perform regex find-and-replace.

        Args:
            pattern: Regular expression pattern
            replacement: Replacement string
            value: String to perform replacement on

        Returns:
            String with replacements made, or None if value is null
        """
        if value is None:
            return None
        try:
            return re.sub(pattern, replacement, value)
        except re.error:
            return value


# Create custom options with our functions
_custom_options = jmespath.Options(custom_functions=CustomFunctions())


def search_with_custom_functions(expression: str, data: Any) -> Any:
    """
    Search data using JMESPath expression with custom functions.

    Args:
        expression: JMESPath expression
        data: Data to search

    Returns:
        Query result
    """
    return jmespath.search(expression, data, options=_custom_options)
