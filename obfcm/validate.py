"""
Plausibility gating for decoded OBFCM records.

Why this matters more than it looks
-----------------------------------
Slovakia read OBFCM at every vehicle inspection station nationwide for eight
months. Of 1,434 attempted reads, only 76.7% returned valid data -- and even
restricting to mandate-era (2021+) registrations, roughly **12% were garbage**,
with the authors noting the data showed "the fuel or energy consumption gap by
several orders of magnitude" (Tapák et al., Energies 2023, 16(19), 6861).

Ross-Tech forum users report the same class of nonsense: a 2018 Tiguan
reporting an average speed of 378 km/h.

So a decoder that returns a number for every car is not a feature -- it is a
bug. Roughly one car in eight must be refused.

The reset problem
-----------------
A *low* reading is not necessarily corruption. Annex XXII 5.3 and 5.4 permit
the counters to reset on ECU replacement, on ECU malfunction, and -- for
vehicles registered in 2021, before the preservation obligation bit -- on
battery disconnect. This module distinguishes "implausible" from "legitimately
reset", because telling a user their car is faulty when it merely had its
battery changed is worse than saying nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .record import Record


class Severity(Enum):
    OK = 0
    SUSPECT = 1        # unusual but physically possible; show with a caveat
    IMPLAUSIBLE = 2    # physically impossible or clearly corrupt; refuse

    def __lt__(self, other):
        return self.value < other.value


class Powertrain(Enum):
    ICE = "ice"
    HEV = "hev"        # non-plug-in hybrid: behaves like ICE for fuel purposes
    PHEV = "phev"      # can legitimately show near-zero fuel over long distance
    UNKNOWN = "unknown"


# Plausible lifetime-average fuel consumption, L/100km.
#
# Lower bounds: the most efficient production diesel hypermiled sits near
# 3 L/100km, so anything under 1.5 cannot be a real ICE lifetime average.
# A PHEV driven almost entirely on grid electricity legitimately approaches
# zero, so it gets no meaningful lower bound.
#
# Upper bounds: a heavy SUV in permanent city traffic tops out around 25;
# 50 is generous headroom for a supercar or a fault. Beyond that the record
# is corrupt, not thirsty.
CONSUMPTION_BOUNDS = {
    Powertrain.ICE: (1.5, 50.0),
    Powertrain.HEV: (1.5, 50.0),
    Powertrain.PHEV: (0.0, 50.0),
    Powertrain.UNKNOWN: (0.5, 60.0),
}

# No road car accumulates this. Catches sign errors and wild scale mistakes.
MAX_LIFETIME_DISTANCE_KM = 2_000_000.0

# Odometer vs OBFCM distance. UN R39 permits the dashboard odometer a ±4%
# tolerance, and Annex XXII 2.6 says OBFCM uses the same source -- so they
# should track closely. A large shortfall points at a counter reset.
ODOMETER_EXCESS_TOLERANCE = 0.10      # OBFCM may exceed odometer by 10%
ODOMETER_RESET_THRESHOLD = 0.50       # OBFCM below half the odometer -> reset


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.code}: {self.message}"


@dataclass
class Verdict:
    findings: List[Finding] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        return max((f.severity for f in self.findings), default=Severity.OK)

    @property
    def usable(self) -> bool:
        """True if the record can be shown to a user, possibly with a caveat."""
        return self.severity is not Severity.IMPLAUSIBLE

    @property
    def reset_suspected(self) -> bool:
        return any(f.code == "COUNTER_RESET_SUSPECTED" for f in self.findings)

    def __bool__(self) -> bool:
        return self.usable

    def explain(self) -> str:
        if not self.findings:
            return "OK -- no plausibility concerns."
        return "\n".join(f"  {f}" for f in self.findings)


def validate(record: Record,
             *,
             powertrain: Powertrain = Powertrain.UNKNOWN,
             odometer_km: Optional[float] = None,
             previous: Optional[Record] = None) -> Verdict:
    """
    Check a decoded record for physical plausibility.

    `odometer_km` and `previous` are optional but each meaningfully sharpens
    the result: the odometer catches resets and scale errors, and a previous
    reading catches non-monotonic counters, which no single reading can.
    """
    v = Verdict()
    add = v.findings.append

    fuel = record.total_fuel_l
    dist = record.total_distance_km

    # --- Structural -------------------------------------------------------
    if not record.populated_fields():
        add(Finding(Severity.IMPLAUSIBLE, "EMPTY_RECORD",
                    "No counters decoded. Either the vehicle does not implement "
                    "OBFCM or the layout does not match this response."))
        return v

    if fuel is None and dist is None:
        add(Finding(Severity.IMPLAUSIBLE, "NO_LIFETIME_COUNTERS",
                    "Neither total fuel nor total distance decoded."))
        return v

    if fuel == 0 and dist == 0:
        add(Finding(Severity.SUSPECT, "ALL_ZERO",
                    "Both lifetime counters are zero. Normal for a factory-fresh "
                    "vehicle; otherwise consistent with a counter reset "
                    "(Annex XXII 5.3/5.4)."))

    # --- Fuel/distance coherence -----------------------------------------
    if fuel is not None and dist is not None:
        if dist == 0 and fuel > 0:
            sev = Severity.SUSPECT if fuel < 20 else Severity.IMPLAUSIBLE
            add(Finding(sev, "FUEL_WITHOUT_DISTANCE",
                        f"{fuel:,.2f} L consumed over 0 km. Possible for a "
                        f"vehicle that has only ever idled; otherwise corrupt."))
        elif fuel == 0 and dist > 0:
            if powertrain is Powertrain.PHEV:
                add(Finding(Severity.OK, "PHEV_FULLY_ELECTRIC",
                            f"{dist:,.1f} km with zero fuel -- valid for a PHEV "
                            f"driven entirely in charge-depleting mode."))
            else:
                add(Finding(Severity.IMPLAUSIBLE, "DISTANCE_WITHOUT_FUEL",
                            f"{dist:,.1f} km covered on zero fuel. Impossible "
                            f"for a combustion vehicle. Note OBFCM excludes "
                            f"pure battery-electric vehicles."))

    # --- The main check: implied lifetime consumption ---------------------
    consumption = record.l_per_100km
    if consumption is not None:
        lo, hi = CONSUMPTION_BOUNDS[powertrain]
        if consumption < lo or consumption > hi:
            add(Finding(Severity.IMPLAUSIBLE, "CONSUMPTION_OUT_OF_RANGE",
                        f"Implied lifetime consumption {consumption:,.2f} L/100km "
                        f"is outside the plausible range {lo}-{hi} for "
                        f"{powertrain.value}. This is the signature of the "
                        f"~12% of vehicles that return corrupt OBFCM data."))

    # --- Absolute sanity --------------------------------------------------
    if dist is not None and dist > MAX_LIFETIME_DISTANCE_KM:
        add(Finding(Severity.IMPLAUSIBLE, "IMPLAUSIBLE_DISTANCE",
                    f"Lifetime distance {dist:,.1f} km exceeds "
                    f"{MAX_LIFETIME_DISTANCE_KM:,.0f} km. Likely a field-width "
                    f"or scale error in the layout."))

    for name, value in record.populated_fields().items():
        if value < 0:
            add(Finding(Severity.IMPLAUSIBLE, "NEGATIVE_COUNTER",
                        f"{name} is negative ({value}). Counters are cumulative "
                        f"and cannot decrease."))

    # --- PHEV internal consistency ---------------------------------------
    # Compute the ratio from raw counters rather than reading
    # Record.electric_distance_share: that property clamps to 1.0 so callers
    # can render it safely, which would hide exactly the corruption we are
    # looking for here.
    ev_km = record.distance_charge_depleting_engine_off_km
    if ev_km is not None and dist:
        if ev_km > dist:
            add(Finding(Severity.IMPLAUSIBLE, "PHEV_SHARE_IMPOSSIBLE",
                        f"Charge-depleting engine-off distance "
                        f"({ev_km:,.1f} km) exceeds total distance "
                        f"({dist:,.1f} km)."))

    parts = [record.fuel_charge_depleting_l, record.fuel_charge_increasing_l]
    if fuel is not None and all(p is not None for p in parts):
        if sum(parts) > fuel * 1.01:      # 1% slack for independent rounding
            add(Finding(Severity.SUSPECT, "PHEV_FUEL_SPLIT_EXCEEDS_TOTAL",
                        "Charge-depleting plus charge-increasing fuel exceeds "
                        "total fuel consumed."))

    # --- Cross-check against the dashboard odometer -----------------------
    if odometer_km is not None and dist is not None and odometer_km > 0:
        ratio = dist / odometer_km
        if ratio > 1 + ODOMETER_EXCESS_TOLERANCE:
            add(Finding(Severity.SUSPECT, "DISTANCE_EXCEEDS_ODOMETER",
                        f"OBFCM distance ({dist:,.1f} km) exceeds the odometer "
                        f"({odometer_km:,.1f} km) by "
                        f"{(ratio - 1) * 100:.1f}%. UN R39 allows the odometer "
                        f"±4%; a larger gap suggests a decode error."))
        elif ratio < ODOMETER_RESET_THRESHOLD:
            add(Finding(Severity.SUSPECT, "COUNTER_RESET_SUSPECTED",
                        f"OBFCM distance ({dist:,.1f} km) is far below the "
                        f"odometer ({odometer_km:,.1f} km). Annex XXII 5.3/5.4 "
                        f"permit a reset on ECU replacement or battery "
                        f"disconnect -- the counters are probably valid but "
                        f"cover only part of the vehicle's life."))

    # --- Monotonicity, if we have history --------------------------------
    if previous is not None:
        for name in ("total_fuel_l", "total_distance_km"):
            now, before = getattr(record, name), getattr(previous, name)
            if now is None or before is None:
                continue
            if now < before:
                drop = (before - now) / before if before else 1.0
                code, sev = ("COUNTER_RESET_SUSPECTED", Severity.SUSPECT) \
                    if drop > 0.5 else ("COUNTER_REGRESSION", Severity.IMPLAUSIBLE)
                add(Finding(sev, code,
                            f"{name} decreased from {before:,.2f} to {now:,.2f}. "
                            f"Lifetime counters are cumulative; a large drop "
                            f"indicates a reset, a small one indicates corruption."))

    return v
