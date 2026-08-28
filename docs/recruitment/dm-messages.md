# The two messages — copy, paste, send

Public searching is exhausted (GitHub repos/issues/PRs, `F817`, Ross-Tech,
MHHAuto, BRISKODA). Every hit is decoded values, an OEM cloud API, or "which
tool reads this?". **Raw OBFCM hex is not on the public internet**, and that
follows from who uses what: VCDS users see decoded numbers and never look at
bytes; terminal-app users don't know Type 17 exists. Nobody has had a reason to
post both.

The data has to be generated, not found. That means one person, one car, two
minutes.

---

## 1. jbakkerxli — send this first

**Why him:** Netherlands, **2021 Audi A3 2.0 TDI** — a mandate-era car. In
October 2024 he asked the forum how to read his OBFCM data, spent two days
trying, and never got a working answer; his last post was still guessing
("i think i found some cumulative fuelconsumption in instrumentclusterdata").
He is not being asked a favour — he gets the thing he wanted.

> **Subject:** Your OBFCM question from last year — I think I can finish it
>
> Hi Jack,
>
> You asked back in October 2024 how to read the OBFCM data on your 2021 A3,
> spent a couple of days on it, and from the thread it looks like you never got
> a clean answer. That thread's closed now, so I hope a DM is alright.
>
> I've been working on the same problem and got most of the way. The reason
> it's hard: VCDS shows you the decoded numbers, but the actual byte format is
> published only in SAE J1979-DA, a standard that costs a few hundred dollars.
> So no free tool can read it, and there's no open-source implementation
> anywhere — I checked properly.
>
> I've written one anyway: https://github.com/Anush-aj/obfcm — the protocol,
> the frame reassembly, the validation, all tested. It's missing exactly one
> thing, and it's something only someone with a 2021-or-newer car can give me.
>
> Two minutes, if you're willing:
>
> 1. Any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque) —
>    send `0917` and copy whatever comes back
> 2. Straight after, your VCDS `[33-OBD]` Mode 9 Type 17 screen from the
>    same car
>
> The raw reply plus the decoded numbers from the same session is enough to
> work out the format. It has to be the same sitting, because the counters move
> as you drive.
>
> `0917` is read-only — service 09 is Request Vehicle Information, it can't
> write or change anything. Blank the VIN.
>
> If it works, you'd be the first person outside a paid-tool vendor able to
> read this properly, and I'll send you your own numbers first. Your A3 would
> be the reference vehicle.

---

## 2. NEtech — send second

**Why him:** VCDS Distributor, Denmark, 4,519 posts. Published readouts from a
dozen cars in thread 36805. Best reach, but for him this is a favour rather
than a trade — so lead with credit, which is genuinely owed.

> **Subject:** OBFCM Type 17 — one raw hex reading, if you have two minutes?
>
> Hi NEtech,
>
> Your April 2023 thread "What is OBFCM.. information" is the best public
> documentation of Type 17 anywhere — I've been using it as a reference. It's
> locked, so I hope a direct message is alright.
>
> I'm building an open-source OBFCM reader, and your posts have already settled
> most of it. From the fourteen vehicles you and Eric listed I could work out
> that Type 17 carries Recent/Lifetime pairs rather than single values, that
> the order is distance then fuel, that the scales are 0.1 km and 0.01 L, and
> that `-0.1` / `-0.01` is an all-bits-set "not available" sentinel rather than
> a reading. That last one would have quietly corrupted every average I
> computed, so — thank you.
>
> One thing is still missing, and it's the only thing between this and a
> working library: **the raw hex**.
>
> I did wonder whether a Controller Channel Map CSV would carry the frames, but
> from the logs posted on the forum those look decoded-only
> (`IDE00371,Fuel consumption,0.69, l/h`). If VCDS's debug-level logging
> captures what's underneath, that one file would do it — you'd know far better
> than me.
>
> Otherwise, if you have any 2021+ car and two minutes:
>
> 1. In any OBD app with a terminal (Car Scanner, OBD Auto Doctor, Torque),
>    send `0917` and copy the raw reply
> 2. Straight afterwards, the VCDS `[33-OBD]` Mode 9 Type 17 screen from that
>    same car
>
> Same sitting, since the counters move. Read-only command, and blank the VIN.
>
> The decoder is written and tested: https://github.com/Anush-aj/obfcm —
> protocol handling, ISO-TP reassembly, plausibility validation and the solver.
> Everything but that one table. MIT licensed, and I'll PR it into python-OBD
> and the OBDb PID database so any app can pick it up. Happy to credit you, or
> not, as you prefer.
>
> Incidentally, your Tiguan example is now a test case — my validator rejects
> it at 1.21 L/100km, which is the same conclusion Eric and Uwe reached by eye.

---

## Also worth a message

**TTT** — Netherlands, 2,388 posts, confirmed in the same thread that he
successfully pulled address-33 data ("I already pulled data from 33, thanks for
the tip"). Use a trimmed version of the NEtech message.

---

## When a reply arrives

```bash
# Save it as a capture, then:
python3 tools/obfcm_solve.py captures/*.json
```

One vehicle narrows it. Three settle it. The solver is built and self-verifying;
this part takes minutes, not weekends.
