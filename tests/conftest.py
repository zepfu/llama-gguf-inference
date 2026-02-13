"""Shared test fixtures for auth module tests."""

import os
import sys

import pytest

# Add scripts/ to path so we can import auth module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


@pytest.fixture
def keys_file(tmp_path):
    """Create a temporary API keys file."""
    path = tmp_path / "api_keys.txt"
    path.write_text("testing:sk-test-1234567890abcdef\nloadtest:sk-load-abcdef1234567890\n")
    return str(path)


@pytest.fixture
def empty_keys_file(tmp_path):
    """Create an empty keys file."""
    path = tmp_path / "api_keys.txt"
    path.write_text("")
    return str(path)


@pytest.fixture
def auth_env(keys_file, monkeypatch):
    """Set up environment for auth-enabled testing."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_KEYS_FILE", keys_file)
    monkeypatch.setenv("MAX_REQUESTS_PER_MINUTE", "100")
    monkeypatch.setenv("DATA_DIR", "/tmp/test-data")


@pytest.fixture
def noauth_env(monkeypatch):
    """Set up environment for auth-disabled testing."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("DATA_DIR", "/tmp/test-data")
