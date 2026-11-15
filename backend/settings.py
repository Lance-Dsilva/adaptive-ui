"""Read server-only configuration without exposing credential values."""

import os
from pathlib import Path


def load_settings(root: Path) -> dict[str, str]:
    values = {"OPENAI_MODEL": "gpt-5-mini"}
    path = root / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key = key.strip()
            if separator and key in {"OPENAI_API_KEY", "OPENAI_MODEL"}:
                values[key] = value.strip().strip("'\"")
    for key in ("OPENAI_API_KEY", "OPENAI_MODEL"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values
