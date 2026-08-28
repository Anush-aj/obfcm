# Short form — Discord, WhatsApp, forum replies, DMs

For OBDeleven/Carista Discords, marque Discords, and one-line replies where a
wall of text would be rude.

---

## One-paragraph version

> EU law has required every car since 2021 to store lifetime fuel-consumed and
> distance counters (OBFCM). The decode format is locked behind a $300 SAE
> standard, so no free app reads it. I'm trying to work it out from examples and
> publish it MIT. If you have a 2021+ EU/UK car: send `0917` in your OBD app's
> terminal, screenshot the reply, plus your VCDS/OBDeleven lifetime fuel+distance
> screen. Read-only command, redact your VIN. Takes two minutes and you'd be
> credited. https://github.com/Anush-aj/obfcm

## One-line version

> Anyone here with a 2021+ EU car and a dongle? Need one screenshot of `0917`
> from your OBD app terminal — trying to open-source the EU fuel-counter format.
> Read-only, 2 minutes, happy to explain. https://github.com/Anush-aj/obfcm

## If someone asks "what's in it for you?"

> Nothing financial yet, honestly. It's a gap that shouldn't exist — the data is
> legally yours and the only thing standing in the way is a paywalled document.
> The decoder goes out MIT and I'm PRing it into python-OBD so every app can use
> it. If it turns into anything later, everyone who sent data gets it free for
> life.

## If someone asks "is this safe?"

> `0917` is OBD service 09, "Request Vehicle Information" — read-only by
> definition in SAE J1979. It cannot write, reset, clear codes, or actuate
> anything. My own tool allowlists commands and hard-blocks services 04, 08, 2E,
> 2F, 31, 11, 27 and 34 before anything is transmitted.
