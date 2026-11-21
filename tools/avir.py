#!/usr/bin/env python3
"""Flipper-AVIR tool: validate the library, build the catalog and universal files, decode codes.

  python3 tools/avir.py validate [FILES...]   check .ir files (default: the whole library)
  python3 tools/avir.py catalog [--check]     write CATALOG.md (--check: fail if it is out of date)
  python3 tools/avir.py universal [--check]   write universal/*.ir (--check: fail if out of date)
  python3 tools/avir.py decode nec 20DF10EF   turn a published 32-bit code into Flipper's form
                         (protocols: nec, necext, samsung32)

No dependencies beyond Python 3.8.
"""

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY = os.path.join(ROOT, "library")

# Largest address / command each protocol takes, as Flipper firmware checks them.
PROTOCOLS = {
    "NEC": (0xFF, 0xFF), "NECext": (0xFFFF, 0xFFFF), "NEC42": (0x1FFF, 0xFF),
    "NEC42ext": (0x3FFFFFF, 0xFFFF), "Samsung32": (0xFF, 0xFF), "RC5": (0x1F, 0x3F),
    "RC5X": (0x1F, 0x7F), "RC6": (0xFF, 0xFF), "SIRC": (0x1F, 0x7F), "SIRC15": (0xFF, 0x7F),
    "SIRC20": (0x1FFF, 0x7F), "Kaseikyo": (0x3FFFFFF, 0x3FF), "RCA": (0xF, 0xFF), "Pioneer": (0xFF, 0xFF),
}

# Button names. The first group matches Flipper's own universal remotes, so files work with them.
NAMES = {
    "Power", "Vol_up", "Vol_dn", "Mute", "Ch_next", "Ch_prev",
    "Power_on", "Power_off", "Input", "Input_next",
    "HDMI_1", "HDMI_2", "HDMI_3", "HDMI_4", "DP", "VGA", "DVI", "USB_C", "HDBaseT",
    "Freeze", "Blank", "Blank_on", "Blank_off", "Aspect", "Menu", "Exit", "Enter",
    "Up", "Down", "Left", "Right", "Info", "Lamp", "Eco",
}
REQUIRED_HEADERS = ("Brand", "Models", "Source", "Tested")


class Signal:
    def __init__(self, fields, line):
        self.f = fields
        self.line = line

    @property
    def name(self):
        return self.f.get("name", "")


def parse(path):
    """(headers, signals, problems) for one .ir file."""
    problems = []
    headers, signals = {}, []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if len(lines) < 2 or lines[0].strip() != "Filetype: IR signals file" or lines[1].strip() != "Version: 1":
        problems.append((1, "must start with 'Filetype: IR signals file' and 'Version: 1'"))
    current, start = None, 0
    for n, raw in enumerate(lines[2:], start=3):
        line = raw.rstrip("\r")
        if raw.endswith("\r"):
            problems.append((n, "Windows line ending; use LF"))
        if line.startswith("#"):
            m = re.match(r"#\s*(\w+):\s*(.*)$", line)
            if m and current is None and not signals:
                headers[m.group(1)] = m.group(2).strip()
            continue
        if not line.strip():
            continue
        m = re.match(r"(\w+):\s*(.*)$", line)
        if not m:
            problems.append((n, f"cannot read line: {line!r}"))
            continue
        key, value = m.group(1), m.group(2).strip()
        if key == "name":
            current = Signal({}, n)
            signals.append(current)
        elif current is None:
            problems.append((n, f"'{key}' before any 'name:'"))
            continue
        if key in current.f:
            problems.append((n, f"'{key}' given twice in one signal"))
        current.f[key] = value
    return headers, signals, problems


def le_value(text):
    """'83 55 00 00' -> 0x5583, or None if it is not four hex bytes."""
    parts = text.split()
    if len(parts) != 4 or not all(re.fullmatch(r"[0-9A-F]{2}", p) for p in parts):
        return None
    return int.from_bytes(bytes(int(p, 16) for p in parts), "little")


