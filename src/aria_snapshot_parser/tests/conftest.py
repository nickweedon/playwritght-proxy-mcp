"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_yaml(fixtures_dir: Path) -> str:
    """Load simple test YAML."""
    return (fixtures_dir / "simple.yaml").read_text()


@pytest.fixture
def google_yaml(fixtures_dir: Path) -> str:
    """Load Google example YAML."""
    return (fixtures_dir / "google.yaml").read_text()


@pytest.fixture
def attributes_yaml(fixtures_dir: Path) -> str:
    """Load attributes test YAML."""
    return (fixtures_dir / "attributes.yaml").read_text()


@pytest.fixture
def regex_yaml(fixtures_dir: Path) -> str:
    """Load regex test YAML."""
    return (fixtures_dir / "regex.yaml").read_text()


@pytest.fixture
def simple_expected_json(fixtures_dir: Path) -> str:
    """Load expected JSON for simple test case."""
    return (fixtures_dir / "simple_expected.json").read_text()


@pytest.fixture
def example_domain_yaml(fixtures_dir: Path) -> str:
    """Load example domain YAML."""
    return (fixtures_dir / "example_domain.yaml").read_text()
