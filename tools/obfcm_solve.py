#!/usr/bin/env python3
"""
obfcm_solve.py -- constraint solver for the OBFCM record layout.

The problem
-----------
EU Regulation 2018/1832 Annex XXII mandates that every EU/UK car registered
from 2021 keeps lifetime counters of total fuel consumed (litres) and total
distance travelled (km), readable at OBD Mode 09 InfoType 0x17.

The regulation publishes the *parameter list* for free. It does NOT publish
the byte order, field widths, or scaling factors -- those live in SAE J1979-DA,
which costs $100-300. That paywall is the only reason no open-source
implementation exists.

The way around it
-----------------
Owners on marque forums already post their *decoded* OBFCM values, read with
VCDS or OBDeleven. If we also get the *raw hex* from the same car, we have
both sides of the equation:

    raw bytes  --[unknown layout]-->  known value

This solver searches every plausible (offset, width, endianness, scale) and
keeps only those consistent with EVERY capture. Two properties make this
converge fast:

  1. The resolutions are fine (0.01 L, 0.1 km), so a wrong offset almost
     never produces a "nice" scale factor.
  2. Across vehicles the counters differ by orders of magnitude, so a layout
     that fits two cars by coincidence is vanishingly unlikely.

Exact arithmetic
----------------
Scales are computed as Fractions, not floats. If fuel = 358.33 L and the
raw integer is 35833, the implied scale is exactly 1/100 -- no epsilon
comparisons, no rounding slop.

Usage
-----
    python3 tools/obfcm_solve.py --selftest
    python3 tools/obfcm_solve.py captures.json
    python3 tools/obfcm_solve.py captures.json --field total_fuel_l --verbose

Capture file format (JSON list):
    [
      {
        "label": "VW Golf 8 2021 1.5 TSI",
        "raw": "49 17 01 00 00 8B F9 00 00 9A B1",
        "known": {"total_fuel_l": 358.33, "total_distance_km": 3960.1},
        "notes": "VCDS address 33, Mode 09 Type 17"
      }
    ]
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Scale plausibility
#
# OBD scaling factors are conventionally 1/N for a small, round N (see the
# J1979 PID table: /2, /4, /20, /32, /50, /100, /128, /255, /256 all appear).
# We accept a derived scale only if it looks like one of those -- that alone
# eliminates the overwhelming majority of coincidental offset matches.
# ---------------------------------------------------------------------------

NICE_DENOMINATORS = {
    1, 2, 3, 4, 5, 8, 10, 16, 20, 25, 32, 40, 50, 64, 100, 128, 200,
    255, 256, 500, 512, 1000, 1024, 3600, 10000, 32768, 65536,
}
MAX_NICE_NUMERATOR = 10

# Scales the regulation's resolutions imply, checked first and reported as
# "expected" when they turn up.
EXPECTED_SCALES = {
    "fuel_litres": Fraction(1, 100),      # 0.01 L, per published readouts
    "distance_km": Fraction(1, 10),       # 0.1 km
    "energy_kwh": Fraction(1, 10),        # 0.1 kWh (ICCT notes 1 decimal)
}


def is_plausible_scale(s: Fraction) -> bool:
    """True if `s` looks like a real OBD scaling factor rather than noise."""
    if s <= 0:
        return False
    return s.numerator <= MAX_NICE_NUMERATOR and s.denominator in NICE_DENOMINATORS


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Capture:
    """One vehicle's raw OBFCM response plus its known decoded values."""
    label: str
    raw: bytes
    known: Dict[str, float]
    notes: str = ""

    def __post_init__(self):
        if not self.raw:
            raise ValueError(f"{self.label}: empty raw payload")


@dataclass(frozen=True)
class FieldLayout:
    """A candidate location and scaling for one OBFCM parameter."""
    offset: int
    width: int
    endian: str          # "big" | "little"
    scale: Fraction

    def raw_int(self, data: bytes) -> Optional[int]:
        if self.offset + self.width > len(data):
            return None
        return int.from_bytes(data[self.offset:self.offset + self.width], self.endian)

    def decode(self, data: bytes) -> Optional[Fraction]:
        r = self.raw_int(data)
        return None if r is None else r * self.scale

    def describe(self) -> str:
        s = self.scale
        pretty = f"1/{s.denominator}" if s.numerator == 1 else f"{s.numerator}/{s.denominator}"
        return (f"bytes[{self.offset}:{self.offset + self.width}] "
                f"{self.width}B {self.endian}-endian x {pretty} "
                f"(= {float(s):g})")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_hex(s: str) -> bytes:
    """Accept '49 17 01 00', '491701 00', '0x49,0x17' -- anything hex-ish."""
    cleaned = re.sub(r"(?i)0x", "", s)
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", cleaned)
    if len(cleaned) % 2:
        raise ValueError(f"odd number of hex digits in {s!r}")
    return bytes.fromhex(cleaned)


