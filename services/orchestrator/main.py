from __future__ import annotations

import argparse
import os

import uvicorn

from services.orchestrator.app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--sqlite", default=os.environ.get("ORCHESTRATOR_SQLITE", "./orchestrator.db"))
    args = parser.parse_args()

    app = create_app(sqlite_path=args.sqlite)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
