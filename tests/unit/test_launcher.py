from types import SimpleNamespace

import scenechat.__main__ as launcher


def test_launcher_disables_request_access_log(monkeypatch):
    captured = {}
    settings = SimpleNamespace(scenechat_host="127.0.0.1", scenechat_port=3700)

    monkeypatch.setattr(launcher, "get_settings", lambda: settings)
    monkeypatch.setattr(
        launcher.uvicorn,
        "run",
        lambda application, **options: captured.update(
            application=application, **options
        ),
    )

    launcher.main()

    assert captured == {
        "application": "scenechat.main:app",
        "host": "127.0.0.1",
        "port": 3700,
        "reload": False,
        "access_log": False,
    }
