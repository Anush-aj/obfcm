#!/usr/bin/env python3
"""
obd_probe.py -- Phase 0 capability probe for a single vehicle.

Answers one question: what does THIS car actually expose over OBD-II?

Why this exists
---------------
The whole product plan branches on a handful of PIDs that are *optional* in
the standard and wildly inconsistent in practice:

  0x10 MAF                 ~80% of vehicles. Fallback fuel estimation.
  0x2F Fuel tank level     Optional, often frozen/hard-zero. Fill-up detection.
  0x5E Engine fuel rate    ~0.3% of light vehicles. Exact fuel, no DFCO logic.
  0x9D Engine+vehicle rate  Same idea, 4 bytes, g/s.
  0x03 Fuel system status  Needed for DFCO detection if we fall back to MAF.
  Mode 09 InfoType 0x17    OBFCM lifetime fuel+distance counters.

That last one is the interesting gamble. OBFCM is mandated in the EU/UK for
2021+ vehicles and is NOT mandated in India (AIS-137 has no lifetime fuel
counters). But the ECU software on global platforms is often shared, and to my
knowledge nobody has ever published a probe result from an Indian-market car.
If 0x17 responds here, the accuracy architecture changes completely.

Zero dependencies for a WiFi ELM327 (stdlib sockets only).
pyserial is imported lazily and only for --serial.

Usage
-----
  WiFi dongle (most common cheap one; joins its own SoftAP):
      python3 tools/obd_probe.py --wifi 192.168.0.10:35000

  Bluetooth Classic / USB (needs: pip install pyserial):
      python3 tools/obd_probe.py --serial /dev/tty.OBDII

  Replay a saved session without a car (for development):
      python3 tools/obd_probe.py --replay probe_raw.log

Output: a human-readable report plus probe_result.json for the record.
"""

import argparse
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# PIDs we care about. (mode, pid, label, decoder)
# Decoders take a list of data bytes (ints, after the mode/pid echo is stripped)
# and return a human-readable string, or None if it can't be decoded.
# ---------------------------------------------------------------------------

FUEL_SYSTEM_STATUS = {
    0x00: "engine off",
    0x01: "open loop, engine not yet warm",
    0x02: "closed loop, using O2 sensor",
    0x04: "open loop due to driving conditions (power enrichment OR decel enleanment)",
    0x08: "open loop due to system fault",
    0x10: "closed loop, but fault with at least one O2 sensor",
}


def _u16(d, i=0):
    return (d[i] << 8) | d[i + 1]


def dec_fuel_system(d):
    parts = []
    for bank, v in enumerate(d[:2], start=1):
        if v:
            parts.append(f"bank{bank}={FUEL_SYSTEM_STATUS.get(v, hex(v))}")
    return "; ".join(parts) if parts else "all banks 0"


