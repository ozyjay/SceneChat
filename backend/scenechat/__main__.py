"""Run SceneChat with `python -m scenechat`."""

import uvicorn

from scenechat.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "scenechat.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
