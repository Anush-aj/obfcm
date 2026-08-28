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

## Do this first: start a NEW thread, don't DM

Both OBFCM threads are locked, so a new one is the only option — not
necroposting. And it beats a DM on reach:

| Person | Activity | Why they'd see it |
|---|---|---|
| **Uwe** | Administrator, 62,637 posts | Explained functional addressing in the Oct 2024 thread |
| **Eric** | Ross-Tech staff, 5,333 posts | Spotted the bad Tiguan data himself |
| **NEtech** | VCDS Distributor, 4,519 posts | Replied in *both* OBFCM threads — he watches the topic |
| **TTT** | 2,388 posts since Jun 2023 | Confirmed pulling address-33 data successfully |

Four demonstrably interested, active people versus one dormant account. Use the
**standalone post text** in `ross-tech.md`.

**Check "Last seen" on any member profile before spending a message on them.**

---

## 1. jbakkerxli — DORMANT, deprioritised

**Do not lead with this one.** All seven of his posts are in that single thread
across two days in October 2024, and he has not posted since — roughly 22
months. His last post promised a scan he never delivered:

> "I will post a scan as soon i have the laptop where vcds is installed ready
> for internet. Since i use vcds its a stand-alone, update through usb."

His VCDS machine is air-gapped, so even a willing reply means moving files off
a disconnected laptop — a chore he already declined once.

Strong motive, no activity. Send it only as a long shot after the thread is up.

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

## 3. TTT — good third option

Netherlands, 2,388 posts since June 2023, so genuinely active. Confirmed in the
Oct 2024 thread that he pulled address-33 data successfully ("I already pulled
data from 33, thanks for the tip"). Trim the NEtech message; he needs no
introduction to the topic.

## Order of operations

1. **New thread on Ross-Tech** — reaches all four at once
2. **NEtech DM** if the thread gets no traction in a week
3. **TTT DM**
4. jbakkerxli, as a long shot

---

## When a reply arrives

```bash
# Save it as a capture, then:
python3 tools/obfcm_solve.py captures/*.json
```

One vehicle narrows it. Three settle it. The solver is built and self-verifying;
this part takes minutes, not weekends.