PID_TABLE = [
    # mode, pid, label, decoder, why_it_matters
    ("01", "03", "Fuel system status", dec_fuel_system,
     "DFCO detection -- required if we fall back to MAF estimation"),
    ("01", "04", "Calculated engine load", lambda d: f"{d[0]/2.55:.1f} %", ""),
    ("01", "05", "Coolant temperature", lambda d: f"{d[0]-40} C", ""),
    ("01", "06", "Short term fuel trim b1", lambda d: f"{d[0]/1.28-100:+.1f} %", ""),
    ("01", "07", "Short term fuel trim b2", lambda d: f"{d[0]/1.28-100:+.1f} %", ""),
    ("01", "08", "Long term fuel trim b1", lambda d: f"{d[0]/1.28-100:+.1f} %", ""),
    ("01", "09", "Long term fuel trim b2", lambda d: f"{d[0]/1.28-100:+.1f} %", ""),
    ("01", "0B", "Intake manifold pressure", lambda d: f"{d[0]} kPa",
     "speed-density fallback if MAF is absent"),
    ("01", "0C", "Engine RPM", lambda d: f"{_u16(d)/4:.0f} rpm", ""),
    ("01", "0D", "Vehicle speed", lambda d: f"{d[0]} km/h",
     "trip covariates (avg speed, idle fraction, stop density)"),
    ("01", "0F", "Intake air temperature", lambda d: f"{d[0]-40} C", ""),
    ("01", "10", "MAF air flow rate", lambda d: f"{_u16(d)/100:.2f} g/s",
     "CRITICAL -- primary fuel estimation input"),
    ("01", "11", "Throttle position", lambda d: f"{d[0]/2.55:.1f} %",
     "DFCO disambiguation (enrichment vs enleanment)"),
    ("01", "1F", "Run time since start", lambda d: f"{_u16(d)} s", ""),
    ("01", "21", "Distance with MIL on", lambda d: f"{_u16(d)} km", ""),
    ("01", "2F", "Fuel tank level", lambda d: f"{d[0]/2.55:.1f} %",
     "CRITICAL -- auto fill-up detection"),
    ("01", "31", "Distance since codes cleared", lambda d: f"{_u16(d)} km", ""),
    ("01", "33", "Barometric pressure", lambda d: f"{d[0]} kPa",
     "altitude/elevation covariate"),
    ("01", "42", "Control module voltage", lambda d: f"{_u16(d)/1000:.2f} V", ""),
    ("01", "44", "Commanded equivalence ratio", lambda d: f"{_u16(d)*2/65536:.3f} lambda",
     "open-loop enrichment correction"),
    ("01", "45", "Relative throttle position", lambda d: f"{d[0]/2.55:.1f} %", ""),
    ("01", "46", "Ambient air temperature", lambda d: f"{d[0]-40} C",
     "temperature covariate -- seasonality is a known confounder"),
    ("01", "5C", "Engine oil temperature", lambda d: f"{d[0]-40} C", ""),
    ("01", "5E", "Engine fuel rate", lambda d: f"{_u16(d)/20:.2f} L/h",
     "CRITICAL -- exact fuel, makes DFCO logic unnecessary"),
    ("01", "9D", "Engine + vehicle fuel rate",
     lambda d: f"engine={_u16(d,0)/50:.2f} g/s, vehicle={_u16(d,2)/50:.2f} g/s",
     "CRITICAL -- same, 4-byte variant"),
    ("01", "9E", "Engine exhaust flow rate", lambda d: f"{_u16(d)*0.2:.1f} kg/h", ""),
    ("01", "A2", "Cylinder fuel rate", lambda d: f"{_u16(d)/32:.2f} mg/stroke", ""),
]

MODE9_TABLE = [
    ("09", "02", "VIN", "vehicle identification -- keys the per-model profile"),
    ("09", "04", "Calibration ID", "ECU software version"),
    ("09", "0A", "ECU name", ""),
    ("09", "17", "OBFCM lifetime fuel + distance",
     "THE BIG ONE -- EU-mandated exact counters. Not required in India. Unknown here."),
]

# Support-bitmap PIDs: each reports support for the following 32 PIDs.
SUPPORT_PIDS_M1 = ["00", "20", "40", "60", "80", "A0", "C0"]
SUPPORT_PIDS_M9 = ["00", "20"]



# ---------------------------------------------------------------------------
# SAFETY GUARD
#
# This probe is strictly READ-ONLY. Every command is checked against an
# allowlist before it reaches the vehicle, so the script physically cannot
# send a write, a reset, or a control request even if someone edits the
# tables above carelessly.
#
# Allowed OBD services (all read-only, defined by SAE J1979):
#   01 current data      02 freeze frame     03 stored DTCs
#   06 test results      07 pending DTCs     09 vehicle information
#   0A permanent DTCs
#
# Explicitly BLOCKED:
#   04  clear DTCs / reset MIL      -- erases emissions readiness data
#   08  control of on-board system  -- actuates components
#   2E  WriteDataByIdentifier       -- UDS write
#   2F  InputOutputControl          -- UDS actuation
#   31  RoutineControl              -- UDS routine
#   11  ECUReset                    -- UDS reset
#   27  SecurityAccess              -- UDS unlock
#   34/36/37  data transfer         -- UDS reflash
#   10  DiagnosticSessionControl    -- can leave an ECU in a non-default session
#
# AT/ST commands configure the ELM327 adapter itself and never reach the car.
# ---------------------------------------------------------------------------

