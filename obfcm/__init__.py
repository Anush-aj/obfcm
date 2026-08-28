"""
obfcm -- read the EU-mandated lifetime fuel and distance counters from any car.

Commission Regulation (EU) 2018/1832 Annex XXII requires every car first
registered in the EU/UK from 1 January 2021 to keep lifetime counters of total
fuel consumed and total distance travelled in the ECU. Regulation (EU) 2021/392
Art. 9(2) requires the readout to be "free of charge and not subject to any
specific conditions".

The data is in roughly 60-70 million vehicles. Reading it needs a €10 ELM327
clone. And yet no free app and no open-source project can do it, because the
byte layout is published only in SAE J1979-DA, which costs $100-300.

This library exists to close that gap.

Quick start
-----------
    import obfcm

    result = obfcm.read(send=my_transport)      # send(cmd) -> raw adapter text
    if result.ok:
        record = obfcm.decode(result.payload, allow_unverified=True)
        verdict = obfcm.validate(record)
        if verdict.usable:
            print(record.summary())
        else:
            print(verdict.explain())

Status
------
Protocol, reassembly, decoding, validation and reporting are complete and
tested. Layout ``type17-v1`` is solved from a real paired capture but stays
verified=False until it decodes three vehicles with no special-casing --
see CONTRIBUTING.md. decode() therefore refuses unless you pass
allow_unverified=True, and any Record it returns carries
layout_verified=False.

That refusal is deliberate. A decoder that confidently returns invented
numbers would be worse than no decoder at all.
"""

from .decode import NoLayoutError, decode, try_decode
from .isotp import parse_response, reassemble
from .layouts import LAYOUTS, FieldSpec, Layout, layout_from_solver, verified_layouts
from .protocol import STRATEGIES, Attempt, ReadResult, Strategy, read
from .record import Record
from .validate import Finding, Powertrain, Severity, Verdict, validate

__version__ = "0.1.0"

__all__ = [
    # Reading
    "read", "ReadResult", "Attempt", "Strategy", "STRATEGIES",
    # Decoding
    "decode", "try_decode", "NoLayoutError", "Record",
    # Validation
    "validate", "Verdict", "Finding", "Severity", "Powertrain",
    # Layouts
    "Layout", "FieldSpec", "LAYOUTS", "verified_layouts", "layout_from_solver",
    # Low level
    "parse_response", "reassemble",
    "__version__",
]
