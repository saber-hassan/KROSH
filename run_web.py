#!/usr/bin/env python3
"""Run KROSH in the browser.

Local:       python run_web.py        then open http://127.0.0.1:5000
Production:  gunicorn --workers 1 --timeout 120 "krosh.web:create_app()"

Only ever run ONE worker. Games are held in process memory, so a second
worker has its own empty dict and a player's next click would land on a
process that has never heard of their game.
"""
import argparse
import os

from krosh.web import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"KROSH is running at http://{args.host}:{args.port}")
    create_app().run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
