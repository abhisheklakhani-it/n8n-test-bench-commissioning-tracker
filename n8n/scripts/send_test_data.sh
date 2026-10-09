#!/usr/bin/env bash
# Loads a small demo scenario into the running workflow (it must be ACTIVE).
# Usage: bash scripts/send_test_data.sh [base_url]   (default http://localhost:5678)
BASE="${1:-http://localhost:5678}"
URL="$BASE/webhook/commissioning-step"

post() { curl -s -X POST "$URL" -H "Content-Type: application/json" -d "$1"; echo; }
step() { post "{\"bench_id\":\"$1\",\"step_id\":\"$2\",\"status\":\"$3\",\"technician\":\"$4\",\"comment\":\"${5:-}\"}"; }

# PS-07: fully commissioned -> release ready
for s in S01 S02 S03 S04 S05 S06 S07; do step PS-07 $s PASS "A. Lakhani"; done

# PS-12: CAN check failed -> P1 alert to Elektrik + Projektleitung
step PS-12 S01 PASS "M. Weber"
step PS-12 S02 PASS "M. Weber"
step PS-12 S03 FAIL "M. Weber" "No CAN messages from ECU"

# PS-21: parallel phase - S04 done, S05 still running, S06 waits for both
step PS-21 S01 PASS "J. Schmidt"
step PS-21 S02 PASS "J. Schmidt"
step PS-21 S03 PASS "J. Schmidt"
step PS-21 S04 PASS "L. Becker"
step PS-21 S05 IN_PROGRESS "T. Nguyen"

# PS-15: just started (lower-case input is normalised)
post '{"bench_id":"ps-15","step_id":"S01","status":"in_progress","technician":"J. Schmidt"}'

# Invalid request -> expect HTTP 400
post '{"bench_id":"PS-99","step_id":"S99","status":"OK"}'

echo "Dashboard: $BASE/webhook/commissioning-status"
