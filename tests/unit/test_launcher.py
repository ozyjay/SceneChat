import signal
from types import SimpleNamespace

import scenechat.__main__ as launcher
from scenechat.services.runtime import clear_shutdown_request, shutdown_requested


def test_launcher_suppresses_routine_server_logs(monkeypatch):
    captured = {}
    settings = SimpleNamespace(scenechat_host="127.0.0.1", scenechat_port=3700)

    class FakeServer:
        def __init__(self, config):
            captured["server_config"] = config

        def run(self):
            captured["run"] = True

    monkeypatch.setattr(launcher, "get_settings", lambda: settings)
    monkeypatch.setattr(launcher.uvicorn, "Config", lambda application, **options: {
        "application": application,
        **options,
    })
    monkeypatch.setattr(launcher, "SceneChatServer", FakeServer)

    launcher.main()

    assert captured["server_config"] == {
        "application": "scenechat.main:app",
        "host": "127.0.0.1",
        "port": 3700,
        "reload": False,
        "access_log": False,
        "log_level": "warning",
    }
    assert captured["run"] is True


def test_server_signal_notifies_streaming_responses(monkeypatch):
    clear_shutdown_request()
    monkeypatch.setattr(launcher.uvicorn.Server, "handle_exit", lambda *args: None)
    server = object.__new__(launcher.SceneChatServer)

    server.handle_exit(signal.SIGINT, None)

    assert shutdown_requested() is True
    clear_shutdown_request()
