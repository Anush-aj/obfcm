# Contributing

The fastest way to help does not involve writing code.

## Send a capture (2 minutes, no software to install)

See **[docs/HOW-TO-HELP.md](docs/HOW-TO-HELP.md)**. If you have a 2021-or-newer
EU/UK car and any OBD dongle, we need the raw reply to `0917` plus your
VCDS/OBDeleven decoded lifetime fuel and distance. That pair is the only thing
standing between this library and working.

**Redact your VIN.** We don't need it and won't store it.

## Code

```bash
./run_tests.sh          # everything, offline, no dependencies, no vehicle
```

Three rules that matter here more than usual:

1. **Never decode with an unverified layout by default.** A decoder that
   returns invented numbers is worse than one that returns nothing — the
   numbers look plausible and nobody checks them.
2. **Keep the probe read-only.** `assert_safe()` allowlists commands before
   transmission. If you add a command, add it to the allowlist deliberately,
   and never add a write, reset, or actuation service.
3. **Add a fixture for every wire format you touch.** ISO-TP bugs do not throw
   exceptions; they silently shift bytes and produce plausible wrong answers.

## Adding a solved layout

Put it in `obfcm/layouts.py` with `verified=True` only once it decodes **three
different vehicles** with no per-car special-casing. A layout that fits one car
is a coincidence.
