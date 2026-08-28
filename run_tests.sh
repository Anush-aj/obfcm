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
