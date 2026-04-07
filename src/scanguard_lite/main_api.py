from __future__ import annotations

import uvicorn

from .api import create_app
from .config import load_config


def main() -> None:
    cfg = load_config()
    app = create_app(sqlite_path=cfg.api["sqlite_path"])
    uvicorn.run(app, host=cfg.api["host"], port=cfg.api["port"])


if __name__ == "__main__":
    main()
