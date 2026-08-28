# Ross-Tech — thread 36805 is LOCKED

**STATUS CHANGED — read this before sending anything.**

The layout is **solved**, from a real paired capture (2020 Ford E-350,
CarDAQ-Plus 3). Every message below was written when we still needed someone
to solve it, and the ask has since shrunk enormously:

| Then | Now |
|---|---|
| "Send raw hex *and* VCDS values, same sitting" | "Send the reply to `0917`" |
| Needed 3 cars to solve | Need 1 European car to **confirm** |
| "Help me work this out" | "I worked it out — does it hold on your car?" |

Rewrite any message you send to reflect that. `../HOW-TO-HELP.md` and
`reddit.md` are already updated; use those as the model.

---


**Checked 28 Aug 2026: thread 36805 shows "Not open for further replies."**

It is also not what I assumed. It is not an ongoing conversation with several
owners posting values — it is a **single informational post by NEtech**
(VCDS Distributor, Denmark, member since 2014, 4,519 messages) from
**3 April 2023**, explaining OBFCM and pasting a full VCDS readout from a
VW Golf 8.

So: no reply is possible, and the "several people are already posting values"
premise was wrong. But the post itself is worth more than a reply would have
been — see `captures/vw-golf8-netech-2023.json`.

---

## Plan A — message NEtech directly. Do this first.

The ask has shrunk. We no longer need decoded values — thread 36805 gave us
fourteen vehicles' worth. **We need raw hex and decoded values from the same
car in the same sitting**, from one cooperative owner. NEtech is the obvious
person: they have the cars, the tool, and they published freely once already.

> **Subject:** OBFCM Type 17 — one raw hex reading, if you have two minutes?
>
> Hi NEtech,
>
> Your April 2023 thread "What is OBFCM.. information" is the best public
> documentation of Type 17 anywhere — I've been using it as a reference. It's
> locked, so I hope a direct message is alright.
>
> I'm building an open-source OBFCM reader, and your posts have already
> settled most of it. From the fourteen vehicles you and Eric listed I could
> work out that Type 17 carries Recent/Lifetime pairs rather than single
> values, that the order is distance then fuel, that the scales are 0.1 km and
> 0.01 L, and that `-0.1` / `-0.01` is an all-bits-set "not available"
> sentinel rather than a reading. That last one would have quietly corrupted
> every average I computed, so — thank you.
>
> One thing is still missing, and it's the only thing between this and a
> working library: **the raw hex**.
>
> VCDS shows the decoded values but not the bytes underneath, and the byte
> offsets are exactly the part locked away in SAE J1979-DA. With both sides
> from the same car, the layout is solvable by constraint search.
>
> So, if you have any 2021+ car and two minutes:
>
> 1. In any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque),
>    send `0917` and copy the raw reply
> 2. Straight afterwards, the VCDS `[33-OBD]` Mode 9 Type 17 screen from that
>    same car
>
> It does have to be the same sitting — the counters move, so I can't pair
> your 2023 figures with today's hex. Read-only command, and blank the VIN.
>
> I did wonder whether a Controller Channel Map CSV would carry the raw
> frames, but from the logs posted on the forum it looks like those are
> decoded-only (`IDE00371,Fuel consumption,0.69, l/h`). If VCDS's debug-level
> logging captures the frames underneath, that one file would do it — you'd
> know far better than me.
>
> The decoder is written and tested: https://github.com/Anush-aj/obfcm —
> protocol handling, ISO-TP reassembly, plausibility validation and the
> solver. Everything but that one table. MIT licensed, and I'll PR it into
> python-OBD and the OBDb PID database so any app can pick it up. Happy to
> credit you, or not, as you prefer.
>
> Incidentally, your Tiguan example is now a test case — my validator rejects
> it at 1.21 L/100km, which is the same conclusion Eric and Uwe reached by eye.

**One reply with the hex finishes the project.**

## Both OBFCM threads are locked

| Thread | Date | Status |
|---|---|---|
| 36805 "What is OBFCM.. information" (Uwe's Bar) | Apr 2023 | **Locked** |
| "How to read information obfcm module europe" (New User Forum) | Oct 2024 | **Locked** |

Ross-Tech appears to close threads routinely. So the options are a **DM** or a
**new thread** — there is nothing live to reply to.

### Other people worth messaging

| Member | Why |
|---|---|
| **NEtech** | VCDS Distributor, Denmark. Published readouts from a dozen cars. Best reach. |
| **jbakkerxli** | Netherlands, **2021 Audi A3 2.0 TDI** — a mandate-era car. Actively tried to read OBFCM and gave up. Would *get something back* from this, so it's a trade rather than a favour. |
| **TTT** | Netherlands, 2,388 posts, confirmed pulling address-33 data successfully. |

## Plan B — a new thread on Ross-Tech

Check the rules on self-promotion first. Post it as a technical question and
link 36805 for context. Use the text below.

## Plan C — everywhere else

`reddit.md` (r/CarHacking first), `short-form.md` for Discords. Do not wait on
Ross-Tech before running these; they are independent.

---

## Standalone post text

**Subject:** Trying to build an open-source OBFCM reader — need raw hex + your
decoded values

---

I've been reading the OBFCM threads here and I'd like to try something, but I
need a few of you to help.

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

**You can make the paywall irrelevant.** NEtech's post in thread 36805 shows
the decoded output — "Total Distance Traveled: 3960.1 km / 3969.3 km, Total
Fuel Consumed: 358.33 L / 361.36 L". If I also have the *raw hex* from the same
car, the layout is solvable by constraint search: the resolutions are fine
enough (0.01 L, 0.1 km) that wrong offsets don't produce plausible scale
factors, and three cars eliminates coincidences.

**What I'm asking for (about two minutes):**

1. In any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque),
   send `0917` and screenshot the reply
2. Screenshot your VCDS `[33-OBD]` Mode 9 Type 17 screen
3. Tell me make/model/year/engine, and whether it's a PHEV

`0917` is service 09, Request Vehicle Information — read-only by definition.
It can't write, reset, clear codes or actuate anything. Please redact your VIN;
I don't need it.

`NO DATA` is also a useful answer — I need to know which cars answer on a
different address, since I gather VAG and BMW differ on whether it comes back
on legacy service 09 or needs `22 F8 17`.

I'd particularly like one PHEV, since those store 12 parameters instead of 6
and will need solving separately.

Repo (layout solved from a real capture; needs confirming on more cars):
https://github.com/Anush-aj/obfcm

Everything goes out MIT-licensed, and I'll PR it into python-OBD and the OBDb
PID database so any app can pick it up. Everyone who helps gets credited by
name unless they'd rather not.
