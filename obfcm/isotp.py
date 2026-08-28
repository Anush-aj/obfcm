"""
ELM327 response parsing and ISO-TP reassembly.

OBFCM responses are always multi-frame, which makes this the load-bearing
piece. Get it wrong and the consecutive-frame PCI byte lands in the middle of
the payload, every field decodes to a plausible-looking wrong number, and
nothing visibly fails.

Three wire formats have to be handled, because which one you get depends on
adapter settings the user may not control:

    single frame   7E8 06 41 0C 1A F8 ...
    ISO-TP multi   7E8 10 0B 49 17 ...  /  7E8 21 F9 ...   (headers on, ATH1)
    indexed        00B / 0: 49 17 01 ... / 1: F9 00 ...     (headers off, CAF1)

In the indexed form the adapter has already stripped PCI bytes and printed the
declared length on its own line; in the raw form it has not, and we must do
both ourselves.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# Adapter-level failures. Any of these anywhere in the response means no data.
NEGATIVE = (
    "NO DATA", "UNABLE TO CONNECT", "CAN ERROR", "BUS INIT", "BUS ERROR",
    "STOPPED", "ERROR", "BUFFER FULL", "DATA ERROR", "FB ERROR", "?",
)


def split_can_header(hexline: str) -> tuple[Optional[str], str]:
    """
    Split an 11-bit (7E8...) or 29-bit (18DAF110...) CAN header off a hex line.

    Returns (header, remainder). header is None for non-CAN protocols
    (ISO 9141-2, KWP2000), where we fall back to plain concatenation.
    """
    if len(hexline) > 8 and hexline.startswith("18DA"):
        return hexline[:8], hexline[8:]
    if len(hexline) > 3 and hexline.startswith("7E"):
        return hexline[:3], hexline[3:]
    return None, hexline


def reassemble(frames: List[List[int]]) -> Optional[bytes]:
    """
    Reassemble one ECU's ISO-TP frames into a single payload.

    PCI encoding per ISO 15765-2:

        0x0N        Single Frame, N = data length (1-7)
        0x1L LL     First Frame, 12-bit total length, 6 data bytes follow
        0x2N        Consecutive Frame, N = sequence number
        0x3x        Flow Control -- sent by the tester, ignored here

    Frames arrive in order within a single response, so arrival order is the
    correct assembly order; sequence numbers are not needed and would wrap
    anyway past 15 frames.
    """
    first: Optional[bytes] = None
    declared: Optional[int] = None
    consecutive: List[bytes] = []
    singles: List[bytes] = []

    for f in frames:
        if not f:
            continue
        kind = f[0] >> 4
        if kind == 0x0:
            n = f[0] & 0x0F
            singles.append(bytes(f[1:1 + n]) if n else bytes(f[1:]))
        elif kind == 0x1 and len(f) >= 2:
            declared = ((f[0] & 0x0F) << 8) | f[1]
            first = bytes(f[2:])
        elif kind == 0x2:
            consecutive.append(bytes(f[1:]))
        # 0x3 flow control: ignore

    if first is not None:
        out = bytearray(first)
        for chunk in consecutive:
            out += chunk
        if declared:
            out = out[:declared]        # drop CAN padding on the final frame
        return bytes(out)

    return singles[0] if singles else None


def extract_payload(hexstr: str, resp_mode: str, pid: str) -> Optional[List[int]]:
    """Locate the echoed mode+pid and return everything after it as ints."""
    idx = hexstr.find(resp_mode + pid)
    if idx >= 0:
        payload = hexstr[idx + 4:]
    else:
        # Mode 09 may carry a record-count byte between mode and infotype.
        idx = hexstr.find(resp_mode)
        if idx < 0:
            return None
        payload = hexstr[idx + 2:]

    payload = re.sub(r"[^0-9A-F]", "", payload)
    if len(payload) % 2:
        payload = payload[:-1]
    if not payload:
        return None
    try:
        return [int(payload[i:i + 2], 16) for i in range(0, len(payload), 2)]
    except ValueError:
        return None


def parse_response(raw: str, mode: str, pid: str) -> Optional[List[int]]:
    """
    Extract the payload bytes for a mode/pid query from raw adapter text.

    Returns a list of ints (payload after the echoed mode+pid), or None if the
    adapter reported a failure or nothing matched.
    """
    up = raw.upper()
    for neg in NEGATIVE:
        if neg in up:
            return None

    resp_mode = f"{int(mode, 16) + 0x40:02X}"
    lines = [l.strip() for l in up.replace("\r", "\n").split("\n") if l.strip()]

    # --- Format 1: adapter-assembled indexed multi-frame ------------------
    indexed: Dict[int, str] = {}
    declared: Optional[int] = None
    for line in lines:
        m = re.match(r"^([0-9A-F]):\s*(.+)$", line)
        if m:
            indexed[int(m.group(1), 16)] = re.sub(r"[^0-9A-F]", "", m.group(2))
        elif re.fullmatch(r"[0-9A-F]{1,3}", line):
            # The ELM327 prints total payload length on its own line ahead of
            # the indexed frames. Without it we keep the CAN padding on the
            # last frame and append phantom bytes to the record.
            declared = int(line, 16)
    if indexed:
        hexstr = "".join(indexed[k] for k in sorted(indexed))
        if declared:
            hexstr = hexstr[:declared * 2]
        return extract_payload(hexstr, resp_mode, pid)

    # --- Format 2: raw CAN frames, grouped by ECU, ISO-TP reassembled -----
    by_header: Dict[str, List[List[int]]] = {}
    headerless = ""
    for line in lines:
        if any(n in line for n in NEGATIVE):
            continue
        h = re.sub(r"[^0-9A-F]", "", line)
        if len(h) < 2:
            continue
        header, body = split_can_header(h)
        if len(body) % 2:
            body = body[:-1]
        try:
            data = [int(body[i:i + 2], 16) for i in range(0, len(body), 2)]
        except ValueError:
            continue
        if header is None:
            headerless += body
        else:
            by_header.setdefault(header, []).append(data)

    # Prefer the engine ECU (7E8); other modules answering a functional
    # request are discarded unless nothing else echoes our command.
    for header in sorted(by_header, key=lambda x: (x != "7E8", x)):
        payload = reassemble(by_header[header])
        if payload is None:
            continue
        got = extract_payload(payload.hex().upper(), resp_mode, pid)
        if got is not None:
            return got

    # --- Format 3: non-CAN protocols, no PCI framing ----------------------
    if headerless:
        return extract_payload(headerless, resp_mode, pid)
    return None


def responding_ecu(raw: str) -> Optional[str]:
    """Best guess at which CAN header answered, for provenance."""
    for line in raw.upper().replace("\r", "\n").split("\n"):
        h = re.sub(r"[^0-9A-F]", "", line.strip())
        header, _ = split_can_header(h)
        if header:
            return header
    return None
