"""CSV -> 80-byte EFT conversion used by `cadeft80 --mode csv`."""

from __future__ import annotations

import argparse
import csv
import io
import re
import sqlite3
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

from . import Batch80, BatchHeader80, CadeftError, Detail80, File80, Header80

COLUMNS = ("name", "institution id", "transit", "account", "amount")
_FIF_INSTITUTION = ("institution id", "institution number", "institution", "institution_id", "institution_number")
_FIF_TRANSIT = ("transit", "branch transit number", "transit number", "branch number", "branch", "transit_number")


def add_csv_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("csv mode (--mode csv)")
    group.add_argument("--originator-id", help="originator id (A record)")
    group.add_argument("--file-creation-number", type=int, help="file creation number (1-9999)")
    group.add_argument("--destination-data-centre", type=int, help="destination data centre (5 digits)")
    group.add_argument("--creation-date", type=date.fromisoformat, default=None,
                       help="file creation date, YYYY-MM-DD (default: today)")
    group.add_argument("--due-date", type=date.fromisoformat, help="batch due date, YYYY-MM-DD")
    group.add_argument("--payment-type", choices=("C", "D"), default="C",
                       help="C = credits, D = debits (default: C)")
    group.add_argument("--transaction-type", default="450", help="3-digit transaction type (default: 450)")
    group.add_argument("--short-name", help="batch short name (max 15 chars)")
    group.add_argument("--long-name", help="batch long name (max 30 chars)")
    group.add_argument("--return-institution-id", help="return institution (3 digits, or 4 as 0BBB)")
    group.add_argument("--return-transit", help="return transit number (5 digits)")
    group.add_argument("--return-account", help="return account number")
    group.add_argument("--fif", help="Payments Canada FIF lookup (CSV, or SQLite .db/.sqlite/.sqlite3); "
                       "rows whose institution + transit are not listed are flagged")
    group.add_argument("--fif-table", default="fif", help="SQLite table holding the FIF (default: fif)")


def _institution(value: str, what: str) -> str:
    if re.fullmatch(r"[0-9]{3}", value):
        return "0" + value
    if re.fullmatch(r"0[0-9]{3}", value):
        return value
    raise CadeftError(f"{what} must be 3 digits (or 4 as 0BBB): {value!r}")


def _transit(value: str, what: str) -> str:
    if not re.fullmatch(r"[0-9]{5}", value):
        raise CadeftError(f"{what} must be 5 digits: {value!r}")
    return value


def _cents(value: str, what: str) -> int:
    try:
        amount = Decimal(value.strip())
    except InvalidOperation:
        raise CadeftError(f"{what} is not a number: {value!r}") from None
    cents = amount * 100
    if cents != cents.to_integral_value() or cents <= 0:
        raise CadeftError(f"{what} must be a positive amount with at most 2 decimals: {value!r}")
    return int(cents)


def _norm(value: str) -> str:
    return value.strip().lower()


def _split(value: str, what: str) -> tuple[str, str]:
    """Normalize FIF values to (0BBB, TTTTT); tolerates 3-digit institutions."""
    value = value.strip()
    return _institution(value[:-5] if len(value) > 5 else value, what), value[-5:]