READONLY_OBD_SERVICES = {"01", "02", "03", "06", "07", "09", "0A"}
BLOCKED_SERVICES = {
    "04": "clear DTCs / reset readiness monitors",
    "08": "control of an on-board system or component",
    "10": "DiagnosticSessionControl (can leave an ECU out of default session)",
    "11": "ECUReset",
    "14": "ClearDiagnosticInformation",
    "27": "SecurityAccess",
    "28": "CommunicationControl",
    "2E": "WriteDataByIdentifier",
    "2F": "InputOutputControlByIdentifier",
    "31": "RoutineControl",
    "34": "RequestDownload",
    "35": "RequestUpload",
    "36": "TransferData",
    "37": "RequestTransferExit",
    "3E": "TesterPresent (keeps a non-default session alive)",
    "85": "ControlDTCSetting",
}


class UnsafeCommand(Exception):
    pass


def assert_safe(cmd, allow_uds_read=False):
    """Raise UnsafeCommand unless `cmd` is a read-only request."""
    c = cmd.strip().upper().replace(" ", "")
    if not c:
        raise UnsafeCommand("empty command")

    # Adapter configuration -- never leaves the ELM327.
    if c.startswith("AT") or c.startswith("ST"):
        return

    if not re.fullmatch(r"[0-9A-F]+", c):
        raise UnsafeCommand(f"non-hex command rejected: {cmd!r}")

    service = c[:2]
    if service in BLOCKED_SERVICES:
        raise UnsafeCommand(
            f"BLOCKED service {service} ({BLOCKED_SERVICES[service]}). "
            "This probe is read-only by design.")
    if service == "22":
        if not allow_uds_read:
            raise UnsafeCommand(
                "UDS ReadDataByIdentifier (22) is off by default. "
                "It is read-only, but pass --try-uds to opt in explicitly.")
        return
    if service not in READONLY_OBD_SERVICES:
        raise UnsafeCommand(
            f"service {service} is not on the read-only allowlist")


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------

class Transport:
    def write(self, data: bytes): raise NotImplementedError
    def read_until_prompt(self, timeout: float) -> str: raise NotImplementedError
    def close(self): pass


class TcpTransport(Transport):
    """WiFi ELM327. Typically 192.168.0.10:35000."""

    def __init__(self, host, port, connect_timeout=10):
        self.sock = socket.create_connection((host, port), timeout=connect_timeout)
        self.sock.settimeout(0.3)
        self.buf = ""

    def write(self, data: bytes):
        self.sock.sendall(data)

    def read_until_prompt(self, timeout=5.0):
        deadline = time.time() + timeout
        while ">" not in self.buf and time.time() < deadline:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buf += chunk.decode("ascii", errors="replace")
            except socket.timeout:
                continue
        out, _, self.buf = self.buf.partition(">")
        return out

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class SerialTransport(Transport):
    """Bluetooth Classic (rfcomm) or USB. Requires pyserial."""

    BAUD_ORDER = [38400, 9600, 230400, 115200, 57600, 19200]

    def __init__(self, port, baud=None):
        try:
            import serial  # noqa: F401
        except ImportError:
            sys.exit(
                "ERROR: --serial needs pyserial.\n"
                "  pip install pyserial\n"
                "(A WiFi dongle via --wifi needs no extra packages.)"
            )
        import serial
        bauds = [baud] if baud else self.BAUD_ORDER
        last_err = None
        for b in bauds:
            try:
                self.ser = serial.Serial(port, b, timeout=0.3)
                # The first char can get eaten if the interface was mid-command.
                self.ser.write(b"\x7f\x7f\r")
                time.sleep(0.2)
                self.ser.reset_input_buffer()
                self.baud = b
                self.buf = ""
                return
            except Exception as e:  # pragma: no cover - hardware dependent
                last_err = e
        sys.exit(f"ERROR: could not open {port}: {last_err}")

    def write(self, data: bytes):
        self.ser.write(data)

    def read_until_prompt(self, timeout=5.0):
        deadline = time.time() + timeout
        while ">" not in self.buf and time.time() < deadline:
            chunk = self.ser.read(512)
            if chunk:
                self.buf += chunk.decode("ascii", errors="replace")
        out, _, self.buf = self.buf.partition(">")
        return out

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class ReplayTransport(Transport):
    """Replays a raw log so the parser can be developed without a car."""

    def __init__(self, path):
        self.entries = {}
        cur = None
        with open(path) as fh:
            for line in fh:
                if line.startswith(">>> "):
                    cur = line[4:].strip()
                    self.entries[cur] = ""
                elif cur is not None:
                    self.entries[cur] += line
        self.last = None

    def write(self, data: bytes):
        self.last = data.decode("ascii", errors="replace").strip()

    def read_until_prompt(self, timeout=5.0):
        return self.entries.get(self.last, "NO DATA\r\r")


