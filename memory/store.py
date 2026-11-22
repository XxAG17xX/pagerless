"""Incident memory: past incidents with their confirmed cause and fix, searchable by symptoms.

Stored in pagerless-db (Postgres + pgvector). Search is hybrid: vector similarity (local embedding
model, nothing leaves the machine) and Postgres full-text search, merged with reciprocal rank fusion
so exact terms like "valkey" or "ECONNREFUSED" count as well as meaning.
"""

import json
import os
from pathlib import Path

import psycopg
from fastembed import TextEmbedding

DB_URL = os.environ.get("PAGERLESS_DB", "postgresql://pagerless:pagerless@localhost:5433/pagerless")
MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions, small enough to run on a laptop CPU
CACHE = Path(__file__).resolve().parent.parent / ".cache" / "fastembed"
_embedder = None


def embed(text: str) -> list[float]:
    global _embedder
    _embedder = _embedder or TextEmbedding(MODEL, cache_dir=str(CACHE))
    return [float(x) for x in next(iter(_embedder.embed([text])))]


def connect() -> psycopg.Connection:
    conn = psycopg.connect(DB_URL, autocommit=True)
    conn.execute("create extension if not exists vector")
    conn.execute("""
        create table if not exists incidents (
            id serial primary key,
            run text unique,            -- run folder the incident came from
            fault text,                 -- fault type, used only to hold incidents out in evaluation
            symptoms text,              -- what the on-call engineer saw: alerts and the agent's summary
            root_cause_service text,    -- confirmed cause (from the answer key, as a postmortem would)
            fix text,
            embedding vector(384),
            search tsvector generated always as (to_tsvector('english', symptoms)) stored
        )""")
    return conn


def add(conn, run: str, fault: str, symptoms: str, cause: str, fix: str) -> None:
    vec = json.dumps(embed(symptoms))
    conn.execute("""insert into incidents (run, fault, symptoms, root_cause_service, fix, embedding)
                    values (%s, %s, %s, %s, %s, %s::vector) on conflict (run) do nothing""",
                 (run, fault, symptoms, cause, fix, vec))


def search(conn, symptoms: str, k: int = 3, exclude_fault: str | None = None) -> list[dict]:
    """Top k past incidents by reciprocal rank fusion of vector and full-text rankings."""
    vec = json.dumps(embed(symptoms))
    rows = conn.execute("""
        with v as (select id, row_number() over (order by embedding <=> %(v)s::vector) r
                   from incidents where fault is distinct from %(x)s order by r limit 20),
             t as (select id, row_number() over (order by ts_rank(search, q) desc) r
                   from incidents, websearch_to_tsquery('english', %(s)s) q
                   where search @@ q and fault is distinct from %(x)s order by r limit 20)
        select i.symptoms, i.root_cause_service, i.fix,
               coalesce(1.0 / (60 + v.r), 0) + coalesce(1.0 / (60 + t.r), 0) as score
        from incidents i left join v using (id) left join t using (id)
        where v.id is not null or t.id is not null
        order by score desc limit %(k)s""",
        {"v": vec, "s": symptoms, "x": exclude_fault, "k": k}).fetchall()
    return [{"symptoms": s, "confirmed_cause": c, "fix": f, "score": round(float(sc), 4)} for s, c, f, sc in rows]


def ingest_runs(runs_dir: Path = Path("runs")) -> int:
    """Turn every finished, scored incident into a memory: its alerts and a correct report's summary."""
    conn, n = connect(), 0
    for truth_file in sorted(runs_dir.glob("*/truth.json")):
        truth = json.loads(truth_file.read_text())
        reports = [json.loads(p.read_text()) for p in sorted(truth_file.parent.glob("attempt_*/report.json"))]
        good = [r for r in reports if r.get("root_cause_service", "").lower() == truth["root_cause_service"].lower()]
        if not good:
            continue
        symptoms = f"Alerts: {', '.join(truth.get('alerts', []))}. {good[0]['summary']}"
        add(conn, truth_file.parent.name, truth["fault"], symptoms, truth["root_cause_service"], truth["fix"])
        n += 1
    return n


if __name__ == "__main__":
    print(f"ingested {ingest_runs()} incidents; total {connect().execute('select count(*) from incidents').fetchone()[0]}")