def validate_file(path):
    headers, signals, problems = parse(path)
    rel = os.path.relpath(path, ROOT)
    for h in REQUIRED_HEADERS:
        if not headers.get(h):
            problems.append((1, f"missing '# {h}:' header"))
    tested = headers.get("Tested", "")
    if tested and not re.match(r"(no|yes\b.*)$", tested):
        problems.append((1, "'# Tested:' must be 'no' or 'yes, <model>, <date>'"))
    if not signals:
        problems.append((1, "no signals"))
    seen = {}
    for s in signals:
        name = s.name
        if name not in NAMES:
            problems.append((s.line, f"name '{name}' is not in the naming list (see CONTRIBUTING.md)"))
        if name in seen:
            problems.append((s.line, f"'{name}' already defined on line {seen[name]}"))
        seen[name] = s.line
        kind = s.f.get("type")
        if kind == "parsed":
            proto = s.f.get("protocol")
            if proto not in PROTOCOLS:
                problems.append((s.line, f"protocol '{proto}' is not one Flipper decodes"))
                continue
            max_a, max_c = PROTOCOLS[proto]
            for field, top in (("address", max_a), ("command", max_c)):
                text = s.f.get(field)
                if text is None:
                    problems.append((s.line, f"'{name}' has no {field}"))
                    continue
                v = le_value(text)
                if v is None:
                    problems.append((s.line, f"'{name}' {field} must be four uppercase hex bytes, e.g. '04 00 00 00'"))
                elif v > top:
                    problems.append((s.line, f"'{name}' {field} 0x{v:X} is above {proto}'s 0x{top:X}"))
            extra = set(s.f) - {"name", "type", "protocol", "address", "command"}
            if extra:
                problems.append((s.line, f"'{name}' has fields a parsed signal doesn't use: {sorted(extra)}"))
        elif kind == "raw":
            freq = s.f.get("frequency", "")
            duty = s.f.get("duty_cycle", "")
            data = s.f.get("data", "").split()
            if not freq.isdigit() or not 10000 <= int(freq) <= 100000:
                problems.append((s.line, f"'{name}' frequency must be 10000-100000 Hz"))
            try:
                if not 0 < float(duty) <= 1:
                    raise ValueError
            except ValueError:
                problems.append((s.line, f"'{name}' duty_cycle must be between 0 and 1"))
            if not data or not all(d.isdigit() and int(d) > 0 for d in data):
                problems.append((s.line, f"'{name}' data must be positive whole microsecond durations"))
            elif len(data) > 1024:
                problems.append((s.line, f"'{name}' has {len(data)} timings; Flipper keeps at most 1024"))
        else:
            problems.append((s.line, f"'{name}' type must be 'parsed' or 'raw'"))
    return [(rel, line, msg) for line, msg in problems], headers, signals


def library_files():
    return sorted(glob.glob(os.path.join(LIBRARY, "**", "*.ir"), recursive=True))


# ------------------------------------------------------------------------------ catalog

def build_catalog():
    rows = []
    for path in library_files():
        _, headers, signals = validate_file(path)
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        category = os.path.basename(os.path.dirname(path)).capitalize()
        protos = sorted({s.f.get("protocol", "raw") for s in signals})
        rows.append((category, headers.get("Brand", "?"), rel, ", ".join(s.name for s in signals),
                     "/".join(protos), headers.get("Tested", "no")))
    out = ["# Catalog", "",
           "Generated by `python3 tools/avir.py catalog`. Do not edit by hand.", "",
           "| Category | Brand | File | Buttons | Protocol | Tested on hardware |",
           "|---|---|---|---|---|---|"]
    for cat, brand, rel, buttons, proto, tested in rows:
        out.append(f"| {cat} | {brand} | [`{rel}`]({rel}) | {buttons} | {proto} | {tested} |")
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------------------ universal files

UNIVERSAL = {
    # file name: (library folder, buttons to gather)
    "av-displays.ir": ("displays", ["Power", "Power_on", "Power_off", "Vol_up", "Vol_dn", "Mute", "Input"]),
    "av-projectors.ir": ("projectors", ["Power", "Power_on", "Power_off", "Blank", "Freeze", "Input"]),
}


