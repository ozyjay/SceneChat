"""Run SceneChat with `python -m scenechat`."""

import uvicorn

from scenechat.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "scenechat.main:app",
        host=settings.scenechat_host,
        port=settings.scenechat_port,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
