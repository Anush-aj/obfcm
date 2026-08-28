#!/usr/bin/env python3
"""Wire-format regression tests for parse_response()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from obfcm.isotp import parse_response

# OBFCM record: 49 17 01 | fuel 35833 (358.33 L) | distance 39601 (3960.1 km)
OBFCM = bytes.fromhex("010000" "8BF9" "0000" "9AB1")

CASES = [
    # (name, raw wire text, mode, pid, expected payload)
    ("single frame (MAF)",
     "7E8054110014A\r\r", "01", "10", bytes([0x01, 0x4A])),

    ("single frame w/ padding (fuel system status)",
     "7E80441030200\r\r", "01", "03", bytes([0x02, 0x00])),

    ("ISO-TP multi-frame, headers on (ATH1)",
     "7E8100B49170100008B\r7E821F900009AB10000\r\r", "09", "17", OBFCM),

    ("indexed multi-frame, headers off (CAF1)",
     "00B\r0: 49 17 01 00 00 8B\r1: F9 00 00 9A B1 00\r\r", "09", "17", OBFCM),

    ("multi-ECU: irrelevant module answers first",
     "7E9034100BE\r7E8100B49170100008B\r7E821F900009AB10000\r\r",
     "09", "17", OBFCM),

    ("29-bit CAN header",
     "18DAF110100B49170100008B\r18DAF11021F900009AB10000\r\r", "09", "17", OBFCM),

    ("NO DATA", "NO DATA\r\r", "09", "17", None),
    ("UNABLE TO CONNECT", "UNABLE TO CONNECT\r\r", "01", "10", None),
]

def main():
    width = max(len(n) for n, *_ in CASES)
    failures = 0
    for name, wire, mode, pid, expect in CASES:
        got = parse_response(wire, mode, pid)
        got_b = bytes(got) if got is not None else None
        ok = got_b == (bytes(expect) if expect is not None else None)
        failures += not ok
        status = "ok  " if ok else "FAIL"
        print(f"  {status} {name:<{width}}  {got_b.hex(' ') if got_b else '(none)'}")
        if not ok:
            exp = bytes(expect).hex(" ") if expect else "(none)"
            print(f"       expected: {exp}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
