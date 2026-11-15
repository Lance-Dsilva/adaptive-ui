"""Read server-only configuration without exposing credential values."""

import os
from pathlib import Path


def load_settings(root: Path) -> dict[str, str]:
    default_model = "gpt-5-mini"
    values = {"OPENAI_MODEL": default_model}
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
    model = values["OPENAI_MODEL"].strip()
    if len(model) > 1 and model[0] in ("'", '"') and model[0] == model[-1]:
        model = model[1:-1].strip()
    values["OPENAI_MODEL"] = model or default_model
    return values
