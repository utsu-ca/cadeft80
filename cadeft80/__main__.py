"""Command-line interface for cadeft80: validates and re-emits an 80-byte EFT file."""

from __future__ import annotations

import argparse
import json
import sys

from . import parse_file80
from .fif_pdf import parse_fif_text, pdf_to_text, write_fif_csv
from .csv_eft import add_csv_arguments, build_from_csv


def main() -> int:
    parser = argparse.ArgumentParser(prog="cadeft80")
    parser.add_argument("--mode", required=True, choices=("parse", "build", "csv", "fif"))
    parser.add_argument("--file", default="", help="input file (default: stdin)")
    parser.add_argument("--latest", action="store_true",
                        help="fif mode: download the latest Banks Numeric List PDF from payments.ca")
    add_csv_arguments(parser)
    args = parser.parse_args()
    try:
        if args.mode == "fif":
            if args.latest:
                from .fif_fetch import download_latest
                path = download_latest()
                print(f"cadeft80: downloaded {path}", file=sys.stderr)
            elif args.file:
                path = args.file
            else:
                raise ValueError("--file (FIF PDF) or --latest is required")
            write_fif_csv(parse_fif_text(pdf_to_text(path)), sys.stdout)
            return 0
        if args.mode == "csv":
            sys.stdout.write(build_from_csv(args))
            return 0
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
