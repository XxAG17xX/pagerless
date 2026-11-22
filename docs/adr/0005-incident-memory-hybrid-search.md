# Incident memory: hybrid search in our own Postgres, with a holdout mode

Past incidents (alerts, a correct report's summary, the confirmed cause and fix) live in
`pagerless-db` next to the LangGraph checkpoints. Search merges pgvector similarity (a local
`bge-small-en-v1.5` embedding, so no incident data leaves the machine) with Postgres full-text
search by reciprocal rank fusion, because exact terms such as `valkey` or `ECONNREFUSED` matter
as much as meaning. One database instead of a separate vector store.

Memory is opt-in (`--memory`). In `holdout` mode the incident's own fault type is hidden, so the
score measures help on faults the agent has never seen, not lookups of a known answer.
