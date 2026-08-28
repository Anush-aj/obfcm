#!/usr/bin/env python3
"""
Library tests for the obfcm package. Zero dependencies -- plain assertions.

Everything here runs without a vehicle, which is the point: when real captures
arrive, the only thing that changes is one entry in obfcm/layouts.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fractions import Fraction

import obfcm
from obfcm import Powertrain, Record, Severity
from obfcm.layouts import FieldSpec, Layout, layout_from_solver

# A Type 17 record shaped like the real thing: four values as Recent/Lifetime
# pairs, distance before fuel. Figures are the VW Golf 8 from Ross-Tech thread
# 36805 (3960.1/3969.3 km, 358.33/361.36 L).
PAYLOAD = bytes.fromhex("01"
                        "00009AB1"     # recent distance  39601 x 0.1
                        "00009B0D"     # total distance   39693 x 0.1
                        "00008BF9"     # recent fuel      35833 x 0.01
                        "00008D28")    # total fuel       36136 x 0.01

# Same record with the Recent window unpopulated -- the sentinel case that
# appears on most vehicles in that thread.
PAYLOAD_SENTINEL = bytes.fromhex("01"
                                 "FFFFFFFF" "00009B0D"
                                 "FFFFFFFF" "00008D28")

HYPOTHESIS_ID = "type17-v1"

VERIFIED = Layout(
    id="test-verified", description="test", verified=True,
    fields={
        "recent_distance_km": FieldSpec(1, 4, Fraction(1, 10)),
        "total_distance_km": FieldSpec(5, 4, Fraction(1, 10)),
        "recent_fuel_l": FieldSpec(9, 4, Fraction(1, 100)),
        "total_fuel_l": FieldSpec(13, 4, Fraction(1, 100)),
    },
)

def isotp_frames(payload, mode="09", pid="17", header="7E8"):
    """Encode a payload as the raw CAN frames an ELM327 prints with ATH1."""
    data = bytes.fromhex(f"{int(mode, 16) + 0x40:02X}{pid}") + payload
    if len(data) <= 7:
        frames = [bytes([len(data)]) + data]
    else:
        frames = [bytes([0x10 | (len(data) >> 8), len(data) & 0xFF]) + data[:6]]
        rest, seq = data[6:], 1
        while rest:
            frames.append(bytes([0x20 | (seq & 0x0F)]) + rest[:7])
            rest, seq = rest[7:], seq + 1
    return "".join(f"{header}{f.hex().upper()}\r" for f in frames) + "\r"


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def approx(a, b, tol=1e-6):
    return a is not None and abs(a - b) < tol


# ---------------------------------------------------------------------------
# Record: derived metrics
# ---------------------------------------------------------------------------

def test_record():
    r = Record(total_fuel_l=358.33, total_distance_km=3960.1)
    check("l/100km", approx(r.l_per_100km, 9.0485, 1e-3), f"{r.l_per_100km}")
    check("km/l", approx(r.km_per_l, 11.0512, 1e-3), f"{r.km_per_l}")
    check("mpg_uk", approx(r.mpg_uk, 31.22, 1e-2), f"{r.mpg_uk}")
    check("mpg_us", approx(r.mpg_us, 26.00, 1e-2), f"{r.mpg_us}")

    # Guards: a partially populated record must never raise or divide by zero.
    check("no fuel -> None", Record(total_distance_km=100).l_per_100km is None)
    check("no distance -> None", Record(total_fuel_l=10).l_per_100km is None)
    check("zero distance -> None",
          Record(total_fuel_l=10, total_distance_km=0).l_per_100km is None)
    check("empty record summary", Record().summary() == "empty record")
    check("populated_fields excludes None",
          Record(total_fuel_l=1.0).populated_fields() == {"total_fuel_l": 1.0})

    # PHEV
    p = Record(total_fuel_l=100.0, total_distance_km=10000.0,
               distance_charge_depleting_engine_off_km=6500.0,
               grid_energy_kwh=1200.0)
    check("is_phev true", p.is_phev)
    check("is_phev false", not r.is_phev)
    check("electric share", approx(p.electric_distance_share, 0.65, 1e-6))
    check("summary mentions electric", "65% electric" in p.summary(), p.summary())


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def test_validate():
    ok = obfcm.validate(Record(total_fuel_l=358.33, total_distance_km=3960.1),
                        powertrain=Powertrain.ICE)
    check("plausible record is OK", ok.severity is Severity.OK, ok.explain())
    check("plausible record usable", ok.usable)
    check("Verdict truthiness", bool(ok))

    def codes(rec, **kw):
        return {f.code for f in obfcm.validate(rec, **kw).findings}

    check("empty record rejected",
          "EMPTY_RECORD" in codes(Record()))

    # The signature failure of the ~12% of corrupt vehicles: consumption off
    # by orders of magnitude.
    check("absurd consumption rejected",
          "CONSUMPTION_OUT_OF_RANGE" in codes(
              Record(total_fuel_l=41_775_269.0, total_distance_km=3960.1),
              powertrain=Powertrain.ICE))
    check("impossibly low consumption rejected",
          "CONSUMPTION_OUT_OF_RANGE" in codes(
              Record(total_fuel_l=1.0, total_distance_km=100_000.0),
              powertrain=Powertrain.ICE))

    check("distance without fuel rejected for ICE",
          "DISTANCE_WITHOUT_FUEL" in codes(
              Record(total_fuel_l=0.0, total_distance_km=5000.0),
              powertrain=Powertrain.ICE))
    # Same record is legitimate for a PHEV always driven on grid power.
    phev = obfcm.validate(Record(total_fuel_l=0.0, total_distance_km=5000.0),
                          powertrain=Powertrain.PHEV)
    check("distance without fuel OK for PHEV", phev.usable, phev.explain())

    check("fuel without distance flagged",
          "FUEL_WITHOUT_DISTANCE" in codes(
              Record(total_fuel_l=500.0, total_distance_km=0.0)))
    check("negative counter rejected",
          "NEGATIVE_COUNTER" in codes(
              Record(total_fuel_l=-5.0, total_distance_km=100.0)))
    check("absurd lifetime distance rejected",
          "IMPLAUSIBLE_DISTANCE" in codes(
              Record(total_fuel_l=500_000.0, total_distance_km=9_000_000.0)))
    check("recent exceeding lifetime rejected",
          "RECENT_EXCEEDS_LIFETIME" in codes(
              Record(total_fuel_l=100.0, total_distance_km=1000.0,
                     recent_fuel_l=500.0)))
    check("PHEV share > 1 rejected",
          "PHEV_SHARE_IMPOSSIBLE" in codes(
              Record(total_fuel_l=100.0, total_distance_km=1000.0,
                     distance_charge_depleting_engine_off_km=5000.0)))

    # Odometer cross-checks
    rec = Record(total_fuel_l=358.33, total_distance_km=3960.1)
    check("counter reset suspected vs odometer",
          "COUNTER_RESET_SUSPECTED" in codes(rec, odometer_km=90_000.0))
    check("reset is suspect, not fatal",
          obfcm.validate(rec, odometer_km=90_000.0).usable)
    check("reset_suspected flag",
          obfcm.validate(rec, odometer_km=90_000.0).reset_suspected)
    check("distance exceeding odometer flagged",
          "DISTANCE_EXCEEDS_ODOMETER" in codes(rec, odometer_km=1000.0))
    check("matching odometer is clean",
          obfcm.validate(rec, odometer_km=3980.0).severity is Severity.OK)

    # Monotonicity
    prev = Record(total_fuel_l=400.0, total_distance_km=4200.0)
    check("small regression is corruption",
          "COUNTER_REGRESSION" in codes(rec, previous=prev))
    big_prev = Record(total_fuel_l=5000.0, total_distance_km=60000.0)
    check("large drop reads as reset",
          "COUNTER_RESET_SUSPECTED" in codes(rec, previous=big_prev))


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------

def test_decode():
    # The honesty rule: refuse rather than invent.
    try:
        obfcm.decode(PAYLOAD)
        check("refuses without verified layout", False, "did not raise")
    except obfcm.NoLayoutError as e:
        check("refuses without verified layout", True)
        check("refusal explains how to help", "HOW-TO-HELP" in str(e))

    rec = obfcm.decode(PAYLOAD, allow_unverified=True)
    check("hypothesis decodes lifetime fuel", approx(rec.total_fuel_l, 361.36, 1e-9))
    check("hypothesis decodes lifetime distance",
          approx(rec.total_distance_km, 3969.3, 1e-9))
    check("hypothesis decodes recent pair",
          approx(rec.recent_fuel_l, 358.33, 1e-9) and
          approx(rec.recent_distance_km, 3960.1, 1e-9))
    check("lifetime consumption matches NEtech's 10.98 km/l",
          approx(rec.km_per_l, 10.98, 1e-2), f"{rec.km_per_l}")

    # The sentinel must read as absent, never as -0.01 or 0.0. Returning a
    # number here would silently corrupt every average computed from it.
    sent = obfcm.decode(PAYLOAD_SENTINEL, allow_unverified=True)
    check("sentinel decodes as absent, not a value",
          sent.recent_fuel_l is None and sent.recent_distance_km is None)
    check("sentinel does not block the lifetime pair",
          approx(sent.total_fuel_l, 361.36, 1e-9))
    check("record marked unverified", rec.layout_verified is False)
    check("record keeps raw bytes", rec.raw == PAYLOAD)
    check("record records layout id", rec.layout_id == HYPOTHESIS_ID)

    # Explicit layout injection
    rec2 = obfcm.decode(PAYLOAD, layout=VERIFIED)
    check("explicit layout works", approx(rec2.total_fuel_l, 361.36, 1e-9))
    check("explicit layout marked verified", rec2.layout_verified is True)

    # Too short for any layout
    try:
        obfcm.decode(b"\x01\x02", allow_unverified=True)
        check("rejects short payload", False, "did not raise")
    except obfcm.NoLayoutError:
        check("rejects short payload", True)

    check("empty payload raises ValueError",
          _raises(ValueError, lambda: obfcm.decode(b"")))
    check("try_decode returns None instead of raising",
          obfcm.try_decode(PAYLOAD) is None)


def _raises(exc, fn):
    try:
        fn()
        return False
    except exc:
        return True


# ---------------------------------------------------------------------------
# Protocol: strategy fallback
# ---------------------------------------------------------------------------

def test_protocol():
    """A stub transport lets us test every branch with no hardware."""
    seen = []

    def transport(responses):
        def send(cmd):
            seen.append(cmd)
            return responses.get(cmd, "NO DATA\r\r")
        return send

    # First strategy succeeds.
    ok_wire = isotp_frames(PAYLOAD)
    r = obfcm.read(transport({"0917": ok_wire}))
    check("first strategy succeeds", r.ok and r.payload == PAYLOAD)
    check("reports strategy name", r.strategy == "classic-functional")
    check("identifies responding ECU", r.ecu == "7E8", r.ecu)
    check("stops after success", len(r.attempts) == 1)

    # Falls through to UDS.
    seen.clear()
    uds_wire = isotp_frames(PAYLOAD, mode="22", pid="F817")
    r = obfcm.read(transport({"22F817": uds_wire}))
    check("falls through to UDS", r.ok and r.strategy == "uds-functional",
          r.explain())
    check("records failed attempts", len(r.attempts) == 2)
    check("failed attempt marked not ok", not r.attempts[0].ok)

    # UDS can be declined.
    seen.clear()
    r = obfcm.read(transport({"22F817": uds_wire}), include_uds=False)
    check("include_uds=False skips UDS", not r.ok)
    check("no UDS command sent", not any(c.startswith("22") for c in seen), seen)

    # Nothing answers.
    r = obfcm.read(transport({}))
    check("no response handled", not r.ok)
    check("all strategies tried", len(r.attempts) == len(obfcm.STRATEGIES))
    check("explains failure", "No OBFCM response" in r.explain())

    # Physical addressing runs setup and teardown.
    seen.clear()
    obfcm.read(transport({}))
    check("sets ECU header for gateway strategy", "ATSH7E0" in seen, seen)
    check("clears receive filter afterwards", "ATCRA" in seen, seen)


# ---------------------------------------------------------------------------
# Layout registry
# ---------------------------------------------------------------------------

def test_layouts():
    check("no verified layout yet (honest default)",
          obfcm.verified_layouts() == [])
    check("hypothesis is marked unverified",
          obfcm.LAYOUTS[HYPOTHESIS_ID].verified is False)

    # Closing the loop: solver output -> Layout -> decode.
    solved = layout_from_solver(
        "solved-v1",
        {"recent_distance_km": (1, 4, "big", Fraction(1, 10)),
         "total_distance_km": (5, 4, "big", Fraction(1, 10)),
         "recent_fuel_l": (9, 4, "big", Fraction(1, 100)),
         "total_fuel_l": (13, 4, "big", Fraction(1, 100))},
        source="3 vehicles",
    )
    check("solver output is verified", solved.verified)
    check("solver output min_length", solved.min_length == 17)
    rec = obfcm.decode(PAYLOAD, layout=solved)
    check("solver output decodes correctly",
          approx(rec.total_fuel_l, 361.36, 1e-9) and
          approx(rec.total_distance_km, 3969.3, 1e-9))
    check("field describe is readable",
          "bytes[13:17]" in solved.fields["total_fuel_l"].describe(),
          solved.fields["total_fuel_l"].describe())

    # A multi-frame round trip through the real parser, so the test fixtures
    # cannot drift away from what the wire format actually produces.
    wire = isotp_frames(PAYLOAD)
    check("payload survives an ISO-TP round trip",
          bytes(obfcm.parse_response(wire, "09", "17")) == PAYLOAD)


# ---------------------------------------------------------------------------
# Real vehicle data -- the most important test in this file
# ---------------------------------------------------------------------------

def test_real_capture():
    """
    The one real paired capture we have: a 2020 Ford E-350 conversion van,
    read with a CarDAQ-Plus 3 (Steve Caruso, 2020-10-06). Raw bytes and
    decoded values came out of the same scan log.

    This is not synthetic and was not fitted to -- the layout was hypothesised
    before this capture existed, from published resolutions and the VCDS
    Recent/Lifetime ordering. If a future change breaks this test, the change
    is wrong.
    """
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "captures",
                        "ford-e350-2020-caruso.json")
    cap = json.load(open(path))[0]
    payload = bytes.fromhex(cap["raw"].replace(" ", ""))[2:]   # drop 49 17 echo

    rec = obfcm.decode(payload, allow_unverified=True)
    for name, want in cap["known"].items():
        got = getattr(rec, name)
        check(f"Ford E-350: {name}", approx(got, want, 1e-9),
              f"got {got}, expected {want}")

    # 293.10 L over 1252.3 km = 23.4 L/100km = 10.0 mpg US, which is correct
    # for a V8 conversion van. Wrong field assignments do not land on a
    # physically sensible figure by accident.
    check("Ford E-350: consumption is physically right",
          approx(rec.l_per_100km, 23.4, 0.05), f"{rec.l_per_100km}")
    check("Ford E-350: mpg_us ~10", approx(rec.mpg_us, 10.05, 0.1), f"{rec.mpg_us}")

    check("Ford E-350: passes validation",
          obfcm.validate(rec, powertrain=Powertrain.ICE).severity is Severity.OK)

    # Recent must not exceed lifetime, and here it genuinely does not.
    check("Ford E-350: recent <= lifetime",
          rec.recent_distance_km < rec.total_distance_km and
          rec.recent_fuel_l < rec.total_fuel_l)

    # Full round trip through the wire layer, as a live read would arrive.
    wire = isotp_frames(payload)
    check("Ford E-350: survives ISO-TP round trip",
          bytes(obfcm.parse_response(wire, "09", "17")) == payload)


# ---------------------------------------------------------------------------

def main():
    for fn in (test_record, test_validate, test_decode, test_protocol,
               test_layouts, test_real_capture):
        fn()
    width = max(len(n) for n, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        failed += not ok
        if ok:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name:<{width}}  {detail}")
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
