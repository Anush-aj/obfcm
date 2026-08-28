"""
Asking the car for its OBFCM record.

There is no single command that works everywhere. The known variance, which is
the main engineering risk in this project:

  * Most vehicles answer legacy OBD service 09 InfoType 0x17 on the functional
    address (`0917`).
  * OBDonUDS platforms map InfoTypes into DID range 0xF800-0xF8FF, requested
    with UDS service 0x22 (`22 F8 17`). BMW and VW MQB are reported to differ
    on which of these responds.
  * Some vehicles behind a gateway answer only when physically addressed to
    the engine ECU rather than broadcast.

So we try strategies in order and stop at the first that yields a payload.
Every attempt is recorded, because a vehicle that answers *nothing* is itself
a useful data point during the solving phase.

Everything here is READ-ONLY. Service 09 is "Request Vehicle Information" and
service 22 is "ReadDataByIdentifier"; neither can write, reset, actuate or
clear anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .isotp import parse_response, responding_ecu

# A transport is any callable that sends one command and returns the adapter's
# raw text reply. This keeps the library independent of how you talk to the
# dongle -- pyserial, a socket, someone else's ELM327 wrapper, or a test stub.
Transport = Callable[[str], str]


@dataclass(frozen=True)
class Strategy:
    name: str
    command: str
    mode: str
    pid: str
    setup: tuple[str, ...] = ()
    teardown: tuple[str, ...] = ()
    note: str = ""


# Ordered most-likely-first. Cheap to try them all: each is one round trip.
STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        name="classic-functional",
        command="0917", mode="09", pid="17",
        note="Legacy OBD service 09 InfoType 0x17, functional addressing. "
             "What Slovakia's inspection system uses with €10 ELM327 clones.",
    ),
    Strategy(
        name="uds-functional",
        command="22F817", mode="22", pid="F817",
        note="OBDonUDS: InfoTypes map into DID 0xF800-0xF8FF via service 0x22.",
    ),
    Strategy(
        name="classic-engine-ecu",
        command="0917", mode="09", pid="17",
        setup=("ATSH7E0", "ATCRA7E8"),
        teardown=("ATCRA",),
        note="Physically addressed to the engine ECU, for gateway-equipped "
             "vehicles that ignore functional requests.",
    ),
    Strategy(
        name="uds-engine-ecu",
        command="22F817", mode="22", pid="F817",
        setup=("ATSH7E0", "ATCRA7E8"),
        teardown=("ATCRA",),
        note="UDS, physically addressed.",
    ),
)


@dataclass
class Attempt:
    strategy: str
    command: str
    raw: str
    payload: Optional[bytes]

    @property
    def ok(self) -> bool:
        return self.payload is not None


@dataclass
class ReadResult:
    payload: Optional[bytes] = None
    strategy: Optional[str] = None
    command: str = ""
    ecu: str = ""
    attempts: List[Attempt] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.payload is not None

    def explain(self) -> str:
        if self.ok:
            return (f"OBFCM responded via '{self.strategy}' ({self.command}) "
                    f"from ECU {self.ecu or '?'}: {len(self.payload)} bytes")
        tried = ", ".join(a.strategy for a in self.attempts)
        return f"No OBFCM response. Tried: {tried or '(nothing)'}"


def read(send: Transport,
         *,
         strategies: tuple[Strategy, ...] = STRATEGIES,
         include_uds: bool = True) -> ReadResult:
    """
    Ask the vehicle for its OBFCM record, trying each strategy in turn.

    `send` is any callable taking a command string and returning the adapter's
    raw reply. Set `include_uds=False` to restrict to legacy service 09 -- some
    users prefer to opt in to UDS explicitly even though it is read-only.
    """
    result = ReadResult()

    for strat in strategies:
        if not include_uds and strat.mode == "22":
            continue

        for cmd in strat.setup:
            send(cmd)
        try:
            raw = send(strat.command)
        finally:
            for cmd in strat.teardown:
                send(cmd)

        payload = parse_response(raw, strat.mode, strat.pid)
        attempt = Attempt(strategy=strat.name, command=strat.command, raw=raw,
                          payload=bytes(payload) if payload else None)
        result.attempts.append(attempt)

        if attempt.ok:
            result.payload = attempt.payload
            result.strategy = strat.name
            result.command = strat.command
            result.ecu = responding_ecu(raw) or ""
            break

    return result