def exact(value: float | str) -> Fraction:
    """
    Convert a decoded value to an exact Fraction.

    Fraction(str(x)) treats '358.33' as 35833/100 rather than the nearest
    binary double, which is what makes the scale derivation exact.
    """
    return Fraction(str(value))


def load_captures(path: str) -> List[Capture]:
    with open(path) as fh:
        blob = json.load(fh)
    if isinstance(blob, dict):
        blob = [blob]
    out = []
    skipped = []
    for i, item in enumerate(blob):
        label = item.get("label", f"capture[{i}]")
        # Half-captures (decoded values but no raw hex yet, or vice versa) are
        # a normal intermediate state while data is being collected. Skip them
        # with a note rather than crashing.
        if not item.get("raw"):
            skipped.append(label)
            continue
        try:
            out.append(Capture(
                label=label,
                raw=parse_hex(item["raw"]),
                # Skip nulls -- the probe writes them as placeholders for
                # fields the tester has not filled in yet.
                known={k: float(v) for k, v in item.get("known", {}).items()
                       if v is not None},
                notes=item.get("notes", ""),
            ))
        except (KeyError, ValueError) as e:
            sys.exit(f"error in capture {i}: {e}")

    if skipped:
        print(f"Skipping {len(skipped)} half-capture(s) with no raw hex yet:")
        for label in skipped:
            print(f"  - {label}")
        print()
    return out


# ---------------------------------------------------------------------------
# The solver
# ---------------------------------------------------------------------------

def solve_field(captures: Sequence[Capture],
                field: str,
                widths: Iterable[int] = (2, 3, 4),
                endians: Iterable[str] = ("big", "little"),
                require_plausible: bool = True) -> List[FieldLayout]:
    """
    Find every (offset, width, endian, scale) consistent with `field` across
    all captures that report it.

    A layout survives only if the scale derived from each capture is
    identical. With two or more captures whose counters differ substantially,
    that is a very strong filter.
    """
    relevant = [c for c in captures if field in c.known]
    if not relevant:
        return []

    shortest = min(len(c.raw) for c in relevant)
    results: List[FieldLayout] = []

    for width in widths:
        if width > shortest:
            continue
        for offset in range(shortest - width + 1):
            for endian in endians:
                scale: Optional[Fraction] = None
                ok = True

                for cap in relevant:
                    probe = FieldLayout(offset, width, endian, Fraction(1))
                    r = probe.raw_int(cap.raw)
                    if not r:                      # None or zero -> unusable
                        ok = False
                        break
                    derived = exact(cap.known[field]) / r
                    if scale is None:
                        scale = derived
                    elif derived != scale:
                        ok = False
                        break

                if ok and scale is not None:
                    if require_plausible and not is_plausible_scale(scale):
                        continue
                    results.append(FieldLayout(offset, width, endian, scale))

    # Prefer wider fields at lower offsets, and "rounder" scales.
    results.sort(key=lambda l: (l.scale.denominator not in (10, 100),
                                -l.width, l.offset))
    return results


def assignment_gaps(asg: Dict[str, "FieldLayout"]) -> int:
    """
    Count unclaimed bytes strictly *between* the fields of an assignment.

    Real binary records are densely packed, so the true layout normally has
    zero interior gaps. This is what disambiguates a 4-byte field starting at
    offset 3 from a 3-byte field starting at offset 4 -- both decode small
    values identically because the leading byte is zero, but only one of them
    leaves no hole behind.
    """
    if not asg:
        return 0
    claimed = set()
    for lay in asg.values():
        claimed |= set(range(lay.offset, lay.offset + lay.width))
    return len(set(range(min(claimed), max(claimed) + 1)) - claimed)


