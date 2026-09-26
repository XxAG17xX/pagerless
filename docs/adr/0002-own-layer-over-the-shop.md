# Our config is a layer on top of the Shop, never an edit to it

Our alerts, Prometheus config and Grafana dashboard live in our own folders and are loaded by our
own compose file, passed last after the Shop's compose files. Prometheus reads only one config
file, so ours is a copy of the Shop's plus a `rule_files:` line, mounted over theirs.

**Consequences:** when the Shop submodule is upgraded, diff its `src/prometheus/prometheus-config.yaml`
against our copy and carry over any changes. We rejected filling in `shop/compose.extras.yaml` or
editing the Shop's Prometheus config, because both edit borrowed code (ADR 0001).
