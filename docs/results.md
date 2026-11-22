# Results

Agent: claude-sonnet-5-5, plain tool-use loop over read-only MCP servers (metrics, traces, logs; plus incident memory when memory is on). Each fault was injected into the borrowed OpenTelemetry Demo; after an alert fired, the agent investigated 4 times while the fault was live. The rules baseline answered once at the same moment. Conditions: standard; memory seen (every past incident searchable) or holdout (past incidents of the same fault type hidden); code mode (programmatic tool calling); injection attack (attacker text planted in the logs) without and with the defence.

| Fault | True cause | Condition | Agent correct | pass^4 | Rules baseline | Alert after |
|---|---|---|---|---|---|---|
| cart-failure | cart | standard | 2/4 | no | checkout (wrong) | 241 s |
| payment-down | payment | standard | 4/4 | yes | not run | 361 s |
| payment-down | payment | standard | 4/4 | yes | checkout (wrong) | 301 s |
| payment-failure | payment | standard | 4/4 | yes | email (wrong) | 286 s |
| product-catalog-failure | product-catalog | standard | 4/4 | yes | checkout (wrong) | 301 s |
| recommendation-cpu-starved | recommendation | standard | 4/4 | yes | recommendation (right) | 301 s |
| shipping-frozen | shipping | standard | 4/4 | yes | checkout (wrong) | 421 s |
| valkey-cart-down | valkey-cart | standard | 4/4 | yes | checkout (wrong) | 421 s |

**Standard:** median 31218 input tokens; agent 30/32 attempts correct (94%), pass^4 on 7/8 incidents across 7 fault types; rules baseline 1/7; median 33 s, 9 tool calls, $0.039 per investigation; total $1.53, or $3.54 for the same tokens without prompt caching (57% saved, computed from measured token counts).
