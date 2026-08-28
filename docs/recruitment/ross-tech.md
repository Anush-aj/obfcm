# Ross-Tech — thread 36805 is LOCKED

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

Best single lead in the project. They have the car, the tool, the data, and
demonstrated willingness to share it publicly. **We already hold half of
vehicle #1** — we need only the raw hex from the same car.

> **Subject:** OBFCM Type 17 — could I ask for the raw hex from your Golf 8?
>
> Hi NEtech,
>
> Your April 2023 post "What is OBFCM.. information" is the clearest write-up
> of Type 17 I've found anywhere. The thread is locked, so I hope a direct
> message is alright.
>
> I'm building an open-source OBFCM reader. The blocker is that the byte
> layout is published only in SAE J1979-DA ($100–300) — the regulation gives
> the parameter list but not the offsets or scaling, so no free tool can
> decode it.
>
> Your post already gives me half the answer:
>
>     Total Distance Traveled : 3960.1 km / 3969.3 km
>     Total Fuel Consumed     : 358.33 L / 361.36 L
>
> If I had the **raw hex** from that same car, the layout becomes solvable by
> constraint search — those resolutions (0.1 km, 0.01 L) are fine enough that
> a wrong offset almost never produces a plausible scale factor.
>
> So the ask, if you still have the Golf 8 and two minutes: in any OBD app
> with a terminal, send `0917` and send me the raw reply. Read-only command,
> and please blank the VIN.
>
> The decoder is already written and tested —
> https://github.com/Anush-aj/obfcm — protocol handling, ISO-TP reassembly,
> plausibility validation and the solver. It's missing exactly one table.
> MIT licensed, and I'll PR it into python-OBD and the OBDb PID database so
> any app can pick it up. Happy to credit you, or not, whichever you prefer.
>
> Either way — thank you for posting that readout publicly. It's the reason
> this is tractable at all.

**If they reply with the hex, vehicle #1 is complete.** Two more and the
layout is solved.

## Plan B — a new thread on Ross-Tech

Only after trying Plan A, and check the forum rules on necroposting and
self-promotion first. Post it as a technical question, link back to 36805 as
context, and use the text below.

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

Repo (library is written and tested, just needs the layout):
https://github.com/Anush-aj/obfcm

Everything goes out MIT-licensed, and I'll PR it into python-OBD and the OBDb
PID database so any app can pick it up. Everyone who helps gets credited by
name unless they'd rather not.
