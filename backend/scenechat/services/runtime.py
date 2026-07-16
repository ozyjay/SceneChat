"""Process-level runtime signals shared by the server and streaming responses."""

from threading import Event


_shutdown_requested = Event()


def clear_shutdown_request() -> None:
    _shutdown_requested.clear()


def request_shutdown() -> None:
    _shutdown_requested.set()


def shutdown_requested() -> bool:
    return _shutdown_requested.is_set()
