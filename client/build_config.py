"""Build-time generation of client configuration for an Android package.

The generated module is an artifact, not source: technical credentials are
read from the build environment and should never be committed or logged.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import os

from config import ConnectorConfig, load_connector_config

DEFAULT_API_URL = "http://87.239.135.39"
DEFAULT_API_PORT = "8002"


def build_values(environ: Mapping[str, str] | None = None) -> ConnectorConfig:
    """Validate values supplied to the package build without printing secrets."""

    source = dict(os.environ if environ is None else environ)
    source.setdefault("API_URL", DEFAULT_API_URL)
    source.setdefault("API_PORT", DEFAULT_API_PORT)
    return load_connector_config("__no_build_env_file__.env", environ=source)


def render_packaged_module(config: ConnectorConfig) -> str:
    """Render a Python module containing only build-selected constants."""

    return (
        "\"\"\"Generated client configuration; do not edit or commit.\"\"\"\n\n"
        f"API_URL = {config.url!r}\n"
        f"API_PORT = {config.port!r}\n"
        f"API_USER = {config.user!r}\n"
        f"API_PASSWORD = {config.password!r}\n"
    )


def write_packaged_module(
    output: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Write the generated module, creating its parent directory if needed."""

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_packaged_module(build_values(environ)), encoding="utf-8")
    return destination


__all__ = [
    "DEFAULT_API_PORT",
    "DEFAULT_API_URL",
    "build_values",
    "render_packaged_module",
    "write_packaged_module",
]
