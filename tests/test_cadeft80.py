import unittest

from cadeft80 import ParseError, ValidationError, RECORD_LENGTH, Detail80, parse_file80

SAMPLE = "\r\n".join([
    "ACOMPANY12C000002036600120",
    "XC430020366SHORT NAME15CARLONG NAME 30 CHARACTERS       0001000111234567        ",
    "C00000012340001000115678901     PAYEE PAYOR NAME 29 CHARS    3021                           ",
    "YC0000000100000000001234",
    "Z00000000000000000000000000000123400001",
])


CSV_ARGS = ["--mode", "csv", "--originator-id", "COMPANY12C", "--file-creation-number", "1",
            "--destination-data-centre", "20366", "--creation-date", "2026-01-01",
            "--due-date", "2026-01-05", "--short-name", "ACME", "--long-name", "ACME INC",
            "--return-institution-id", "001", "--return-transit", "00011",
            "--return-account", "1234567"]


class CsvTests(unittest.TestCase):
    def run_csv(self, text, *extra):
        import subprocess, sys
        return subprocess.run([sys.executable, "-m", "cadeft80", *CSV_ARGS, *extra], input=text.encode(),
                              capture_output=True)

    def test_csv_builds_valid_file(self):
        res = self.run_csv("name,institution id,transit,account,amount\nJane Doe,002,12345,987654,12.34\n")
        self.assertEqual(res.returncode, 0, res.stderr)
        eft = parse_file80(res.stdout.decode())
        eft.validate()
        detail = eft.batches[0].details[0]
        self.assertEqual((detail.amount, detail.institution_id, detail.name),
                         (1234, "000212345", "JANE DOE"))

    def test_csv_rejects_bad_header(self):
        res = self.run_csv("name,institution id,transit,account\nA,002,12345,1\n")
        self.assertEqual(res.returncode, 1)
        self.assertIn("header", res.stderr.decode())

    def test_csv_flags_all_invalid_rows_and_fif(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            fif = os.path.join(d, "fif.csv")
            with open(fif, "w") as f:
                f.write("Institution Number,Branch Transit Number\n0002,12345\n")
            res = self.run_csv("name,institution id,transit,account,amount\n"
                               "OK,002,12345,1,1.00\nBAD,002,99999,1,1.00\nBAD2,002,12345,1,x\n",
                               "--fif", fif)
        err = res.stderr.decode()
        self.assertEqual(res.returncode, 1)
        self.assertIn("2 invalid row(s)", err)
        self.assertIn("line 3", err)
        self.assertIn("line 4", err)


class FifPdfTests(unittest.TestCase):
    def test_parse_routing_pairs(self):
        from cadeft80.fif_pdf import parse_fif_text
        text = ("100 MILE HOUSE, BC\n001000550 00550-010 CANADIAN IMPERIAL BANK OF COMMERCE 100 Mile House "
                "Banking Centre, 1-325 Birch Ave, Box 98, 100 Mile 001000550 00550-010\n"
                "000200123 00123-999 MISMATCH\n")
        self.assertEqual(parse_fif_text(text), [("010", "00550")])


class FifFetchTests(unittest.TestCase):
    def test_find_latest_url(self):
        from cadeft80.fif_fetch import find_latest_url
        html = ('<a href="/sites/default/files/2026-10-01-Banks_Numeric_List.pdf">a</a>'
                '<a href="https://www.payments.ca/sites/default/files/2026-11-20-Banks_Numeric_List.pdf">b</a>')
        self.assertEqual(find_latest_url(html),
                         "https://www.payments.ca/sites/default/files/2026-11-20-Banks_Numeric_List.pdf")


class Eft80Tests(unittest.TestCase):
    def test_rejects_non_spec_characters(self):
        bad = SAMPLE.replace("PAYEE PAYOR", "PAYEE/PAYOR")
        with self.assertRaises(ParseError):
            parse_file80(bad)

    def test_create_defaults_to_crlf(self):
        out = parse_file80(SAMPLE).create()
        self.assertTrue(out.endswith("\r\n"))
        self.assertEqual(out.count("\r\n"), out.count("\n"))

    def test_parse_sample(self):
        eft = parse_file80(SAMPLE)
        eft.validate()
        self.assertEqual(eft.header.originator_id, "COMPANY12C")
        batch = eft.batches[0]
        self.assertEqual(batch.header.short_name, "SHORT NAME15CAR")
        self.assertEqual(batch.header.return_account_no, "1234567")
        detail = batch.details[0]
        self.assertEqual((detail.amount, detail.institution_id, detail.account_no),
                         (1234, "000100011", "5678901"))
        self.assertEqual(detail.name, "PAYEE PAYOR NAME 29 CHARS")
        self.assertEqual(detail.cross_reference, "3021")
        self.assertEqual(eft.footer.credit_amount, 1234)

    def test_create_round_trip_is_80_wide(self):
        eft = parse_file80(SAMPLE)
        out = eft.create()
        lines = out.split("\r\n")[:-1]
        self.assertTrue(all(len(line) == RECORD_LENGTH for line in lines))
        self.assertEqual([l.rstrip() for l in lines], [l.rstrip() for l in SAMPLE.split("\r\n")])
        self.assertEqual(parse_file80(out).to_dict(), eft.to_dict())

    def test_only_crlf_accepted(self):
        for eol in ("\n", "\r"):
            with self.assertRaises(ParseError):
                parse_file80(SAMPLE.replace("\r\n", eol))
        with self.assertRaises(ParseError):
            parse_file80(SAMPLE.replace("\r\nZ", "\nZ"))

    def test_bad_footer(self):
        eft = parse_file80(SAMPLE.replace("00001", "00002", 1)[:-5] + "00002")
        with self.assertRaises(ValidationError):
            eft.validate()

    def test_errors(self):
        with self.assertRaises(ParseError):
            parse_file80(SAMPLE.replace("\r\nZ00000000000000000000000000000123400001", ""))
        with self.assertRaises(ParseError):
            parse_file80("Y")
        with self.assertRaises(ValidationError):
            Detail80("D", 1, "000100011", "123", "N", "X" * 16).build()


if __name__ == "__main__":
    unittest.main()
