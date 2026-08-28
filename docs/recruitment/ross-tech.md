# Ross-Tech forums — the highest-value audience

**Why here first:** thread 36805 already has VCDS owners posting their decoded
OBFCM values voluntarily. They have the tool, they've already done half the
work, and the paywall problem is exactly the kind of thing this audience finds
annoying. Reply in that thread rather than starting a new one.

**Tone:** technical peer asking for help, not a developer marketing an app.
Do not mention any future paid product. There isn't one yet, and hinting at it
here will get the post ignored.

**Before posting:** read the last page or two of the thread. This draft assumes
people are still posting decoded values and nobody has solved the layout. If
that has changed, adjust — a reply that ignores the recent conversation reads
badly and wastes the best audience you have.

---

## REPLY to thread 36805 — use this one

Short, joins the existing conversation, does not re-explain OBFCM to the people
whose thread it is.

---

Reading back through this thread, a few of you have posted your decoded OBFCM
figures from Mode 09 Type 17 — total fuel consumed and total distance. Those
posts are more useful than they look, and I'd like to ask for one small
addition.

The reason no free tool reads OBFCM is that the byte layout is only published
in SAE J1979-DA ($100–300). The regulation gives you the parameter list but not
the offsets or the scaling, so everyone either buys the standard or does
without.

But your decoded values plus the **raw hex from the same car** make the layout
recoverable by constraint search. The resolutions are fine enough (0.01 L,
0.1 km) that a wrong offset almost never produces a plausible scale factor, and
three cars is enough to rule out coincidence.

So if you have a 2021+ car and two minutes: in any OBD app with a terminal
(Car Scanner, OBD Auto Doctor, Torque), send `0917` and post the raw reply
alongside your VCDS Type 17 figures. It's a read-only request — service 09 is
Request Vehicle Information, it can't write or reset anything. Please blank
your VIN.

`NO DATA` is a useful answer too. I need to know which cars want `22 F8 17`
instead, and I gather VAG and BMW differ here.

I've written the decoder already — https://github.com/Anush-aj/obfcm — protocol
handling, ISO-TP reassembly, plausibility validation and the solver, all tested.
It's missing exactly one table. MIT licensed, and I'll PR it into python-OBD and
the OBDb PID database so any app can pick it up. Anyone who helps gets credited.

A PHEV would be especially welcome, since those carry 12 parameters rather
than 6 and need solving separately.

---

## Alternative: standalone post

Use this only if thread 36805 turns out to be dead, or a moderator asks you to
start a new one.

**Subject:** Trying to build an open-source OBFCM reader — need raw hex + your
decoded values

---

I've been reading through the OBFCM threads here and I'd like to try something,
but I need a few of you to help.

Short version: EU 2018/1832 Annex XXII requires every car registered from
Jan 2021 to keep lifetime counters of total fuel consumed and total distance,
and mandates "standardised and unrestricted access" to them. Reg 2021/392 Art.
9(2) goes further — the readout "shall be free of charge and not subject to any
specific conditions."

But the *parameter list* is all the regulation publishes. The byte order, field
widths and scaling factors live in SAE J1979-DA, which is paywalled at
$100–300. That's the only reason there is no open-source implementation. I
checked: GitHub code search returns zero results for OBFCM + ELM327, and there
are no apps that read it. Slovakia's inspection system does it at national
scale with €10 ELM327 clones, so it's clearly not hard — the layout just isn't
public.

**You can make the paywall irrelevant.** Several of you have already posted
decoded values here, like "Total Distance Travelled: 3960.1 km / Total Fuel
Consumed: 358.33 L". If I also have the *raw hex* from the same car, the layout
is solvable by constraint search — the resolutions are fine enough (0.01 L,
0.1 km) that wrong offsets don't produce plausible scale factors, and three
cars is enough to eliminate coincidences.

**What I'm asking for (about two minutes):**

1. In any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque),
   send `0917` and screenshot the reply
2. Screenshot your VCDS address 33 → Mode 09 Type 17 screen
3. Tell me make/model/year/engine, and whether it's a PHEV

`0917` is service 09, Request Vehicle Information — read-only by definition.
It can't write, reset, clear codes or actuate anything. Please redact your VIN;
I don't need it.

`NO DATA` is also a useful answer — I need to know which cars answer on a
different address, since I gather VAG and BMW differ on whether it comes back
on legacy service 09 or needs `22 F8 17`.

I'd particularly like one PHEV, since those store 12 parameters instead of 6
and will need solving separately.

Repo (library is written and tested, just needs the layout):
https://github.com/Anush-aj/obfcm

Everything goes out MIT-licensed, and I'll PR it into python-OBD and the OBDb
PID database so any app can pick it up. Everyone who helps gets credited by
name unless they'd rather not.
