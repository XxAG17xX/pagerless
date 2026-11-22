#!/usr/bin/env bash
# The Stage 4 experiments, one after another, each on a healthy Shop:
#   1. prompt injection, without and with the defence (2 incidents x 4 attempts each)
#   2. code mode on every fault type (4 attempts each)
#   3. incident memory in holdout mode on every fault type (4 attempts each)
# Usage: bash faults/experiments.sh   (several hours; about $5 of API calls)
cd "$(dirname "$0")/.."
ALL="payment-down payment-failure cart-failure product-catalog-failure currency-down shipping-frozen recommendation-cpu-starved valkey-cart-down"

alerting() {
  curl -s localhost:9090/api/v1/alerts | python -c \
    "import sys,json;print(sum(a['state'] in ('firing','pending') for a in json.load(sys.stdin)['data']['alerts']))"
}

run() {  # run <label> <fault> [inject.py flags...]
  for _ in $(seq 80); do [ "$(alerting)" = "0" ] && break; sleep 15; done
  if [ "$(alerting)" != "0" ]; then echo "== $1 $2: skipped, Shop still alerting after 20 min"; return; fi
  echo "== $1 $2"
  uv run --env-file .env faults/inject.py "$2" --agent --repeats 4 "${@:3}" 2>&1 \
    | grep --line-buffered -E "broke the Shop|^alert:|^baseline:|^attempt|^fixed|Traceback"
}

for i in 1 2; do
  PAGERLESS_DEFENCE=0 run "injection, no defence" payment-down-injected
  PAGERLESS_DEFENCE=1 run "injection, with defence" payment-down-injected
done
for f in $ALL; do PAGERLESS_CODE_MODE=1 run "code mode" "$f"; done
uv run python memory/store.py 2>&1 | tail -1
for f in $ALL; do run "memory holdout" "$f" --memory holdout; done
uv run faults/results.py > /dev/null && echo "results written to docs/results.md"
