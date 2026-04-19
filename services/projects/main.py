from __future__ import annotations

import os
import pathlib

from services.projects.app import create_app

_DEFAULT_DB = pathlib.Path(os.getenv("PROJECTS_DB", "data/projects.db"))
_DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)

app = create_app(sqlite_path=_DEFAULT_DB)
