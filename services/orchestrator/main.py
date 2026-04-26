from __future__ import annotations

import argparse
import os

import uvicorn

from agent_protocol.local_env import load_local_env
from services.orchestrator.app import create_app


def main():
    load_local_env(explicit_path=os.environ.get("AGENT_FIRST_ENV_FILE"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--sqlite", default=os.environ.get("ORCHESTRATOR_SQLITE", "./orchestrator.db"))
    args = parser.parse_args()

    app = create_app(sqlite_path=args.sqlite)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
