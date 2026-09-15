#!/usr/bin/env python3
"""Run KROSH in the browser.

    python run_web.py            then open http://127.0.0.1:5000
"""
import argparse

from krosh.web import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"KROSH is running at http://{args.host}:{args.port}")
    create_app().run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
