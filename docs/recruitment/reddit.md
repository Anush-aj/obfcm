# Reddit — primary channel

Ross-Tech is closed: both OBFCM threads are locked, and registration requires
a VCDS serial number. Reddit has no gatekeeping.

**Subreddits, in order:** r/CarHacking (best — technical, enjoys exactly this),
then r/OBD2, r/VolkswagenGolf, r/CarTalkUK, r/MechanicAdvice.

Read each sub's self-promotion rules first. Post it as a result being shared,
not a product being launched.

---

## The post

**Title:**
`I cracked the EU-mandated fuel counter format that's locked behind a $300 SAE standard. Does it work on your car?`

---

Every car registered in the EU/UK since 1 Jan 2021 — around 60–70 million
vehicles — is legally required to keep lifetime counters of total fuel consumed
and total distance travelled. EU 2018/1832 Annex XXII. Reg 2021/392 Art. 9(2)
says the readout "shall be free of charge and not subject to any specific
conditions."

It lives at Mode 09 InfoType 0x17. Slovakia reads it at every inspection
station in the country using €10 ELM327 clones.

And yet no free tool reads it, because the regulation publishes the *parameter
list* but not the byte layout — that's in SAE J1979-DA, which costs $100–300.
GitHub code search returned **zero** results for OBFCM + ELM327. python-OBD
doesn't have it. The OBDb PID database doesn't have it.

**So I worked it out from a real capture instead.**

```
payload:  01 00 00 30 E0 00 00 30 EB 00 00 72 4A 00 00 72 7E

bytes[1:5]   0x000030E0 = 12512  x 1/10   = 1251.2 km   recent distance
bytes[5:9]   0x000030EB = 12523  x 1/10   = 1252.3 km   lifetime distance
bytes[9:13]  0x0000724A = 29258  x 1/100  =  292.58 L   recent fuel
bytes[13:17] 0x0000727E = 29310  x 1/100  =  293.10 L   lifetime fuel
```

Every parameter is a **Recent/Lifetime pair**, distance before fuel. All-bits-
set is a "not available" sentinel (which is why VCDS shows unpopulated fields
as `-0.1 km` / `-0.01 L` — it renders it signed).

All four fields match the scan tool exactly, and the result is physically
right: 293.10 L over 1252.3 km is 23.4 L/100km = **10.0 mpg US**, correct for
the vehicle it came from (a V8 conversion van). Wrong field assignments don't
land on a sensible figure by accident.

**Here's the catch: that's one vehicle, and it's a Ford.** I have no idea
whether VAG, BMW, Stellantis or Toyota order the record the same way.

**The ask — one command, about a minute:**

In any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque), send:

```
0917
```

Paste what comes back, plus make/model/year/fuel. That's genuinely it — I'll
decode it and tell you your car's true lifetime consumption.

`NO DATA` is useful too; it tells me which cars need `22 F8 17` instead.

If you happen to have VCDS or OBDeleven, the decoded `[33-OBD]` Mode 9 Type 17
values from the same sitting make it conclusive rather than just plausible —
but that's a bonus, not a requirement.

`0917` is service 09, Request Vehicle Information. Read-only by definition —
it cannot write, reset or clear anything. Blank your VIN.

A PHEV would be especially interesting, since those carry 12 parameters
instead of 6.

Code, tests and the full working: **https://github.com/Anush-aj/obfcm**

MIT, and I'm PRing it into python-OBD and OBDb so any app can pick it up.
Everyone who sends a capture gets credited.

---

## Interesting side note worth including if the thread gets technical

The capture that cracked it is a **US** vehicle. US light-duty has no OBFCM
mandate — but it carries the same SAE J1979-DA ITID $17 for GHG tracking. So
this may work on far more cars than the EU/UK 2021+ population.
