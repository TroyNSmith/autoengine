"""autoengine tests."""

import autoengine


def test_stub() -> None:
    """Stub test to ensure the test suite runs."""
    print(autoengine.__version__)  # noqa: T201


def test__greet() -> None:
    """Test the greet function."""
    assert autoengine.greet("World") == "Hello, World!"
