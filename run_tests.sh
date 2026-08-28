#!/bin/sh
# Everything runs offline, with no dependencies and no vehicle attached.
set -e
cd "$(dirname "$0")"

echo "── wire formats ──────────────────────────────────────────────"
python3 tests/test_parse.py
echo
echo "── library ───────────────────────────────────────────────────"
python3 tests/test_obfcm.py
echo
echo "── layout solver ─────────────────────────────────────────────"
python3 tools/obfcm_solve.py --selftest | tail -4
echo
echo "── probe against fixtures ────────────────────────────────────"
for f in tools/fixtures/*.log; do
    python3 tools/obd_probe.py --replay "$f" \
        --out /tmp/obfcm_t.json --raw /tmp/obfcm_t.log --capture /tmp/obfcm_c.json \
        > /tmp/obfcm_probe.txt 2>&1 \
        && echo "  ok   $f" \
        || { echo "  FAIL $f"; cat /tmp/obfcm_probe.txt; exit 1; }
done
echo
echo "── example syntax ────────────────────────────────────────────"
python3 -m py_compile examples/python_obd_type17.py
echo "  ok   examples/python_obd_type17.py"
echo
echo "── OBDb SAEJ1979 InfoType 17 patch ───────────────────────────"
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("docs/obdb-saej1979-itid17.json").read_text())
cmds = data["commands"]
assert any(c["cmd"] == {"09": "17"} for c in cmds), cmds
assert any(c["cmd"] == {"22": "F817"} for c in cmds), cmds
for c in cmds:
    assert c["hdr"] == "7E0" and c["rax"] == "7E8", c
    assert len(c["signals"]) == 4, c
    for s in c["signals"]:
        fmt = s["fmt"]
        for key in ("bix", "len", "div", "unit"):
            assert key in fmt, (s["id"], fmt)
assert all(s["fmt"]["bix"] == 8 for c in cmds for s in c["signals"] if s["id"] == "OBFCM_DIST_REC")
print(f"  ok   {len(cmds)} commands, Mode 09 ITID 17 and UDS F817")
PY
echo
echo "── read-only safety guard ────────────────────────────────────"
python3 - <<'PY'
import sys; sys.path.insert(0, "tools")
from obd_probe import assert_safe, UnsafeCommand
blocked = ["04", "0401", "08", "2EF190", "3101FF00", "1101", "2701",
           "3401", "1003", "3E00", "22F817"]
for c in blocked:
    try:
        assert_safe(c)
        print(f"  LEAKED {c}"); sys.exit(1)
    except UnsafeCommand:
        pass
for c in ["ATZ", "ATE0", "0100", "0917", "0902"]:
    assert_safe(c)
print(f"  ok   {len(blocked)} write/reset services blocked, reads permitted")
PY
echo
echo "All checks passed."