# ---------------------------------------------------------------------------
# ELM327 session
# ---------------------------------------------------------------------------

class Elm327:
    def __init__(self, transport, raw_log=None, verbose=False, allow_uds_read=False):
        self.t = transport
        self.raw_log = raw_log
        self.verbose = verbose
        self.allow_uds_read = allow_uds_read
        self.protocol = None
        self.sent = []

    def cmd(self, s, timeout=5.0, delay=0.0):
        assert_safe(s, allow_uds_read=self.allow_uds_read)   # read-only enforcement
        self.sent.append(s)
        self.t.write((s + "\r").encode("ascii"))
        if delay:
            time.sleep(delay)
        resp = self.t.read_until_prompt(timeout)
        if self.raw_log:
            self.raw_log.write(f">>> {s}\n{resp}\n")
            self.raw_log.flush()
        if self.verbose:
            print(f"    [{s}] -> {resp.strip()!r}")
        return resp

    def init(self):
        """Standard init. Order matters; see ELM327 datasheet."""
        steps = [
            ("ATZ", "reset", 1.0),
            ("ATE0", "echo off", 0.1),
            ("ATL0", "linefeeds off", 0.1),
            ("ATS0", "spaces off", 0.1),
            ("ATH1", "headers on (multi-ECU disambiguation)", 0.1),
            ("ATSP0", "auto protocol", 0.5),
        ]
        print("Initialising adapter")
        for cmd, why, delay in steps:
            resp = self.cmd(cmd, delay=delay)
            ok = "OK" in resp or cmd == "ATZ"
            print(f"  {cmd:<8} {why:<45} {'ok' if ok else 'no ack'}")

        rv = clean(self.cmd("ATRV"))
        print(f"  ATRV     battery voltage{'':<31} {rv}")
        try:
            volts = float(re.sub(r"[^0-9.]", "", rv))
            if volts < 6:
                print("\n  WARNING: battery reads under 6V. Is the ignition on?")
        except ValueError:
            pass

        # Wake the bus and let ATSP0 settle on a protocol.
        probe = self.cmd("0100", timeout=10)
        if "UNABLE TO CONNECT" in probe.upper():
            print("\n  ERROR: adapter could not connect to the vehicle bus.")
            print("  Turn the ignition to ON (engine running is best) and retry.")
            return False
        self.protocol = clean(self.cmd("ATDPN")) + " / " + clean(self.cmd("ATDP"))
        print(f"  ATDP     protocol{'':<38} {self.protocol}")
        return True

    def query(self, mode, pid, timeout=5.0):
        """Returns (data_bytes, raw_text). data_bytes is None if no valid reply."""
        raw = self.cmd(f"{mode}{pid}", timeout=timeout)
        return parse_response(raw, mode, pid), raw


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def clean(s):
    return " ".join(s.replace("\r", " ").replace("\n", " ").split())


