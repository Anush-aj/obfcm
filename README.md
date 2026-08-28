# obfcm

**Read the fuel counter the EU put in your car — the one no app can read.**

Since 1 January 2021, every car registered in the EU or UK is legally required
to keep a running total of **every litre of fuel it has ever burned** and
**every kilometre it has ever travelled**. That's roughly 60–70 million
vehicles. The law says the readout must be *"free of charge and not subject to
any specific conditions."* A €10 dongle can reach it.

And yet no free app reads it, and until now no open-source project could.

```
$ python3 tools/obd_probe.py --serial /dev/tty.OBDII
    Trying classic OBD:  09 17
    RESPONDED with 17 bytes: 01 00 00 9a b1 00 00 9b 0d 00 00 8b f9 00 00 8d 28
    Wrote obfcm_capture.json -- a solver-ready capture.
```

---

## Why nobody has done this

The regulation ([EU 2018/1832](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32018R1832)
Annex XXII) publishes the **parameter list** for free. It does not publish the
**byte order, field widths or scaling** — those are deferred to SAE J1979-DA,
which costs $100–300.

That paywall is the entire barrier. Verified 28 August 2026: authenticated
GitHub code search returns **zero** results for `obfcm elm327`, `F817 fuel`,
`lifetimeFuelConsumed`, or `lifetime fuel consumed OBD service 09`. Google Play
returns no OBFCM apps. python-OBD, AndrOBD, and the OBDb PID database all lack
it. Slovakia reads it at every inspection station in the country using €10
ELM327 clones ([Tapák et al., *Energies* 2023](https://www.mdpi.com/1996-1073/16/19/6861)) —
so it isn't hard, the format just isn't public.

**We're solving it from examples instead of buying the standard.** VCDS owners
already post their *decoded* values on marque forums. With the *raw hex* from
the same car, the layout is recoverable by constraint search.

**[→ Help finish it. Two minutes, no software to install.](docs/HOW-TO-HELP.md)**

---

## Status

| Component | State |
|---|---|
| Protocol — command selection, per-OEM addressing fallback | ✅ done |
| ISO-TP reassembly — multi-frame, multi-ECU, 11 & 29-bit headers | ✅ done, 8/8 tests |
| Decoding, records, derived metrics | ✅ done |
| Plausibility validation | ✅ done, 70/70 tests |
| Layout solver | ✅ done, self-verifying |
| Record shape, scales, sentinel | ✅ known |
| **The byte layout** | ✅ **solved from a real capture** — see below |
| Confirmation on a European vehicle | ❌ **one capture away** |

Everything is finished except one table. When the solver produces a layout, it
drops into [`obfcm/layouts.py`](obfcm/layouts.py) and the library works.

### What is already pinned down

[Ross-Tech thread 36805](https://forums.ross-tech.com/index.php?threads/36805/)
carries VCDS output for **14 vehicles** — VW, Audi, Škoda, SEAT, a MAN truck,
across petrol, diesel, hybrid and battery-electric. Recorded in
[`captures/reference-vcds-thread-36805.json`](captures/reference-vcds-thread-36805.json).
It settles four things the regulation does not publish:

```
Type 17 - Vehicle Operation Data - Distance-Fuel Used, Recent/Lifetime:
         Total Distance Traveled : 3960.1 km / 3969.3 km
         Total Fuel Consumed : 358.33 L / 361.36 L
```

1. **Four values, not two.** Every parameter is a Recent/Lifetime pair.
2. **Order:** distance before fuel, Recent before Lifetime — confirmed by the
   VCDS label `ENG121352`.
3. **Scales:** 1/10 for km, 1/100 for litres.
4. **All-bits-set is a "not available" sentinel.** VCDS renders it signed,
   which is why unpopulated windows print as `-0.1 km` and `-0.01 L`. Decoding
   it as a number would silently corrupt every average. `FieldSpec.decode()`
   returns `None`.

Largest values observed — 6,886.07 L and 59,663.0 km — mean fields need at
least 3 bytes.

### The layout, solved

A **real paired capture** — raw bytes and decoded values from the same scan log
— settled it. 2020 Ford E-350 conversion van, CarDAQ-Plus 3, Mode 9 InfoType 17
(Steve Caruso, 2020-10-06):

```
payload:  01 00 00 30 E0 00 00 30 EB 00 00 72 4A 00 00 72 7E

bytes[1:5]   0x000030E0 = 12512  x 1/10   = 1251.2 km   recent distance
bytes[5:9]   0x000030EB = 12523  x 1/10   = 1252.3 km   lifetime distance
bytes[9:13]  0x0000724A = 29258  x 1/100  =  292.58 L   recent fuel
bytes[13:17] 0x0000727E = 29310  x 1/100  =  293.10 L   lifetime fuel
```

All four match the scan tool exactly. And the result is physically right:
293.10 L over 1252.3 km is **23.4 L/100km = 10.0 mpg US**, which is what a V8
conversion van does. Wrong field assignments do not land on a sensible figure
by accident.

The layout was hypothesised *before* this capture existed, from the published
resolutions and the VCDS Recent/Lifetime ordering — so this is confirmation,
not curve-fitting. It is now a regression test (`tests/test_obfcm.py`).

**A notable side effect:** this is a *US* vehicle. US light-duty has no OBFCM
mandate, but it carries the same SAE J1979-DA ITID $17 for GHG tracking. The
addressable fleet may be far larger than the EU/UK 2021+ population.

### What is still missing

`verified=False`, deliberately. The layout is confirmed on **one US Ford**.
Whether VAG, BMW or Stellantis order the fields identically is untested — and
per [CONTRIBUTING.md](CONTRIBUTING.md), a layout earns `verified=True` only
after decoding three different vehicles with no special-casing.

**One European capture would flip it.**

### The library already reproduces the thread

Two independent checks against data we did not fit to:

| | |
|---|---|
| Škoda Karoq figures decoded | **14.87 km/l** — NEtech's stated figure: 14.86 |
| 2018 Tiguan | `[IMPLAUSIBLE] CONSUMPTION_OUT_OF_RANGE` at 1.21 L/100km |

That Tiguan is the one Ross-Tech's own staff dismissed by eye — Eric: *"type 17
makes no sense on that Tiguan, that's 1.2 L/100km"*; Uwe: *"average speed has
been something like 378 km/h!"* It is a documented instance of the ~12%
corrupt-data rate that `validate()` exists to catch.

---

## Usage

```python
import obfcm

result = obfcm.read(send=my_transport)        # send(cmd) -> raw adapter text
if result.ok:
    record  = obfcm.decode(result.payload)
    verdict = obfcm.validate(record, powertrain=obfcm.Powertrain.ICE,
                             odometer_km=48_213)
    if verdict.usable:
        print(record.summary())
        # 361.36 L  3,969.3 km  9.10 L/100km (10.98 kmpl)
    else:
        print(verdict.explain())
```

`send` is any callable that takes a command and returns the adapter's reply —
pyserial, a socket, someone else's ELM327 wrapper, or a test stub. The library
never talks to hardware itself.

### Two design decisions worth knowing

**It refuses rather than invents.** `decode()` will not use an unverified
layout unless you explicitly pass `allow_unverified=True`, and any record so
produced carries `layout_verified=False`. A decoder that confidently returns
made-up numbers is worse than no decoder: the numbers look plausible and nobody
checks them.

**It rejects about one car in eight, on purpose.** Slovakia's national
deployment found ~12% of mandate-era vehicles return corrupt OBFCM data, with
consumption wrong "by several orders of magnitude". `validate()` catches those,
and distinguishes them from *legitimate* counter resets — Annex XXII 5.3/5.4
permit a reset on ECU replacement or battery disconnect, so a low reading is
ambiguous, not faulty.

---

## Tools

| | |
|---|---|
| [`tools/obd_probe.py`](tools/obd_probe.py) | Read-only vehicle probe. Walks Mode 01/09 support bitmaps, reads decision-critical PIDs, attempts OBFCM via four addressing strategies, and writes a solver-ready capture file. |
| [`tools/obfcm_solve.py`](tools/obfcm_solve.py) | Constraint solver. Given raw hex plus known decoded values, finds every consistent (offset, width, endianness, scale) using exact rational arithmetic. |

```bash
./run_tests.sh                                    # everything, offline, no deps

# Develop with no car attached
python3 tools/obd_probe.py --replay tools/fixtures/sim_eu_obfcm.log
python3 tools/obfcm_solve.py --selftest

# Real vehicle (--wifi needs nothing; --serial needs pyserial)
python3 tools/obd_probe.py --wifi 192.168.0.10:35000 --note "VW Golf 2022"
```

## Safety

The probe is **strictly read-only, enforced in code**. `assert_safe()`
allowlists every command before transmission and hard-blocks services `04`
(clear DTCs), `08` (actuation), `2E` (write), `2F` (I/O control), `31`
(routine), `11` (ECU reset), `27` (security access), `34`/`36`/`37` (reflash),
`10` (session control) and `3E` (tester present). AT/ST commands configure the
adapter and never reach the vehicle. UDS `22` is read-only but opt-in.

Service 09 is *Request Vehicle Information* — read-only by definition in
SAE J1979. It cannot change anything on your car.

## Honest expectations

This is a genuine open-source first, not a business. Realistic revenue is
€0–300/month. BMW already exposes the same signals through its free CarData
API, and once the layout is published, Car Scanner and Carista can each ship it
in a weekend. That's fine — the data is legally yours and reading it shouldn't
require a paywalled document.

Two claims that appear elsewhere and are **wrong**:

- **There is no ±5% legal accuracy guarantee.** Annex XXII point 4 requires
  only "the most accurate values that can be achieved by the ECU." The ±5%
  figure belongs to fleet-level conformity monitoring.
- **OBFCM is not an independent odometer.** Annex XXII 2.6 states distance uses
  *"the same data source that the vehicle odometer uses"*, and it is resettable.
  It is a useful cross-check, not tamper-proof evidence.

## Licence

MIT.
