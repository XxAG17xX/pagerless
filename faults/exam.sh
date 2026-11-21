#!/usr/bin/env bash
# Run the exam: every fault in turn, the agent investigating each one REPEATS times.
# Usage: bash faults/exam.sh [repeats] [fault ...]   (default: 4 repeats, all faults)
# Waits for a healthy Shop (no alert pending or firing) before each fault; skips after 20 minutes.
cd "$(dirname "$0")/.."
REPEATS=${1:-4}; shift
FAULTS=${*:-payment-failure cart-failure product-catalog-failure currency-down shipping-frozen recommendation-cpu-starved valkey-cart-down payment-down}

alerting() {
  curl -s localhost:9090/api/v1/alerts | python -c \
    "import sys,json;print(sum(a['state'] in ('firing','pending') for a in json.load(sys.stdin)['data']['alerts']))"
}

for f in $FAULTS; do
  for _ in $(seq 80); do [ "$(alerting)" = "0" ] && break; sleep 15; done
  if [ "$(alerting)" != "0" ]; then echo "== $f: skipped, Shop still alerting after 20 min"; continue; fi
  echo "== $f"
  uv run --env-file .env faults/inject.py "$f" --agent --repeats "$REPEATS" 2>&1 \
    | grep -E "broke the Shop|^alert:|^baseline:|^attempt|^fixed|Error|error:" | grep -v " INFO "
done
