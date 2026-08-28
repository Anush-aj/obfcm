# How to help — 1 minute, one command

**The layout is solved.** We can now read the EU-mandated lifetime fuel and
distance counters that no free tool could read before.

It's confirmed on **one vehicle** — a 2020 Ford E-350, where all four fields
matched the scan tool exactly and the result (10.0 mpg US) is right for the
car. What we don't know is whether **Volkswagen, BMW, Stellantis, Toyota or
anyone else** lay the record out the same way.

That's all that's left: does it work on your car?

---

## The ask

**One command, any OBD app with a terminal**, on a car registered 2021 or
newer (EU/UK), or any 2020+ US vehicle:

```
0917
```

Copy whatever comes back and send it. That's it.

It'll look something like:

```
7E8 10 13 49 17 01 00 00 30
7E8 21 E0 00 00 30 EB 00 00
7E8 22 72 4A 00 00 72 7E 00
```

Apps with a terminal / console / custom-command box: **Car Scanner ELM OBD2**,
**OBD Auto Doctor**, **Torque**. Exact menu names vary by version — look for
"Terminal", "Console", "Custom command" or "Send command".

**If you get `NO DATA`**, try `22F817` instead and send that. Either way, tell
us the make, model, year and fuel type — a car that *refuses* is useful data
too, because it tells us which vehicles need a different addressing mode.

## Make it conclusive (optional)

If you also have **VCDS** or **OBDeleven**, grab the decoded values from the
same car in the same sitting:

- VCDS: `[33-OBD]` → Mode 9 → Type 17
- It prints four numbers, as Recent/Lifetime pairs

```
Total Distance Traveled : 3960.1 km / 3969.3 km
Total Fuel Consumed : 358.33 L / 361.36 L
```

That turns "our decode looks plausible" into "our decode is provably correct".
It has to be the same sitting — the counters climb as you drive.

But this is a **bonus, not a requirement**. The hex alone is genuinely useful.

---

## Is this safe for my car?

Yes, and you don't have to take our word for it.

`0917` is **OBD service 09, Request Vehicle Information** — read-only by
definition in SAE J1979. It cannot write, reset, clear a fault code, actuate
anything, or change a setting.

Our own probe enforces this in code: every command is checked against an
allowlist before transmission, and services `04` (clear DTCs), `08`
(actuation), `2E` (write), `2F` (I/O control), `31` (routine), `11` (ECU
reset), `27` (security access) and `34` (reflash) are hard-blocked. See
`assert_safe()` in [`tools/obd_probe.py`](../tools/obd_probe.py).

**Please redact your VIN** from anything you send. We don't need it and don't
want it.

---

## What you get

- Your car's true lifetime fuel consumption, which nothing else will tell you
- Credit by name or handle, unless you'd rather not
- The decoder itself, MIT-licensed, free forever, for everyone

## Where to send it

Open an issue: **https://github.com/Anush-aj/obfcm/issues** — or reply in
whichever thread you found this in.

---

## Why this matters

Your car has counted every millilitre of fuel it has burned since the day it
was built. EU law says that number is yours and must be readable free of
charge.

Until now, reading it required a €300 garage tool or a $300 paywalled standard.
It shouldn't.
