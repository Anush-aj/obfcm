# Captures

One JSON file per vehicle. A capture is **usable** only when it has both:

- `raw` — the hex reply to `0917` (or `22F817`)
- `known` — the decoded values from VCDS / OBDeleven for the *same car*

Either alone proves nothing. Files with `raw: null` are half-captures waiting
for the other side.

```bash
python3 tools/obfcm_solve.py captures/*.json     # once you have 3 complete
```

## Known InfoType map

From NEtech's post on [Ross-Tech thread 36805](https://forums.ross-tech.com/index.php?threads/36805/)
(VCDS, `[33-OBD]`, VW Golf 8, Apr 2023). Each parameter is reported as a
**Recent / Lifetime** pair:

| Type | Contents |
|---|---|
| 16 | Engine Run-Idle Time — ignition counter, fuelled ignition cycles, total engine run time, total idle run time |
| **17** | **Distance-Fuel Used — total distance travelled, total fuel consumed** ← the OBFCM counters |
| 18 | PKE-EOE — positive kinetic energy (km/h²), engine output energy (kWh) |
| 19 | PSA — propulsion system active time: total, idle, city |
| 24 | Active powertrain warm-up features off-cycle credit — warm-up timer |
