"""Generate the configuration module consumed by a packaged client."""

from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.build_config import write_packaged_module


if __name__ == "__main__":
    write_packaged_module(Path(__file__).resolve().parents[1] / "client" / "packaged_config.py")
