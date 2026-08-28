# Recruitment — the one gating task

Everything downstream depends on getting raw hex + decoded values from a few
EU/UK cars. No amount of coding substitutes for it. Do this **before** writing
the library.

## Where to post, in priority order

| # | Channel | Why | Post to use |
|---|---|---|---|
| 1 | **Ross-Tech forums**, [thread 36805](https://forums.ross-tech.com/index.php?threads/36805/) | VCDS owners already posting decoded OBFCM values. Half the work is done. | `ross-tech.md` |
| 2 | **r/CarHacking** | Technical audience, receptive to reverse-engineering | `reddit.md` |
| 3 | **Briskoda**, VW/Audi/Ford marque forums | 2021+ EU cars, dongle owners | `ross-tech.md`, lightly adapted |
| 4 | **r/CarTalkUK**, r/VolkswagenGolf | Broad reach, plainer framing | `reddit.md` (second version) |
| 5 | **OBDeleven / Carista Discords** | Already own the tools | `short-form.md` |

Link to [`../HOW-TO-HELP.md`](../HOW-TO-HELP.md) rather than repeating the
instructions inline.

## Rules that matter

- **Never pitch a product.** There isn't one. Mentioning a future paid app is
  the fastest way to get ignored or removed.
- **Read each subreddit's self-promotion rules** before posting.
- **Answer every reply**, including "NO DATA" reports — those tell us which
  cars need `22 F8 17` instead of `0917`, which is real information.
- **Tell people to redact their VIN.** Don't collect it, don't store it.

## Target

**5 vehicles**, spread across VW/BMW/Ford/Stellantis, **including one PHEV**
(they store 12 parameters instead of 6 and need solving separately).

## Kill test

> **If fewer than 3 usable (raw hex + decoded value) pairs arrive within 3
> weeks, stop the project.**

This is a designed exit, not a failure. Total sunk cost at that point is two
weekends and zero rupees. The alternative — building the library first and
discovering nobody will send data — costs a month more and ends the same way.

## Tracking

| Vehicle | Year | Fuel | Raw hex | Decoded | Source | Status |
|---|---|---|---|---|---|---|
| _(fill in as replies arrive)_ | | | | | | |

Usable = raw hex **and** decoded values from the **same car**. One without the
other doesn't count toward the three.

## As data arrives

```bash
# 1. Add each vehicle to a captures file (see tools/obd_probe.py --capture
#    for the format, or write it by hand)
# 2. Solve
python3 tools/obfcm_solve.py captures.json

# 3. Cross-validate: a layout derived from car 1 must decode cars 2 and 3
#    with no special-casing. If it doesn't, it's a coincidence, not a layout.
```