def solve_record(captures: Sequence[Capture],
                 fields: Sequence[str],
                 require_plausible: bool = True
                 ) -> tuple[Dict[str, List[FieldLayout]], List[Dict[str, FieldLayout]]]:
    """
    Solve every field, then find whole-record assignments in which no two
    fields overlap in the byte range they claim.

    Returns (per_field_candidates, non_overlapping_assignments).
    """
    per_field = {f: solve_field(captures, f, require_plausible=require_plausible)
                 for f in fields}

    solvable = [f for f in fields if per_field[f]]
    assignments: List[Dict[str, FieldLayout]] = []

    if solvable:
        for combo in itertools.product(*(per_field[f] for f in solvable)):
            spans = [range(l.offset, l.offset + l.width) for l in combo]
            used: set[int] = set()
            clash = False
            for span in spans:
                s = set(span)
                if s & used:
                    clash = True
                    break
                used |= s
            if not clash:
                assignments.append(dict(zip(solvable, combo)))
            if len(assignments) >= 200:      # guard against combinatorial blowup
                break

    assignments.sort(key=lambda a: (assignment_gaps(a),
                                    min(l.offset for l in a.values())))
    return per_field, assignments


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(captures: Sequence[Capture], fields: Sequence[str], verbose: bool) -> int:
    print("=" * 74)
    print("OBFCM LAYOUT SOLVER")
    print("=" * 74)
    print(f"\n{len(captures)} capture(s):")
    for c in captures:
        print(f"  {c.label}")
        print(f"    raw ({len(c.raw)}B): {c.raw.hex(' ')}")
        for k, v in c.known.items():
            print(f"    known: {k} = {v}")
        if c.notes:
            print(f"    note:  {c.notes}")

    if len(captures) < 2:
        print("\n  WARNING: with a single capture, coincidental matches are common.")
        print("  Cross-validation needs at least 2 vehicles; 3 is the plan's bar.")

    per_field, assignments = solve_record(captures, fields)

    print("\n" + "-" * 74)
    print("PER-FIELD CANDIDATES")
    print("-" * 74)
    exit_code = 0
    for f in fields:
        cands = per_field.get(f, [])
        n_reporting = sum(1 for c in captures if f in c.known)
        if n_reporting == 0:
            print(f"\n  {f}: no capture reports this field -- skipped")
            continue
        print(f"\n  {f}  ({n_reporting} capture(s) report it)")
        if not cands:
            print("    NO CANDIDATES. Either the field is absent from this record,")
            print("    the scale is unconventional, or a decoded value is mistyped.")
            exit_code = 1
            continue
        for lay in cands[:10 if not verbose else len(cands)]:
            marker = ""
            for name, sc in EXPECTED_SCALES.items():
                if lay.scale == sc:
                    marker = f"   <- matches expected {name} resolution"
            print(f"    {lay.describe()}{marker}")
            if verbose:
                for c in captures:
                    if f in c.known:
                        got = lay.decode(c.raw)
                        print(f"        {c.label}: {float(got):.4f} "
                              f"(expected {c.known[f]})")
        if len(cands) > 10 and not verbose:
            print(f"    ... and {len(cands) - 10} more (use --verbose)")

    print("\n" + "-" * 74)
    print("NON-OVERLAPPING RECORD ASSIGNMENTS")
    print("-" * 74)
    if not assignments:
        print("\n  None found -- candidate fields all claim overlapping bytes.")
        exit_code = 1
    else:
        for i, asg in enumerate(assignments[:5], 1):
            g = assignment_gaps(asg)
            start = min(l.offset for l in asg.values())
            bits = []
            if i == 1:
                bits.append("best fit")
            if g:
                bits.append(f"{g} unclaimed interior byte{'s' if g != 1 else ''}")
            bits.append(f"starts at byte {start}")
            print(f"\n  Assignment {i}:  ({', '.join(bits)})")
            for name, lay in sorted(asg.items(), key=lambda kv: kv[1].offset):
                print(f"    {name:<24} {lay.describe()}")
        if len(assignments) > 5:
            print(f"\n  ... and {len(assignments) - 5} more.")
        zero_gap = [a for a in assignments if assignment_gaps(a) == 0]
        if len(assignments) == 1:
            print("\n  Exactly one consistent assignment. That is the layout.")
        elif len(zero_gap) == 1:
            print("\n  Exactly one gap-free assignment -- that is almost certainly")
            print("  the layout. The others leave unclaimed bytes mid-record.")
        else:
            print(f"\n  {len(assignments)} assignments remain consistent.")
            print("  Residual ambiguity is usually leading zero bytes: a 4-byte")
            print("  field whose top byte is always 0x00 reads identically as a")
            print("  3-byte field one offset later. Both decode real values the")
            print("  same way, so this rarely matters in practice -- prefer the")
            print("  earliest-starting, gap-free assignment.")

    return exit_code


# ---------------------------------------------------------------------------
# Self-test: prove the solver works with zero real data
# ---------------------------------------------------------------------------

