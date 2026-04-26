from __future__ import annotations

import os
from pathlib import Path


def load_local_env(
    *,
    explicit_path: str | None = None,
    default_candidates: tuple[str, ...] = (".env.local", ".env"),
) -> str | None:
    """Load KEY=VALUE lines into os.environ (without overriding existing vars).

    This keeps local developer setup simple (no terminal exports required)
    while still allowing shell-provided vars to take precedence.
    """
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    else:
        for rel in default_candidates:
            candidates.append(Path(rel))

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and os.environ.get(key) is None:
                os.environ[key] = value
        return str(path)
    return None
