"""
OBFCM record layouts.

The layout is DATA, not code
----------------------------
Everything else in this package is finished. The only unknown is where each
counter sits inside the response and what it is scaled by -- and that is
expressed here as a table. When `tools/obfcm_solve.py` produces a layout from
real captures, it drops into `LAYOUTS` and the whole library works.

Why there is no verified layout yet
-----------------------------------
Commission Regulation (EU) 2018/1832 Annex XXII point 3 publishes the
*parameter list* for free. The byte order, field widths and scaling factors are
deferred to ISO 15031-5 / SAE J1979-DA via UN/ECE R83 Annex 11 App.1
§6.5.3.2(a). J1979-DA costs $100-300, which is the sole reason no open-source
implementation exists anywhere.

We are solving it from examples instead. See docs/recruitment/.

The honesty rule
----------------
A layout carries `verified: bool`. `obfcm.decode()` refuses to use an
unverified layout unless the caller explicitly opts in. A decoder that
confidently returns invented numbers would be worse than no decoder at all --
the numbers would look plausible and nobody would check them.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Optional


@dataclass(frozen=True)
class FieldSpec:
    """Where one counter lives inside the record payload."""
    offset: int
    width: int
    scale: Fraction
    endian: str = "big"

    def decode(self, payload: bytes) -> Optional[float]:
        if self.offset + self.width > len(payload):
            return None
        raw = int.from_bytes(payload[self.offset:self.offset + self.width],
                             self.endian)
        return float(raw * self.scale)

    def describe(self) -> str:
        s = self.scale
        pretty = f"1/{s.denominator}" if s.numerator == 1 else f"{s.numerator}/{s.denominator}"
        return (f"bytes[{self.offset}:{self.offset + self.width}] "
                f"{self.endian}-endian x {pretty}")


@dataclass(frozen=True)
class Layout:
    """A complete field assignment for one record shape."""
    id: str
    description: str
    verified: bool
    fields: Dict[str, FieldSpec]
    source: str = ""

    @property
    def min_length(self) -> int:
        if not self.fields:
            return 0
        return max(f.offset + f.width for f in self.fields.values())

    def fits(self, payload: bytes) -> bool:
        return len(payload) >= self.min_length

    def decode(self, payload: bytes) -> Dict[str, float]:
        out = {}
        for name, spec in self.fields.items():
            value = spec.decode(payload)
            if value is not None:
                out[name] = value
        return out


# ---------------------------------------------------------------------------
# The registry
#
# Add verified layouts here as they are solved. Keep unverified hypotheses
# clearly marked -- they exist so the pipeline is testable end to end, not so
# they can be shipped.
# ---------------------------------------------------------------------------

LAYOUTS: Dict[str, Layout] = {

    # -----------------------------------------------------------------
    # HYPOTHESIS ONLY -- NOT VERIFIED AGAINST ANY REAL VEHICLE.
    #
    # Derived from the published resolutions (0.01 L, 0.1 km seen in Slovak
    # PTI readouts and consistent with ICCT's remark that grid energy has
    # "only one decimal place") plus the Annex XXII 3.1 parameter order, and
    # assuming byte 0 of the payload is a record-count byte.
    #
    # It is here so decode/validate/report can be tested without a car. It
    # must not be trusted, and `verified=False` makes the library refuse it
    # unless the caller explicitly asks.
    # -----------------------------------------------------------------
    "ice-hypothesis-v1": Layout(
        id="ice-hypothesis-v1",
        description="Conventional/HEV, Annex XXII 3.1 order (HYPOTHESIS)",
        verified=False,
        source="inferred from published resolutions; no vehicle confirms it",
        fields={
            "total_fuel_l": FieldSpec(offset=1, width=4, scale=Fraction(1, 100)),
            "total_distance_km": FieldSpec(offset=5, width=4, scale=Fraction(1, 10)),
        },
    ),
}


def verified_layouts() -> list[Layout]:
    return [l for l in LAYOUTS.values() if l.verified]


def candidate_layouts(payload: bytes, allow_unverified: bool = False) -> list[Layout]:
    """Layouts long enough to decode `payload`, verified ones first."""
    pool = LAYOUTS.values() if allow_unverified else verified_layouts()
    fitting = [l for l in pool if l.fits(payload)]
    return sorted(fitting, key=lambda l: (not l.verified, l.id))


def layout_from_solver(layout_id: str,
                       assignment: Dict[str, tuple],
                       description: str = "",
                       source: str = "",
                       verified: bool = True) -> Layout:
    """
    Build a Layout from `tools/obfcm_solve.py` output.

    `assignment` maps field name -> (offset, width, endian, scale), which is
    exactly what the solver's FieldLayout carries. This closes the loop:
    solve, paste, ship.
    """
    return Layout(
        id=layout_id,
        description=description or f"solved layout {layout_id}",
        verified=verified,
        source=source,
        fields={
            name: FieldSpec(offset=o, width=w, endian=e, scale=Fraction(s))
            for name, (o, w, e, s) in assignment.items()
        },
    )
