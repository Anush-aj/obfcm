"""
Turning an OBFCM payload into a Record.

When more than one layout fits, we do not guess: each candidate is decoded and
validated, and the one producing a physically plausible record wins. A layout
that yields 41,775,269 L/100km is not a close second -- it is wrong, and the
validator says so for free.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .layouts import Layout, candidate_layouts, verified_layouts
from .record import Record
from .validate import Powertrain, Severity, validate


class NoLayoutError(RuntimeError):
    """Raised when no usable layout exists for a payload."""


_NO_VERIFIED_LAYOUT_HELP = """\
No verified OBFCM layout is available yet.

The EU publishes the parameter list (Reg. 2018/1832 Annex XXII point 3) but not
the byte order, field widths or scaling -- those live in SAE J1979-DA, which is
paywalled. This library solves the layout from real captures instead, and does
not yet have enough of them.

Options:
  * Pass allow_unverified=True to decode with the current hypothesis. The
    returned Record will have layout_verified=False. Do not show these numbers
    to anyone as fact.
  * Help finish it -- see docs/HOW-TO-HELP.md. It takes two minutes and needs
    no software installed.
"""


def decode(payload: bytes,
           *,
           allow_unverified: bool = False,
           powertrain: Powertrain = Powertrain.UNKNOWN,
           layout: Optional[Layout] = None) -> Record:
    """
    Decode an OBFCM payload into a Record.

    Refuses to use an unverified layout unless explicitly permitted, because a
    decoder that silently returns invented numbers is worse than one that
    returns nothing: the numbers look plausible and nobody checks them.
    """
    if not payload:
        raise ValueError("empty payload")

    if layout is not None:
        candidates: List[Layout] = [layout]
    else:
        candidates = candidate_layouts(payload, allow_unverified=allow_unverified)

    if not candidates:
        if not allow_unverified and not verified_layouts():
            raise NoLayoutError(_NO_VERIFIED_LAYOUT_HELP)
        raise NoLayoutError(
            f"No layout fits a {len(payload)}-byte payload "
            f"({payload.hex(' ')}). Record shapes vary between conventional "
            f"vehicles (6 parameters) and plug-in hybrids (12)."
        )

    scored: List[Tuple[int, int, Layout, Record]] = []
    for cand in candidates:
        rec = _apply(cand, payload)
        verdict = validate(rec, powertrain=powertrain)
        # Rank: plausible first, then verified, then more fields decoded.
        scored.append((verdict.severity.value, 0 if cand.verified else 1, cand, rec))

    scored.sort(key=lambda t: (t[0], t[1], -len(t[3].populated_fields())))
    best = scored[0]

    if best[0] == Severity.IMPLAUSIBLE.value and len(candidates) > 1:
        # Every candidate produced nonsense. Say so rather than returning the
        # least-bad nonsense.
        raise NoLayoutError(
            f"All {len(candidates)} candidate layouts produced implausible "
            f"values for payload {payload.hex(' ')}. Either this vehicle uses "
            f"a record shape we have not solved, or the response is corrupt "
            f"(~12% of mandate-era vehicles return unusable OBFCM data)."
        )

    return best[3]


def _apply(layout: Layout, payload: bytes) -> Record:
    values = layout.decode(payload)
    return Record(
        raw=payload,
        layout_id=layout.id,
        layout_verified=layout.verified,
        **values,
    )


def try_decode(payload: bytes, **kwargs) -> Optional[Record]:
    """decode() that returns None instead of raising. For batch processing."""
    try:
        return decode(payload, **kwargs)
    except (NoLayoutError, ValueError):
        return None
