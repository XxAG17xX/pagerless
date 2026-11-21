# Results

Agent: claude-sonnet-5-5, plain tool-use loop over 3 read-only MCP servers (metrics, traces, logs).
Each fault was injected into the borrowed OpenTelemetry Demo; after an alert fired, the agent investigated 4 times while the fault was live. The rules baseline answered once at the same moment.

| Fault | True cause | Agent correct | pass^4 | Rules baseline | Alert after |
|---|---|---|---|---|---|
| cart-failure | cart | 2/4 | no | checkout (wrong) | 241 s |
| payment-down | payment | 4/4 | yes | not run | 361 s |
| payment-down | payment | 4/4 | yes | checkout (wrong) | 301 s |
| payment-failure | payment | 4/4 | yes | email (wrong) | 286 s |
| product-catalog-failure | product-catalog | 4/4 | yes | checkout (wrong) | 301 s |
| recommendation-cpu-starved | recommendation | 4/4 | yes | recommendation (right) | 301 s |
| shipping-frozen | shipping | 4/4 | yes | checkout (wrong) | 421 s |
| valkey-cart-down | valkey-cart | 4/4 | yes | checkout (wrong) | 421 s |

- **Agent:** 30/32 attempts correct (94%); pass^4 on 7/8 incidents across 7 fault types.
- **Rules baseline:** 1/7 incidents correct (14%).
- **Per investigation (median):** 33 s, 9 tool calls, $0.039.
- **Total API cost of these 32 investigations:** $1.53. Billing the same tokens without prompt caching would have cost $3.54, so caching cut cost by 57% (computed from measured token counts, not a separate run).
