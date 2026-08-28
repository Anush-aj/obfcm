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


## What VCDS can and cannot give us

**Confirmed negative:** the VCDS Controller Channel Map CSV
(`[Applications]` → `[Controller Channel Map]` → address `33` → Measuring
values → CSV, saved to `C:\Ross-Tech\VCDS\Logs`) contains **decoded values
only**:

```
IDE00011,Vehicle Identification Number (VIN),WV2ZZZ2KZKX007899,
IDE00371,Fuel consumption,0.69, l/h
IDE01922,Vehicle distance driven,189700, km
```

Format is `IDE-number, description, value, unit`. No raw frames. Evidenced by a
2019 VW Caddy channel map posted on the Ross-Tech forums.

So VCDS cannot supply the raw hex on its own. The layout requires **two
artefacts from the same car in the same session**: `0917` raw output from a
generic OBD terminal app, and the decoded Type 17 values from VCDS/OBDeleven.

**Still unverified:** whether VCDS *debug-level* logging (a different feature
from the channel map) captures raw CAN frames. Worth asking; do not assume.
