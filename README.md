# cadeft80

[![Python](https://github.com/protoconal/cadeft/actions/workflows/python.yml/badge.svg)](https://github.com/protoconal/cadeft/actions/workflows/python.yml)
[![Apache 2 License](https://img.shields.io/badge/license-Apache2-blue.svg)](LICENSE)

`cadeft80` is a dependency-free Python library for reading and writing the 80-byte (TD) Electronic Funds
Transfer (EFT) file format: fixed 80-character A/X/C/D/Y/Z records. The CPA 005 1464-byte standard format
is not supported.

Derived from [moov-io/cadeft](https://github.com/moov-io/cadeft) (Go). See [Attribution](#attribution).

## Installation

```sh
pip install cadeft80
```

Requires Python 3.10+.

## Usage

Trailing blanks may be trimmed on input, non-spec characters are rejected, records must be delimited by CRLF
on input (bare CR or LF is rejected), output is CRLF-terminated by default, and batch controls and the footer
are computed on output:

```python
from cadeft80 import parse_file80

eft_file = parse_file80(open("td_fees.txt", newline="").read())
eft_file.validate()
print(eft_file.create())  # CRLF by default; pass eol= to override
```

## Command line

```sh
python -m cadeft80 --mode parse --file eft_file.txt   # EFT -> JSON
python -m cadeft80 --mode build --file eft_file.txt   # validate and re-emit
```

CSV to EFT: the header must be exactly `name,institution id,transit,account,amount` (amount in dollars,
institution id 3 digits, transit 5 digits). All invalid rows are reported (with line numbers) and no file is written.
`--fif` optionally checks each institution + transit against a Payments Canada FIF export, as a CSV or a SQLite
database (`--fif-table`, default `fif`). It needs `institution`/`transit` columns (e.g. `Institution Number`,
`Branch Transit Number`) or one combined `routing number` column.

```sh
python -m cadeft80 --mode csv --file payees.csv --fif fif.csv \
  --originator-id COMPANY12C --file-creation-number 1 --destination-data-centre 20366 \
  --due-date 2026-12-01 --short-name "ACME PAYROLL" --long-name "ACME INC PAYROLL" \
  --return-institution-id 001 --return-transit 00011 --return-account 1234567 > eft.txt
```

Build a FIF lookup CSV from the Payments Canada FIF PDF (needs `pypdf` or `pdftotext`; only the `001000550 00550-010`
routing pairs are read), then pass it, or the PDF itself, to `--fif`:

```sh
python -m cadeft80 --mode fif --file fif.pdf > fif.csv
python -m cadeft80 --mode fif --latest > fif.csv   # fetch the newest PDF from payments.ca
```

## Testing

```sh
python -m unittest discover -s tests
```

## Releasing

Update the version in `pyproject.toml` and `CHANGELOG.md`, then push a tag (`git tag v0.2.0 && git push origin v0.2.0`).
The release workflow builds the package, creates the GitHub release, and publishes
to PyPI via [trusted publishing](https://docs.pypi.org/trusted-publishers/) (configure the `pypi` environment).

## Project status

cadeft80 is currently being developed for use in multiple production environments. The library was developed in large part by [Synctera](https://synctera.com/). Please star the project if you are interested in its progress. Let us know if you encounter any bugs/unclear documentation or have feature suggestions by opening up an issue or pull request. Thanks!

## Attribution

This project is a derivative work of [moov-io/cadeft](https://github.com/moov-io/cadeft),
Copyright 2023 Moov.IO, licensed under the Apache License 2.0. The Go sources were re-implemented in
Python. See [NOTICE](NOTICE).

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
