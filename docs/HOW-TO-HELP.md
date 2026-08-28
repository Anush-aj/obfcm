# How to help — 2 minutes, no software to install

We're building the first open-source reader for **OBFCM**, the lifetime fuel
and distance counters that EU law has required in every car registered since
1 January 2021.

The data is in your car right now. The regulation says you're entitled to read
it free of charge. But the byte layout is published only in **SAE J1979-DA**,
a standard that costs $100–300 — which is why no free app, and no open-source
project anywhere, can read it.

**We can get around that paywall entirely if a handful of owners send two
numbers and one screenshot.**

---

## What we need

Two things from the same car, ideally on the same day:

### 1. The raw hex — from any OBD app with a terminal

Most OBD apps have a way to send a raw command. Look for **Terminal**,
**Console**, **Custom command**, or **Send command** (exact names vary by app
and version):

- **Car Scanner ELM OBD2** — custom command / terminal screen
- **OBD Auto Doctor** — console
- **Torque Pro** — adapter console

Send this, exactly:

```
0917
```

Screenshot or copy whatever comes back. It will look something like:

```
7E8 10 0B 49 17 01 00 00 8B
7E8 21 F9 00 00 9A B1 00 00
```

If you get `NO DATA`, that's still a useful result — please tell us the make,
model and year anyway. Some cars answer on a different address and we want to
know which.

### 2. The decoded values — from VCDS or OBDeleven

- **VCDS**: address **33** (OBD-II) → **Mode 09**, **Type 17**. It's labelled
  something like *"Vehicle Operation Data — Distance/Fuel Used"*.
- **OBDeleven**: the equivalent lifetime fuel/distance readout.

We need the two numbers it shows:

- Total fuel consumed — e.g. `358.33 L`
- Total distance travelled — e.g. `3960.1 km`

A screenshot is perfect.

### 3. Your car

Make, model, year, engine, and whether it's a plug-in hybrid. PHEVs store 12
parameters instead of 6, so they need solving separately — if you have one,
you're especially useful.

---

## Is this safe for my car?

Yes, and you don't have to take our word for it.

`0917` is a **read** request — OBD service 09 is "Request Vehicle Information",
which is read-only by definition in the standard. It cannot write, reset,
clear a fault code, actuate anything, or change a setting.

Our own probe tool enforces this in code: every command is checked against an
allowlist before transmission, and services `04` (clear DTCs), `08` (actuation),
`2E` (write), `31` (routine), `11` (ECU reset), `27` (security access) and
`34` (reflash) are hard-blocked. See `assert_safe()` in
[`tools/obd_probe.py`](../tools/obd_probe.py).

**Please redact your VIN** from any screenshot. We don't need it and don't
want it.

---

## What you get

- Credit by name (or handle) in the repository, unless you'd rather not
- Lifetime free access to anything built on top of this
- The decoder itself, MIT-licensed, free forever, for everyone

## Where to send it

**Open an issue: https://github.com/Anush-aj/obfcm/issues** — or just reply in the
thread you found this in, whichever is easier.

---

## Why bother?

Your car has been counting every millilitre of fuel it has burned since the day
it was built. That number is more accurate than any tank-to-tank calculation
you can do by hand, and EU law says it's yours.

Right now, reading it requires a €300 garage tool or a paywalled standard.
It shouldn't.
