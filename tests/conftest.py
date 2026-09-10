"""Shared fixtures."""

import importlib.util

import pytest


def _has_flatland() -> bool:
    return importlib.util.find_spec("flatland") is not None


@pytest.fixture
def flatland_available() -> bool:
    return _has_flatland()
