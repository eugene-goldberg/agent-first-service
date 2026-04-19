from __future__ import annotations

import argparse
import os
import pathlib

import uvicorn

from services.projects.app import create_app
from services.projects.seed import load_seed

_DEFAULT_DB = pathlib.Path(os.getenv("PROJECTS_DB", "data/projects.db"))
_DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)

app = create_app(sqlite_path=_DEFAULT_DB)

# If PROJECTS_SEED is set (env var, used when loaded by uvicorn --reload) apply on import.
_SEED_FROM = os.getenv("PROJECTS_SEED")
if _SEED_FROM:
    load_seed(app.state.session_maker, _SEED_FROM)


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-from", type=pathlib.Path, default=None)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.seed_from:
        load_seed(app.state.session_maker, args.seed_from)

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    _main()
