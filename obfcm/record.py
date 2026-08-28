"""
The OBFCM record and its derived metrics.

Field names follow Commission Regulation (EU) 2018/1832 Annex XXII point 3,
which is the authoritative list. Point 3.1 defines six parameters for
conventional and non-OVC hybrid vehicles; point 3.2 defines twelve for OVC-HEVs
(plug-in hybrids), adding the charge-depleting / charge-increasing breakdown
and grid energy.

Only the lifetime counters are modelled here. The instantaneous parameters in
the same list (engine fuel rate, vehicle fuel rate, vehicle speed) are already
available as ordinary Mode 01 PIDs and are not what makes OBFCM interesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Unit conversion constants.
_LITRES_PER_UK_GALLON = 4.54609188
_LITRES_PER_US_GALLON = 3.785411784
_KM_PER_MILE = 1.609344


@dataclass
class Record:
    """
    A decoded OBFCM lifetime record.

    All counters are cumulative over the life of the vehicle. Per Annex XXII
    5.2 they must be preserved across power loss (for vehicles type-approved
    from 1 Jan 2022 and all new vehicles from 1 Jan 2023), but 5.3 and 5.4
    permit a reset on ECU replacement or malfunction -- so a low reading is
    ambiguous, not necessarily wrong. See `obfcm.validate`.
    """

    # --- Annex XXII 3.1: all vehicles -------------------------------------
    #
    # VCDS output from a VW Golf 8 (Ross-Tech thread 36805) shows Type 17
    # reports each parameter TWICE, as "Recent / Lifetime":
    #
    #     Total Distance Traveled : 3960.1 km / 3969.3 km
    #     Total Fuel Consumed     : 358.33 L / 361.36 L
    #
    # The regulation only names the lifetime counters, so the recent pair is
    # either an addition in the standard's field order or a VAG extension.
    # Either way the record is twice the size assumed, and the solver must
    # look for four values, not two.
    total_fuel_l: Optional[float] = None
    total_distance_km: Optional[float] = None
    recent_fuel_l: Optional[float] = None
    recent_distance_km: Optional[float] = None

    # --- Annex XXII 3.2: OVC-HEV (plug-in hybrid) only --------------------
    fuel_charge_depleting_l: Optional[float] = None
    fuel_charge_increasing_l: Optional[float] = None
    distance_charge_depleting_engine_off_km: Optional[float] = None
    distance_charge_depleting_engine_on_km: Optional[float] = None
    distance_charge_increasing_km: Optional[float] = None
    grid_energy_kwh: Optional[float] = None

    # --- Provenance -------------------------------------------------------
    raw: bytes = b""
    command: str = ""          # "0917" or "22F817"
    ecu: str = ""              # responding CAN header, e.g. "7E8"
    layout_id: str = ""        # which layout decoded this
    layout_verified: bool = False

    # ------------------------------------------------------------------
    # Derived metrics
    #
    # Every one returns None rather than raising or dividing by zero, because
    # a partially populated record is normal: many vehicles answer with the
    # ICE subset only, and a brand-new car legitimately has zero distance.
    # ------------------------------------------------------------------

    @property
    def is_phev(self) -> bool:
        """True if any OVC-HEV-only counter is populated."""
        return any(v is not None for v in (
            self.fuel_charge_depleting_l,
            self.fuel_charge_increasing_l,
            self.distance_charge_depleting_engine_off_km,
            self.grid_energy_kwh,
        ))

    @property
    def l_per_100km(self) -> Optional[float]:
        if not self.total_fuel_l or not self.total_distance_km:
            return None
        return self.total_fuel_l * 100.0 / self.total_distance_km

    @property
    def km_per_l(self) -> Optional[float]:
        """India and much of Asia quote kmpl rather than L/100km."""
        if not self.total_fuel_l or not self.total_distance_km:
            return None
        return self.total_distance_km / self.total_fuel_l

    @property
    def mpg_uk(self) -> Optional[float]:
        kpl = self.km_per_l
        return None if kpl is None else kpl * _LITRES_PER_UK_GALLON / _KM_PER_MILE

    @property
    def mpg_us(self) -> Optional[float]:
        kpl = self.km_per_l
        return None if kpl is None else kpl * _LITRES_PER_US_GALLON / _KM_PER_MILE

    @property
    def electric_distance_share(self) -> Optional[float]:
        """
        Fraction of lifetime distance driven with the engine off, 0.0-1.0.

        This is the PHEV number nobody else can show you. The EU's own
        aggregated OBFCM data found real-world PHEV fuel consumption running
        far above type-approval values, precisely because assumed electric
        share is optimistic. This is the measured share for one specific car.
        """
        off = self.distance_charge_depleting_engine_off_km
        if off is None or not self.total_distance_km:
            return None
        return min(1.0, off / self.total_distance_km)

    @property
    def recent_l_per_100km(self) -> Optional[float]:
        """Consumption over the recent window, where the vehicle reports one."""
        if not self.recent_fuel_l or not self.recent_distance_km:
            return None
        return self.recent_fuel_l * 100.0 / self.recent_distance_km

    def populated_fields(self) -> dict[str, float]:
        """Only the counters that actually decoded, for display and export."""
        names = (
            "total_fuel_l", "total_distance_km",
            "recent_fuel_l", "recent_distance_km",
            "fuel_charge_depleting_l", "fuel_charge_increasing_l",
            "distance_charge_depleting_engine_off_km",
            "distance_charge_depleting_engine_on_km",
            "distance_charge_increasing_km", "grid_energy_kwh",
        )
        return {n: getattr(self, n) for n in names if getattr(self, n) is not None}

    def summary(self) -> str:
        """One-line human summary. Never invents precision it does not have."""
        if not self.populated_fields():
            return "empty record"
        bits = []
        if self.total_fuel_l is not None:
            bits.append(f"{self.total_fuel_l:,.2f} L")
        if self.total_distance_km is not None:
            bits.append(f"{self.total_distance_km:,.1f} km")
        if (c := self.l_per_100km) is not None:
            bits.append(f"{c:.2f} L/100km ({self.km_per_l:.2f} kmpl)")
        if (share := self.electric_distance_share) is not None:
            bits.append(f"{share * 100:.0f}% electric")
        return "  ".join(bits)