# The protocol layer lives in the obfcm package -- this tool is a development
# and field-probe front end for it, not a second implementation.
from obfcm.isotp import NEGATIVE, parse_response, reassemble, split_can_header  # noqa: E402


def decode_support_bitmap(data, base):
    """PID 0x00/0x20/... return 4 bytes = a bitmap for the next 32 PIDs."""
    if not data or len(data) < 4:
        return set()
    bits = int.from_bytes(bytes(data[:4]), "big")
    supported = set()
    for i in range(32):
        if bits & (1 << (31 - i)):
            supported.add(base + 1 + i)
    return supported


# ---------------------------------------------------------------------------
# Probe stages
# ---------------------------------------------------------------------------

def probe_support(elm, mode, support_pids):
    """Walk the support bitmaps to get the declared PID set."""
    supported = set()
    for sp in support_pids:
        base = int(sp, 16)
        data, _ = elm.query(mode, sp)
        if not data:
            break
        found = decode_support_bitmap(data, base)
        supported |= found
        # The top bit of each bitmap indicates the next bitmap is supported.
        if (base + 0x20) not in found:
            break
    return supported


def probe_obfcm(elm):
    """
    OBFCM lives at Mode 09 InfoType 0x17 on classic OBD, or DID 0xF817
    via UDS service 0x22 on OBDonUDS vehicles. Try both.

    The response is multi-frame, so this also exercises ISO-TP reassembly.
    """
    results = {}

    print("\n  Trying classic OBD:  09 17")
    data, raw = elm.query("09", "17", timeout=8)
    results["classic_0917"] = {"raw": clean(raw), "bytes": data}
    if data:
        print(f"    RESPONDED with {len(data)} bytes: {bytes(data).hex(' ')}")
    else:
        print(f"    no data ({clean(raw)[:60]})")

    if not elm.allow_uds_read:
        print("  Skipping OBDonUDS 22 F8 17 (read-only, but opt-in: --try-uds)")
        results["uds_22F817"] = {"skipped": True}
        return results

    print("  Trying OBDonUDS:     22 F8 17")
    raw = elm.cmd("22F817", timeout=8)
    up = raw.upper()
    ok = not any(n in up for n in NEGATIVE) and "62F817" in re.sub(r"[^0-9A-F]", "", up)
    results["uds_22F817"] = {"raw": clean(raw), "ok": ok}
    print(f"    {'RESPONDED' if ok else 'no data'} ({clean(raw)[:60]})")

    return results


def format_obfcm(data):
    """
    Decode the record with the library and show the result.

    The layout is derived from a real paired capture (2020 Ford E-350,
    CarDAQ-Plus 3) but is still marked unverified in obfcm/layouts.py, because
    it has only been confirmed on that one US vehicle. So we decode, but we
    say so.
    """
    if not data:
        return []
    payload = bytes(data)
    out = [f"    record: {len(payload)} bytes -- {payload.hex(' ')}"]

    try:
        import obfcm
        rec = obfcm.decode(payload, allow_unverified=True)
    except Exception as e:                       # noqa: BLE001 - report, never crash
        out.append(f"    could not decode: {e}")
        return out

    fields = rec.populated_fields()
    if not fields:
        out.append("    no fields decoded -- record shape may differ on this vehicle")
        return out

    out.append("")
    for name, value in fields.items():
        unit = "km" if name.endswith("_km") else ("L" if name.endswith("_l") else "")
        out.append(f"      {name:<24} {value:>12,.2f} {unit}")

    if rec.l_per_100km is not None:
        out.append("")
        out.append(f"      lifetime economy         "
                   f"{rec.l_per_100km:>12,.2f} L/100km"
                   f"   ({rec.km_per_l:.2f} kmpl, {rec.mpg_us:.1f} mpg US)")

    verdict = obfcm.validate(rec)
    if verdict.severity is not obfcm.Severity.OK:
        out.append("")
        for line in verdict.explain().splitlines():
            out.append(f"    {line.strip()}")
    if not rec.layout_verified:
        out.append("")
        out.append("    NOTE: layout confirmed on one US vehicle only. Treat these")
        out.append("    numbers as provisional and send us the capture below.")
    return out


