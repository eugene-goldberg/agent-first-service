from __future__ import annotations

import pathlib
import sys

# Ensure the repo root is on sys.path for the `services.*` and `agent_protocol.*` packages
_REPO = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