def build_universal():
    """Flipper's universal-remote format: one file, many signals per button name, sent in turn."""
    files = {}
    for fname, (folder, buttons) in UNIVERSAL.items():
        lines = ["Filetype: IR library file", "Version: 1",
                 f"# Generated by tools/avir.py universal from library/{folder}/. Do not edit by hand."]
        for button in buttons:
            for path in library_files():
                if os.path.basename(os.path.dirname(path)) != folder:
                    continue
                headers, signals, _ = parse(path)
                for s in signals:
                    if s.name == button:
                        lines.append(f"# {headers.get('Brand', '?')}")
                        lines.append(f"name: {s.name}")
                        for key in ("type", "protocol", "address", "command", "frequency", "duty_cycle", "data"):
                            if key in s.f:
                                lines.append(f"{key}: {s.f[key]}")
        files[fname] = "\n".join(lines) + "\n"
    return files


# ------------------------------------------------------------------------------ decoding

def rev8(b):
    return int(f"{b:08b}"[::-1], 2)


def decode(protocol, code):
    """Published 32-bit code (MSB-first, as remotes' manuals and LIRC write it) -> (protocol, address, command)."""
    code = re.sub(r"^0X", "", code.strip().upper())
    if not re.fullmatch(r"[0-9A-F]{8}", code):
        raise ValueError("give eight hex digits, e.g. 20DF10EF")
    b = [rev8(int(code[i:i + 2], 16)) for i in range(0, 8, 2)]
    p = protocol.lower()
    if p == "nec":
        if b[1] != b[0] ^ 0xFF:
            raise ValueError("address byte isn't followed by its inverse: try necext")
        if b[3] != b[2] ^ 0xFF:
            raise ValueError("command byte isn't followed by its inverse")
        return "NEC", f"{b[0]:02X} 00 00 00", f"{b[2]:02X} 00 00 00"
    if p == "necext":
        if b[3] != b[2] ^ 0xFF:
            raise ValueError("command byte isn't followed by its inverse")
        return "NECext", f"{b[0]:02X} {b[1]:02X} 00 00", f"{b[2]:02X} {b[3]:02X} 00 00"
    if p == "samsung32":
        if b[0] != b[1]:
            raise ValueError("Samsung32 repeats the address byte")
        if b[3] != b[2] ^ 0xFF:
            raise ValueError("command byte isn't followed by its inverse")
        return "Samsung32", f"{b[0]:02X} 00 00 00", f"{b[2]:02X} 00 00 00"
    raise ValueError("protocol must be nec, necext or samsung32")


# ------------------------------------------------------------------------------ CLI

def write_or_check(path, content, check):
    current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if check:
        if current != content:
            print(f"{os.path.relpath(path, ROOT)} is out of date: run tools/avir.py without --check")
            return False
        return True
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    print(f"wrote {os.path.relpath(path, ROOT)}")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("files", nargs="*")
    c = sub.add_parser("catalog")
    c.add_argument("--check", action="store_true")
    u = sub.add_parser("universal")
    u.add_argument("--check", action="store_true")
    d = sub.add_parser("decode")
    d.add_argument("protocol")
    d.add_argument("code")
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        files = args.files or library_files()
        problems = []
        for f in files:
            problems.extend(validate_file(f)[0])
        for rel, line, msg in problems:
            print(f"{rel}:{line}: {msg}")
        print(f"{len(files)} file(s), {len(problems)} problem(s)")
        return 1 if problems else 0
    if args.cmd == "catalog":
        return 0 if write_or_check(os.path.join(ROOT, "CATALOG.md"), build_catalog(), args.check) else 1
    if args.cmd == "universal":
        ok = True
        for fname, content in build_universal().items():
            ok &= write_or_check(os.path.join(ROOT, "universal", fname), content, args.check)
        return 0 if ok else 1
    if args.cmd == "decode":
        try:
            proto, addr, cmd = decode(args.protocol, args.code)
        except ValueError as e:
            print(f"error: {e}")
            return 1
        print(f"protocol: {proto}\naddress: {addr}\ncommand: {cmd}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
