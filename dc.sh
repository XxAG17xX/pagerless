
#!/usr/bin/env bash
export DEMO_VERSION=3.1.0
docker compose --env-file shop/.env --env-file shop/.env.override -f shop/compose.yaml -f shop/compose.observability.yaml -f shop/compose.extras.yaml -f compose.pagerless.yaml "$@"