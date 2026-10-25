"""ASGI entrypoint for SGF-AP."""

from api.config import load_api_config
from api.sgfap_api import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn

    config = load_api_config()
    uvicorn.run(app, host="0.0.0.0", port=config.port)
