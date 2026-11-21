"""Run with: python3 -m unittest discover tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import avir  # noqa: E402

# Published 32-bit codes (MSB-first, as manufacturers and LIRC write them) for buttons in the
# library. Each library entry must decode from one of these, so a typo in a file fails here.
PUBLISHED = {
    "library/displays/lg-tv.ir": ("nec", {
        "Power": "20DF10EF", "Power_on": "20DF23DC", "Power_off": "20DFA35C", "Vol_up": "20DF40BF",
        "Vol_dn": "20DFC03F", "Mute": "20DF906F", "Ch_next": "20DF00FF", "Ch_prev": "20DF807F",
        "Input": "20DFD02F"}),
    "library/displays/samsung-tv.ir": ("samsung32", {
        "Power": "E0E040BF", "Power_on": "E0E09966", "Power_off": "E0E019E6", "Vol_up": "E0E0E01F",
        "Vol_dn": "E0E0D02F", "Mute": "E0E0F00F", "Ch_next": "E0E048B7", "Ch_prev": "E0E008F7",
        "Input": "E0E0807F"}),
    "library/projectors/epson.ir": ("necext", {"Power": "C1AA09F6"}),
}

# Sony SIRC codes are written as (device, command) in Sony's tables.
SONY_TV = {"Power": 21, "Power_on": 46, "Power_off": 47, "Vol_up": 18, "Vol_dn": 19, "Mute": 20,
           "Ch_next": 16, "Ch_prev": 17, "Input": 37}


def signals(rel):
    _, sigs, _ = avir.parse(os.path.join(avir.ROOT, rel))
    return {s.name: s.f for s in sigs}


class Library(unittest.TestCase):
    def test_every_file_validates(self):
        for path in avir.library_files():
            problems = avir.validate_file(path)[0]
            self.assertEqual(problems, [], path)

    def test_codes_match_published_codes(self):
        for rel, (proto, codes) in PUBLISHED.items():
            got = signals(rel)
            self.assertEqual(set(got), set(codes), rel)
            for name, code in codes.items():
                p, a, c = avir.decode(proto, code)
                self.assertEqual((got[name]["protocol"], got[name]["address"], got[name]["command"]), (p, a, c),
                                 f"{rel} {name}")

    def test_sony_codes(self):
        got = signals("library/displays/sony-tv.ir")
        self.assertEqual(set(got), set(SONY_TV))
        for name, cmd in SONY_TV.items():
            self.assertEqual(got[name]["protocol"], "SIRC")
            self.assertEqual(got[name]["address"], "01 00 00 00")
            self.assertEqual(got[name]["command"], f"{cmd:02X} 00 00 00", name)

    def test_generated_files_are_current(self):
        self.assertEqual(avir.main(["catalog", "--check"]), 0)
        self.assertEqual(avir.main(["universal", "--check"]), 0)


class Validator(unittest.TestCase):
    def check(self, body, header=True):
        text = "Filetype: IR signals file\nVersion: 1\n"
        if header:
            text += "# Brand: X\n# Models: Y\n# Source: Z\n# Tested: no\n"
        text += body
        with tempfile.NamedTemporaryFile("w", suffix=".ir", delete=False) as f:
            f.write(text)
        try:
            return [m for _, _, m in avir.validate_file(f.name)[0]]
        finally:
            os.unlink(f.name)

    def test_good(self):
        self.assertEqual(self.check("#\nname: Power\ntype: parsed\nprotocol: NEC\naddress: 04 00 00 00\ncommand: 08 00 00 00\n"), [])

    def test_raw_good(self):
        self.assertEqual(self.check("#\nname: Power\ntype: raw\nfrequency: 38000\nduty_cycle: 0.330000\ndata: 9000 4500 560 560\n"), [])

    def test_problems(self):
        msgs = self.check(
            "#\nname: Power\ntype: parsed\nprotocol: NEC\naddress: 104 00 00 00\ncommand: 08 00 00 00\n"
            "#\nname: Power\ntype: parsed\nprotocol: SIRC\naddress: 20 00 00 00\ncommand: 08 00 00 00\n"
            "#\nname: Volume_Up\ntype: parsed\nprotocol: Foo\naddress: 00 00 00 00\ncommand: 00 00 00 00\n"
            "#\nname: Mute\ntype: raw\nfrequency: 5\nduty_cycle: 2\ndata: 9000 -1\n", header=False)
        joined = "\n".join(msgs)
        for expected in ["missing '# Brand:'", "four uppercase hex bytes", "already defined", "above SIRC",
                         "not in the naming list", "protocol 'Foo'", "frequency", "duty_cycle", "positive whole"]:
            self.assertIn(expected, joined)


class Decode(unittest.TestCase):
    def test_nec(self):
        self.assertEqual(avir.decode("nec", "20DF10EF"), ("NEC", "04 00 00 00", "08 00 00 00"))

    def test_nec_rejects_extended(self):
        with self.assertRaises(ValueError):
            avir.decode("nec", "C1AA09F6")

    def test_necext(self):
        self.assertEqual(avir.decode("necext", "0xC1AA09F6"), ("NECext", "83 55 00 00", "90 6F 00 00"))

    def test_samsung(self):
        self.assertEqual(avir.decode("samsung32", "E0E040BF"), ("Samsung32", "07 00 00 00", "02 00 00 00"))


if __name__ == "__main__":
    unittest.main()
