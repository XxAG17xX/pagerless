# LangGraph on top of the plain loop, with Pagerless's own Postgres

The plain loop (`agent/investigate.py`) stays as the reference and is what the exam scores. The
LangGraph version (`agent/graph.py`) uses the same prompt and tools and adds the two things the loop
cannot do: checkpoints after every step, so a crashed investigation resumes, and an `interrupt` that
pauses for a human to approve the fix. Checkpoints live in our own `pagerless-db` (Postgres with
pgvector, which incident memory will reuse), never in the Shop's database.

**Consequence:** on Windows, psycopg's async mode needs the selector event loop, which cannot start
subprocesses, so the graph connects to the MCP servers in-process rather than over stdio.
