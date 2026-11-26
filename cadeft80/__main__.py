"""Command-line interface for cadeft80: validates and re-emits an 80-byte EFT file."""

from __future__ import annotations

import argparse
import json
import sys

from . import parse_file80


def main() -> int:
    parser = argparse.ArgumentParser(prog="cadeft80")
    parser.add_argument("--mode", required=True, choices=("parse", "build"))
    parser.add_argument("--file", default="")
    args = parser.parse_args()
    try:
        if args.file:
            with open(args.file, encoding="utf-8", newline="") as source:
                text = source.read()
        else:
            text = sys.stdin.buffer.read().decode("utf-8")
        eft_file = parse_file80(text)
        if args.mode == "parse":
            sys.stdout.write(json.dumps(eft_file.to_dict(), separators=(",", ":")))
        else:
            sys.stdout.write(eft_file.create())
        return 0
    except Exception as exc:
        print(f"cadeft80: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