def load_fif(path: str, table: str) -> set[tuple[str, str]]:
    """Returns {(0BBB, TTTTT)}. CSV/SQLite need an institution column and a transit column (by header name);
    a single combined 0BBBTTTTT / BBBTTTTT column named 'routing number' is also accepted."""
    if path.lower().endswith(".pdf"):
        from .fif_pdf import parse_fif_text, pdf_to_text
        return {("0" + b, t) for b, t in parse_fif_text(pdf_to_text(path))}
    if path.lower().endswith((".db", ".sqlite", ".sqlite3")):
        if not re.fullmatch(r"\w+", table):
            raise CadeftError(f"invalid --fif-table: {table!r}")
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            cur = db.execute(f'SELECT * FROM "{table}"')
            names = [_norm(d[0]) for d in cur.description]
            rows = [[("" if v is None else str(v)) for v in r] for r in cur]
    else:
        with open(path, encoding="utf-8-sig", newline="") as source:
            data = list(csv.reader(source))
        if not data:
            raise CadeftError(f"FIF file {path} is empty")
        names, rows = [_norm(n) for n in data[0]], data[1:]

    def find(options):
        return next((names.index(o) for o in options if o in names), None)

    inst, transit = find(_FIF_INSTITUTION), find(_FIF_TRANSIT)
    combined = find(("routing number", "routing_number", "routing"))
    if (inst is None or transit is None) and combined is None:
        raise CadeftError(f"FIF {path}: could not find institution and transit columns in {names}")
    out = set()
    for row in rows:
        try:
            if inst is not None and transit is not None:
                out.add((_institution(row[inst].strip().zfill(3) if len(row[inst].strip()) < 4
                                      else row[inst].strip(), "fif"), row[transit].strip().zfill(5)))
            else:
                out.add(_split(row[combined].strip().zfill(8), "fif"))
        except (CadeftError, IndexError):
            continue
    if not out:
        raise CadeftError(f"FIF {path} contains no usable routing numbers")
    return out


def _require(args: argparse.Namespace, *names: str) -> None:
    missing = [f"--{n.replace('_', '-')}" for n in names if getattr(args, n) in (None, "")]
    if missing:
        raise CadeftError("missing required flags: " + ", ".join(missing))


def build_from_csv(args: argparse.Namespace) -> str:
    _require(args, "originator_id", "file_creation_number", "destination_data_centre", "due_date",
             "short_name", "long_name", "return_institution_id", "return_transit", "return_account")
    if args.file:
        with open(args.file, encoding="utf-8", newline="") as source:
            text = source.read()
    else:
        text = sys.stdin.buffer.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""))
    header = [_norm(h) for h in reader.fieldnames or []]
    reader.fieldnames = header
    if header != list(COLUMNS):
        raise CadeftError("CSV header must be: " + ",".join(COLUMNS) + "; got: " + ",".join(header))
    fif = load_fif(args.fif, args.fif_table) if args.fif else None

    details, errors = [], []
    for row in reader:
        line = reader.line_num
        if not any((v or "").strip() for v in row.values() if v is not None):
            continue
        try:
            if None in row or any(v is None for v in row.values()):
                raise CadeftError("wrong number of columns")
            institution = _institution(row["institution id"].strip(), "institution id")
            transit = _transit(row["transit"].strip(), "transit")
            if fif is not None and (institution, transit) not in fif:
                raise CadeftError(f"routing number {institution[1:]}-{transit} not found in FIF")
            detail = Detail80(
                record_type=args.payment_type,
                amount=_cents(row["amount"], "amount"),
                institution_id=institution + transit,
                account_no=row["account"].strip(),
                name=row["name"].strip().upper(),
            )
            if not detail.name:
                raise CadeftError("name is required")
            detail.validate()
            details.append(detail)
        except CadeftError as exc:
            errors.append(f"line {line}: {exc}")
    if errors:
        raise CadeftError(f"{len(errors)} invalid row(s):\n  " + "\n  ".join(errors))
    if not details:
        raise CadeftError("CSV contains no data rows")

    eft_file = File80(
        header=Header80(
            originator_id=args.originator_id,
            file_creation_number=args.file_creation_number,
            creation_date=args.creation_date or date.today(),
            destination_data_centre=args.destination_data_centre,
        ),
        batches=[Batch80(
            header=BatchHeader80(
                payment_type=args.payment_type,
                transaction_type=args.transaction_type,
                due_date=args.due_date,
                short_name=args.short_name.upper(),
                long_name=args.long_name.upper(),
                return_institution_id=_institution(args.return_institution_id, "--return-institution-id")
                + _transit(args.return_transit, "--return-transit"),
                return_account_no=args.return_account,
            ),
            details=details,
        )],
    )
    return eft_file.create()
