#!/usr/bin/env python3
"""
Read SAE J1979 InfoType 17 (OBFCM) with python-OBD.

This file is an example in the MIT-licensed obfcm repository. It is not a
patch to python-OBD and does not relicense this code under the GPL.
python-OBD (https://github.com/brendan-w/python-OBD) is GPLv2, barely
maintained, and has no InfoType 17 command — so we keep a custom OBDCommand
here rather than waiting on an upstream PR.

Requires:
    pip install obfcm          # this package, stdlib only
    pip install obd            # python-OBD, optional, GPL — not a runtime dep

Usage:
    python3 examples/python_obd_type17.py
    python3 examples/python_obd_type17.py /dev/ttyUSB0
"""

from __future__ import annotations

import os
import sys

# Git clone: allow `python3 examples/python_obd_type17.py` without pip install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import obfcm


def decode_type17(messages):
    """
    python-OBD decoder.

    ``messages[0].data`` is the reassembled ISO-TP payload including the
    SID and PID/DID echo. Strip those, then pass the same 17-byte record
    ``obfcm.decode`` expects: item-index ``01`` then four big-endian uint32s.
    """
    if not messages:
        return None
    data = bytes(messages[0].data)
    if not data:
        return None
    if data[0] == 0x62:       # UDS ReadDataByIdentifier: 62 F8 17 ...
        payload = data[3:]
    elif len(data) >= 2:      # service 09: 49 17 ...
        payload = data[2:]
    else:
        payload = data
    return obfcm.decode(payload, allow_unverified=True)


def type17_command():
    """Custom OBDCommand for service 09 InfoType 17. python-OBD import is local
    so this module can be read without python-OBD installed."""
    from obd import OBDCommand
    from obd.protocols import ECU

    # 19 response bytes: 49 17 + 01 item-index + 16 data bytes.
    # fast=False: do not append a frame-count digit to a multi-frame Mode 09.
    return OBDCommand(
        "OBFCM_TYPE17",
        "OBFCM distance/fuel used, recent/lifetime (SAE J1979 ITID $17)",
        b"0917",
        19,
        decode_type17,
        ECU.ENGINE,
        False,
    )


def type17_uds_command():
    """Same record via OBDonUDS DID F817, for platforms that ignore 0917."""
    from obd import OBDCommand
    from obd.protocols import ECU

    return OBDCommand(
        "OBFCM_TYPE17_UDS",
        "OBFCM via UDS ReadDataByIdentifier F817",
        b"22F817",
        20,  # 62 F8 17 + 01 + 16 data bytes
        decode_type17,
        ECU.ENGINE,
        False,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        import obd
    except ImportError:
        print("python-OBD is not installed. pip install obd", file=sys.stderr)
        return 2

    args = argv if argv is not None else sys.argv[1:]
    port = args[0] if args else None
    connection = obd.OBD(port) if port else obd.OBD()
    if not connection.is_connected():
        print("No adapter.", file=sys.stderr)
        return 1

    for cmd in (type17_command(), type17_uds_command()):
        response = connection.query(cmd, force=True)
        if response.is_null() or response.value is None:
            print(f"{cmd.command.decode()} -> no data")
            continue
        rec = response.value
        print(f"{cmd.command.decode()} via {cmd.name}: {rec.summary()}")
        print(f"  layout {rec.layout_id}  verified={rec.layout_verified}")
        print(f"  recent {rec.recent_distance_km} km / {rec.recent_fuel_l} L")
        print(f"  life   {rec.total_distance_km} km / {rec.total_fuel_l} L")
        connection.close()
        return 0

    connection.close()
    print("No OBFCM response on 0917 or 22F817.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