def build_synthetic(fuel_l: float, dist_km: float, speed: int = 0) -> bytes:
    """
    Construct a record under a KNOWN layout so the solver can be verified
    before any real capture exists.

    Layout used here (a hypothesis, not the answer):
        [0:2]  49 17     mode+infotype echo
        [2]    01        record count
        [3:7]  fuel      4B big-endian, x 1/100  -> litres
        [7:11] distance  4B big-endian, x 1/10   -> km
        [11]   speed     1B                      -> km/h
    """
    return (bytes([0x49, 0x17, 0x01])
            + round(fuel_l * 100).to_bytes(4, "big")
            + round(dist_km * 10).to_bytes(4, "big")
            + bytes([speed]))


def selftest() -> int:
    print("=" * 74)
    print("SELF-TEST -- can the solver recover a layout it was not told?")
    print("=" * 74)

    truth = [
        ("VW Golf 8 2021 1.5 TSI", 358.33, 3960.1),
        ("Skoda Octavia 2022 2.0 TDI", 1235.95, 31872.0),
        ("Ford Focus 2021 1.0 EcoBoost", 2669.16, 11190.0),
    ]
    captures = [
        Capture(label=lbl,
                raw=build_synthetic(f, d),
                known={"total_fuel_l": f, "total_distance_km": d},
                notes="synthetic")
        for lbl, f, d in truth
    ]

    print("\nGround truth (hidden from the solver):")
    print("  fuel     bytes[3:7]  4B big-endian x 1/100")
    print("  distance bytes[7:11] 4B big-endian x 1/10")

    fields = ["total_fuel_l", "total_distance_km"]
    per_field, assignments = solve_record(captures, fields)

    expected = {
        "total_fuel_l": FieldLayout(3, 4, "big", Fraction(1, 100)),
        "total_distance_km": FieldLayout(7, 4, "big", Fraction(1, 10)),
    }

    print("\nResults:")
    ok = True
    for f in fields:
        cands = per_field[f]
        found = expected[f] in cands
        print(f"  {f:<24} {len(cands)} candidate(s), "
              f"true layout {'FOUND' if found else 'MISSING'}")
        for lay in cands:
            flag = "  <-- correct" if lay == expected[f] else ""
            print(f"      {lay.describe()}{flag}")
        ok &= found

    print(f"\n  Non-overlapping assignments: {len(assignments)}")
    exact_match = any(a == expected for a in assignments)
    print(f"  True assignment present: {'YES' if exact_match else 'NO'}")
    ranked_first = bool(assignments) and assignments[0] == expected
    print(f"  True assignment ranked first: {'YES' if ranked_first else 'NO'} "
          f"(gaps={assignment_gaps(assignments[0]) if assignments else '-'})")
    exact_match = exact_match and ranked_first

    # Single-capture ambiguity check -- documents why the plan needs 3 cars.
    solo = solve_field(captures[:1], "total_fuel_l")
    trio = solve_field(captures, "total_fuel_l")
    print(f"\n  Ambiguity with 1 vehicle:  {len(solo)} candidate(s)")
    print(f"  Ambiguity with 3 vehicles: {len(trio)} candidate(s)")
    if len(trio) < len(solo):
        print("  -> More vehicles narrow the search, as designed.")

    print("\n" + "=" * 74)
    if ok and exact_match:
        print("SELF-TEST PASSED -- solver recovers a layout it was never given.")
        return 0
    print("SELF-TEST FAILED")
    return 1


# ---------------------------------------------------------------------------

DEFAULT_FIELDS = [
    "total_fuel_l",
    "total_distance_km",
    # Type 17 reports Recent/Lifetime pairs -- see Ross-Tech thread 36805.
    "recent_fuel_l",
    "recent_distance_km",
    # PHEV extras (EU 2018/1832 Annex XXII 3.2)
    "fuel_charge_depleting_l",
    "fuel_charge_increasing_l",
    "distance_charge_depleting_engine_off_km",
    "distance_charge_depleting_engine_on_km",
    "distance_charge_increasing_km",
    "grid_energy_kwh",
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Solve the OBFCM record layout from raw hex + known values.")
    ap.add_argument("captures", nargs="?", help="JSON file of captures")
    ap.add_argument("--selftest", action="store_true",
                    help="verify the solver against synthetic data (no car needed)")
    ap.add_argument("--field", action="append", dest="fields",
                    help="restrict to these field names (repeatable)")
    ap.add_argument("--any-scale", action="store_true",
                    help="do not require a conventional scale factor")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.captures:
        ap.print_help()
        return 2

    captures = load_captures(args.captures)
    if not captures:
        print("No complete captures yet -- each needs BOTH raw hex and decoded")
        print("values from the same vehicle. See docs/HOW-TO-HELP.md.")
        return 1
    fields = args.fields or sorted(
        {k for c in captures for k in c.known} or DEFAULT_FIELDS)
    return report(captures, fields, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
