"""Run SceneChat with `python -m scenechat`."""

from copy import deepcopy

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from scenechat.config import get_settings
from scenechat.services.runtime import clear_shutdown_request, request_shutdown


class SceneChatServer(uvicorn.Server):
    """Notify streaming responses before Uvicorn waits for them to close."""

    def handle_exit(self, sig: int, frame) -> None:
        request_shutdown()
        super().handle_exit(sig, frame)


def main() -> None:
    settings = get_settings()
    clear_shutdown_request()
    log_config = deepcopy(LOGGING_CONFIG)
    log_config["loggers"]["scenechat.vision.modeldeck"] = {
        "handlers": ["default"],
        "level": "INFO",
        "propagate": False,
    }
    config = uvicorn.Config(
        "scenechat.main:app",
        host=settings.scenechat_host,
        port=settings.scenechat_port,
        reload=False,
        access_log=False,
        log_level="warning",
        log_config=log_config,
    )
    SceneChatServer(config).run()


if __name__ == "__main__":
    main()