def write_capture_stub(path, data, note, protocol):
    """
    Emit a capture file that tools/obfcm_solve.py can consume directly.

    The tester fills in `known` from their VCDS / OBDeleven screen. That pair
    -- raw bytes plus decoded truth -- is the entire input the solver needs.
    """
    stub = [{
        "label": note or "unlabelled vehicle",
        "raw": bytes(data).hex(" "),
        "known": {
            "total_fuel_l": None,
            "total_distance_km": None,
        },
        "notes": f"protocol: {protocol}. Fill 'known' from VCDS address 33 "
                 f"Mode 09 Type 17, or OBDeleven. Remove any field you "
                 f"do not have a value for.",
    }]
    with open(path, "w") as fh:
        json.dump(stub, fh, indent=2)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Probe a vehicle's OBD-II capabilities (Phase 0).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--wifi", metavar="HOST:PORT",
                   help="WiFi ELM327, e.g. 192.168.0.10:35000")
    g.add_argument("--serial", metavar="PORT",
                   help="Serial/Bluetooth port, e.g. /dev/tty.OBDII")
    g.add_argument("--replay", metavar="LOGFILE",
                   help="Replay a saved raw log (no car needed)")
    ap.add_argument("--baud", type=int, help="Force serial baud rate")
    ap.add_argument("--out", default="probe_result.json")
    ap.add_argument("--capture", default="obfcm_capture.json",
                    help="where to write the solver-ready OBFCM capture")
    ap.add_argument("--raw", default="probe_raw.log",
                    help="Raw session log (replayable)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--note", default="", help="Vehicle description for the record")
    ap.add_argument("--try-uds", action="store_true",
                    help="Also try UDS ReadDataByIdentifier 22F817 for OBFCM. "
                         "Read-only, but opt-in.")
    args = ap.parse_args()

    if args.wifi:
        host, _, port = args.wifi.partition(":")
        print(f"Connecting to WiFi adapter at {host}:{port or 35000}")
        transport = TcpTransport(host, int(port or 35000))
    elif args.serial:
        print(f"Opening serial port {args.serial}")
        transport = SerialTransport(args.serial, args.baud)
    else:
        print(f"Replaying {args.replay}")
        transport = ReplayTransport(args.replay)

    raw_log = open(args.raw, "w") if not args.replay else None
    elm = Elm327(transport, raw_log=raw_log, verbose=args.verbose,
                 allow_uds_read=args.try_uds)

    result = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "note": args.note,
        "supported_mode01": [],
        "supported_mode09": [],
        "live": {},
        "obfcm": {},
    }

    try:
        print("=" * 74)
        print("OBD-II CAPABILITY PROBE  --  READ-ONLY")
        print("No write, reset, actuation or reflash command can be sent;")
        print("every command is allowlist-checked before transmission.")
        if args.note:
            print(f"Vehicle: {args.note}")
        print("=" * 74)

        if not elm.init():
            return 1
        result["protocol"] = elm.protocol

        # --- Stage 1: declared support bitmaps ---------------------------
        print("\n" + "-" * 74)
        print("STAGE 1  Declared PID support (Mode 01 bitmaps)")
        print("-" * 74)
        m1 = probe_support(elm, "01", SUPPORT_PIDS_M1)
        result["supported_mode01"] = sorted(f"{p:02X}" for p in m1)
        print(f"  ECU declares {len(m1)} Mode 01 PIDs supported.")
        if m1:
            pretty = " ".join(f"{p:02X}" for p in sorted(m1))
            for i in range(0, len(pretty), 68):
                print(f"    {pretty[i:i+68]}")

        m9 = probe_support(elm, "09", SUPPORT_PIDS_M9)
        result["supported_mode09"] = sorted(f"{p:02X}" for p in m9)
        print(f"\n  ECU declares {len(m9)} Mode 09 InfoTypes supported:"
              f" {' '.join(f'{p:02X}' for p in sorted(m9)) or '(none)'}")
        if 0x17 in m9:
            print("    >>> InfoType 17 IS DECLARED. OBFCM may be present. <<<")

        # --- Stage 2: actually read the PIDs that matter ------------------
        print("\n" + "-" * 74)
        print("STAGE 2  Live read of decision-critical PIDs")
        print("-" * 74)
        print(f"  {'PID':<5} {'Name':<30} {'Result':<28}")
        print(f"  {'-'*5} {'-'*30} {'-'*28}")
        for mode, pid, label, decoder, why in PID_TABLE:
            declared = int(pid, 16) in m1
            data, raw = elm.query(mode, pid)
            if data:
                try:
                    value = decoder(data)
                except Exception:
                    value = f"raw {bytes(data).hex(' ')}"
                status = value
                result["live"][pid] = {"label": label, "supported": True,
                                       "value": value,
                                       "raw": bytes(data).hex(" ")}
            else:
                status = "-- no data --" if declared else "not supported"
                result["live"][pid] = {"label": label, "supported": False}
            flag = "*" if why.startswith("CRITICAL") else " "
            print(f" {flag}{pid:<5} {label:<30} {status:<28}")

        # --- Stage 3: the OBFCM gamble ------------------------------------
        print("\n" + "-" * 74)
        print("STAGE 3  OBFCM lifetime counters  (the unknown for Indian cars)")
        print("-" * 74)
        result["obfcm"] = probe_obfcm(elm)
        ob = result["obfcm"].get("classic_0917", {}).get("bytes")
        if ob:
            print()
            for line in format_obfcm(ob):
                print(line)
            stub = write_capture_stub(args.capture, ob, args.note,
                                      result.get("protocol", "unknown"))
            print(f"\n    Wrote {stub} -- a solver-ready capture.")
            print("    Add your VCDS/OBDeleven values under \"known\", then run:")
            print(f"      python3 tools/obfcm_solve.py {stub}")

        # --- Verdict -------------------------------------------------------
        print("\n" + "=" * 74)
        print("VERDICT")
        print("=" * 74)
        live = result["live"]
        has = lambda p: live.get(p, {}).get("supported")

        if has("5E") or has("9D"):
            print("  FUEL: exact ECU-reported fuel rate available (5E/9D).")
            print("        Use it directly. No DFCO heuristics needed.")
            tier = "exact_fuel_rate"
        elif has("10"):
            print("  FUEL: MAF only. Estimation required, and it will be")
            print("        5-15% off uncalibrated -- WORSE than the dashboard.")
            print("        Ground truth stays the pump receipt; MAF is for")
            print("        covariates and DFCO-corrected live display only.")
            tier = "maf_estimation"
        else:
            print("  FUEL: no MAF, no fuel rate. Speed-density fallback via MAP")
            print("        would need an engine VE model. Not viable.")
            print("        This vehicle is fill-up-log only.")
            tier = "manual_only"
        result["fuel_tier"] = tier

        print(f"\n  TANK LEVEL (2F): {'available' if has('2F') else 'NOT available'}"
              f" -- auto fill-up detection "
              f"{'possible' if has('2F') else 'not possible on this car'}")
        print(f"  DFCO INPUTS:     fuel system status {'ok' if has('03') else 'MISSING'},"
              f" throttle {'ok' if has('11') or has('45') else 'MISSING'}")
        cov = [p for p in ("0D", "0C", "46", "33") if has(p)]
        print(f"  COVARIATES:      {len(cov)}/4 available ({' '.join(cov) or 'none'})")

        if ob:
            print("\n  *** OBFCM RESPONDED. This is a genuinely novel result -- no")
            print("      published probe of an Indian-market vehicle exists.")
            print("      If the counters are plausible, the accuracy architecture")
            print("      changes: exact fuel + distance, no estimation at all.")
        else:
            print("\n  OBFCM: absent, as expected outside the EU/UK.")

    finally:
        if raw_log:
            raw_log.close()
        transport.close()

    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"\nWrote {args.out} and {args.raw}")
    print("Send me both and I'll tell you exactly what to build against.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
