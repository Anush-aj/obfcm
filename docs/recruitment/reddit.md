# Reddit — r/CarTalkUK, r/VolkswagenGolf, r/CarHacking, r/MechanicAdvice

**Read each subreddit's self-promotion rules first.** r/CarHacking is the most
receptive — it's a technical audience that will engage with the reverse-
engineering angle. r/CarTalkUK and marque subs want a plain-English framing and
will downvote anything that smells like an app launch.

**Post as a question/project, never as a product.** No links to anything
commercial. A GitHub link is fine once the repo exists.

---

## r/CarHacking version

**Title:** The EU mandates a lifetime fuel counter in every car since 2021.
Nobody has open-sourced how to read it. Want to help fix that?

---

Every car registered in the EU/UK since 1 Jan 2021 has to keep OBFCM counters —
total fuel consumed (0.01 L resolution) and total distance (0.1 km) — for the
life of the vehicle. EU 2018/1832 Annex XXII. Reg 2021/392 Art. 9(2) says the
readout must be free of charge and unconditional.

It lives at Mode 09 InfoType 0x17, or `22 F8 17` on OBDonUDS cars. Slovakia
reads it at every inspection station with €10 ELM327 clones.

And yet: GitHub code search returns **zero** results for OBFCM + ELM327.
python-OBD doesn't have it. The OBDb PID database doesn't have it. No app on
the Play Store reads it.

The reason is dumb — the parameter list is free in the regulation, but the byte
layout is in SAE J1979-DA, which costs $100–300.

I want to solve it by constraint search instead of buying the standard. VCDS
users already post their decoded values on Ross-Tech's forums. If I have the
raw hex from the same car, the layout falls out: the scale factors have to be
conventional (1/100, 1/10), and three cars kills any coincidental fit.

I've written the solver already (exact rational arithmetic, no float
tolerances). I just need data.

**If you have a 2021+ EU/UK car and any dongle:** send `0917` in your app's
terminal, screenshot the reply, and if you have VCDS or OBDeleven screenshot
the decoded lifetime fuel/distance too. Redact your VIN.

Read-only — service 09 can't write anything.

Repo (library is written and tested, just needs the layout):
https://github.com/Anush-aj/obfcm

MIT licence, PRs going to python-OBD and OBDb, everyone credited.

Especially want a PHEV: those store 12 parameters instead of 6.

---

## r/CarTalkUK / marque sub version (plainer)

**Title:** Your car has counted every drop of fuel it's ever burned. I'm trying
to make that readable for free.

---

Since 2021, EU and UK law requires every new car to keep a running total of all
the fuel it has ever used and all the distance it has ever covered. It's more
accurate than working it out from receipts, and the law says you're entitled to
read it.

The catch: the instructions for decoding it are in a standard that costs a few
hundred pounds, so no free app can do it. Garages have tools that can. Owners
don't.

I'm trying to work out the format from examples instead, and publish it free.

**If you have a 2021-or-newer car and an OBD dongle**, this takes two minutes:
open your OBD app's terminal, type `0917`, screenshot what comes back. If you
also have VCDS or OBDeleven, screenshot the lifetime fuel/distance screen.

It's a read-only command — it can't change anything on your car. Please blank
out your VIN.

Happy to send you your own decoded figures once it works.
