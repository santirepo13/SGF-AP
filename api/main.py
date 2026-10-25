"""ASGI entrypoint for SGF-AP."""

from __future__ import annotations

from pathlib import Path
import sys


if __package__ in (None, ""):
    _PACKAGE_DIRECTORY = Path(__file__).resolve().parent
    _PROJECT_DIRECTORY = _PACKAGE_DIRECTORY.parent
    sys.path[:] = [
        entry
        for entry in sys.path
        if Path(entry or ".").resolve() != _PACKAGE_DIRECTORY
    ]
    sys.path.insert(0, str(_PROJECT_DIRECTORY))

from api.config import load_api_config
from api.sgfap_api import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = load_api_config()
    uvicorn.run(app, host="0.0.0.0", port=config.port)
