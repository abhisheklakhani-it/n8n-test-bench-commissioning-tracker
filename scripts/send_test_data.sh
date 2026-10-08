#!/usr/bin/env bash
# Sends sample commissioning step results to the n8n workflow (must be ACTIVE).
# Usage: bash send_test_data.sh [base_url]   (default http://localhost:5678)
BASE="${1:-http://localhost:5678}"
URL="$BASE/webhook/commissioning-step"

post() { curl -s -X POST "$URL" -H "Content-Type: application/json" -d "$1"; echo; }

# PS-07: fully commissioned -> release ready
for s in S01 S02 S03 S04 S05 S06 S07; do
  post "{\"bench_id\":\"PS-07\",\"step_id\":\"$s\",\"status\":\"PASS\",\"technician\":\"A. Lakhani\"}"
done

# PS-12: in progress with a failure and a blocker
post '{"bench_id":"PS-12","step_id":"S01","status":"PASS","technician":"M. Weber"}'
post '{"bench_id":"PS-12","step_id":"S02","status":"PASS","technician":"M. Weber"}'
post '{"bench_id":"PS-12","step_id":"S03","status":"FAIL","technician":"M. Weber","comment":"No CAN messages from ECU","measurements":{"bus_load_pct":0}}'
post '{"bench_id":"PS-12","step_id":"S04","status":"BLOCKED","technician":"M. Weber","comment":"Pressure sensor not delivered"}'

# PS-15: just started
post '{"bench_id":"ps-15","step_id":"S01","status":"in_progress","technician":"J. Schmidt"}'

# Invalid request -> expect HTTP 400
post '{"bench_id":"PS-99","step_id":"S99","status":"OK"}'

echo "Dashboard: $BASE/webhook/commissioning-status"
