from __future__ import annotations

import argparse
import os

import uvicorn

from services.communications.app import create_app
from services.communications.db import Base, make_engine, make_sessionmaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--sqlite", default=os.environ.get("COMMUNICATIONS_SQLITE", "./communications.db"))
    parser.add_argument("--seed-from", default=os.environ.get("COMMUNICATIONS_SEED"))
    args = parser.parse_args()

    engine = make_engine(f"sqlite:///{args.sqlite}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)

    if args.seed_from:
        from services.communications.seed import load_seed

        load_seed(session_maker, args.seed_from)

    app = create_app(session_maker=session_maker)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
