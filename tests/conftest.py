import pytest


@pytest.fixture
def anyio_backend():
    """The application uses asyncio in production; do not parametrise tests over Trio."""
    return "asyncio"
