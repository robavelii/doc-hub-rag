"""Retrieval (and optionally answer) evaluation for Doc-Hub.

Ingests evals/corpora/* into a throwaway tenant through the real ingestion
pipeline, asks every question in evals/questions.yaml through the real
retrieval code, and reports hit@k / MRR by question kind and corpus.

  cd backend
  python -m evals.run_eval                       # report only
  python -m evals.run_eval --check evals/baselines/mock.json   # fail on regression
  python -m evals.run_eval --write-baseline evals/baselines/local.json
  python -m evals.run_eval --answers             # also grade generated answers (needs a real LLM)

Uses whatever EMBEDDING_PROVIDER / RERANKER the environment configures, so the
same harness measures mock (lexical-only signal), local and OpenAI setups.
"""

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import AdminSyncSession, AsyncSessionLocal, set_tenant_rls
from app.models.document import Document
from app.models.tenant import Tenant
from app.services.auth_service import api_key_prefix, generate_api_key, hash_api_key
from app.services.retrieval import retrieve
from app.workers.ingest_task import ingest_notion_page

EVAL_DIR = Path(__file__).resolve().parent
KS = (1, 3, 6)
REGRESSION_TOLERANCE = 0.02
REFUSAL = "don't have that information"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def load_questions(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text())
    out = []
    for corpus, items in data.items():
        for i, item in enumerate(items):
            out.append({"id": f"{corpus}-{i:03d}", "corpus": corpus, **item})
    return out


def setup_tenant() -> tuple[str, list[str]]:
    tenant_id = uuid.uuid4()
    raw = generate_api_key()
    with AdminSyncSession() as db:
        db.add(
            Tenant(
                id=tenant_id,
                name="Eval tenant",
                slug=f"eval-{tenant_id.hex[:8]}",
                plan="pro",
                api_key_hash=hash_api_key(raw),
                api_key_prefix=api_key_prefix(raw),
            )
        )
    doc_ids = []
    for path in sorted((EVAL_DIR / "corpora").glob("*/*")):
        doc_id = uuid.uuid4()
        with AdminSyncSession() as db:
            db.add(
                Document(
                    id=doc_id,
                    tenant_id=tenant_id,
                    filename=path.name,
                    file_type="md" if path.suffix == ".md" else "txt",
                    s3_key="",
                    status="pending",
                )
            )
        result = ingest_notion_page.apply(args=[str(doc_id), str(tenant_id), path.read_text(), path.name])
        if result.failed():
            raise RuntimeError(f"ingestion failed for {path}: {result.result!r}")
        doc_ids.append(str(doc_id))
    return str(tenant_id), doc_ids


def teardown_tenant(tenant_id: str) -> None:
    with AdminSyncSession() as db:
        tenant = db.get(Tenant, uuid.UUID(tenant_id))
        if tenant:
            db.delete(tenant)


def _first_hit_rank(chunks, evidence: list[str]) -> int | None:
    spans = [_norm(e) for e in evidence]
    for rank, chunk in enumerate(chunks, start=1):
        text = _norm(chunk.text)
        if any(span in text for span in spans):
            return rank
    return None


async def _answer(question: str, tenant_id: str, db) -> str:
    from app.services.query_service import complete_rag_query, run_rag_query

    context = await run_rag_query(question, tenant_id, db, [])
    return (await complete_rag_query(context, tenant_id, db))["answer"]


async def evaluate(questions: list[dict], tenant_id: str, *, with_answers: bool) -> dict:
    rows = []
    for q in questions:
        async with AsyncSessionLocal() as db:
            await set_tenant_rls(db, tenant_id)
            started = time.perf_counter()
            result = await retrieve(db, tenant_id, q["q"], top_k=max(KS))
            latency_ms = (time.perf_counter() - started) * 1000
            row = {
                "id": q["id"],
                "corpus": q["corpus"],
                "kind": q["kind"],
                "question": q["q"],
                "latency_ms": round(latency_ms, 1),
                "confidence": result.confidence,
                "rank": _first_hit_rank(result.chunks, q["evidence"]) if q["evidence"] else None,
            }
            if with_answers:
                answer = await _answer(q["q"], tenant_id, db)
                row["answer"] = answer
                if q["kind"] == "unanswerable":
                    row["answer_ok"] = REFUSAL in answer.lower()
                elif q.get("answer"):
                    row["answer_ok"] = _norm(q["answer"]) in _norm(answer)
            rows.append(row)
    return summarize(rows)


def _metrics(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["kind"] != "unanswerable"]
    n = len(answerable)
    if not n:
        return {"n": 0}
    out = {"n": n}
    for k in KS:
        out[f"hit@{k}"] = round(sum(1 for r in answerable if r["rank"] and r["rank"] <= k) / n, 3)
    out[f"mrr@{max(KS)}"] = round(sum(1 / r["rank"] for r in answerable if r["rank"]) / n, 3)
    graded = [r for r in rows if "answer_ok" in r]
    if graded:
        out["answer_accuracy"] = round(sum(1 for r in graded if r["answer_ok"]) / len(graded), 3)
    return out


def summarize(rows: list[dict]) -> dict:
    by_kind, by_corpus = defaultdict(list), defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
        by_corpus[r["corpus"]].append(r)
    latencies = [r["latency_ms"] for r in rows]
    return {
        "config": {
            "embedding_provider": settings.embedding_provider_name,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "reranker": getattr(settings, "RERANKER", "none"),
        },
        "overall": _metrics(rows),
        "by_kind": {k: _metrics(v) for k, v in sorted(by_kind.items()) if k != "unanswerable"},
        "by_corpus": {k: _metrics(v) for k, v in sorted(by_corpus.items())},
        "latency_ms": {
            "p50": round(statistics.median(latencies), 1),
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 1),
        },
        "misses": [
            {"id": r["id"], "question": r["question"]}
            for r in rows
            if r["kind"] != "unanswerable" and not r["rank"]
        ],
        "rows": rows,
    }


def render_report(report: dict) -> str:
    cfg = report["config"]
    out = [f"Embeddings: {cfg['embedding_provider']} ({cfg['embedding_dimensions']}d) · reranker: {cfg['reranker']}", ""]
    header = ["slice", "n"] + [f"hit@{k}" for k in KS] + [f"mrr@{max(KS)}"]
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "---|" * len(header))

    def line(name, m):
        out.append("| " + " | ".join([name, str(m.get("n", 0))] + [f"{m.get(h, 0):.3f}" for h in header[2:]]) + " |")

    line("overall", report["overall"])
    for k, m in report["by_kind"].items():
        line(f"kind: {k}", m)
    for k, m in report["by_corpus"].items():
        line(f"corpus: {k}", m)
    out.append("")
    out.append(f"Latency p50 {report['latency_ms']['p50']} ms · p95 {report['latency_ms']['p95']} ms")
    if "answer_accuracy" in report["overall"]:
        out.append(f"Answer accuracy: {report['overall']['answer_accuracy']:.3f}")
    out.append(f"Misses at k={max(KS)}: {len(report['misses'])}")
    for miss in report["misses"]:
        out.append(f"- {miss['id']}: {miss['question']}")
    return "\n".join(out)


def print_report(report: dict) -> None:
    text = render_report(report)
    print("\n" + text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write("## Retrieval eval\n\n" + text + "\n")


def check_regression(report: dict, baseline_path: Path) -> list[str]:
    baseline = json.loads(baseline_path.read_text())
    failures = []
    for metric, expected in baseline["overall"].items():
        if metric == "n" or not isinstance(expected, int | float):
            continue
        actual = report["overall"].get(metric, 0)
        if actual < expected - REGRESSION_TOLERANCE:
            failures.append(f"{metric}: {actual:.3f} < baseline {expected:.3f} (tolerance {REGRESSION_TOLERANCE})")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=EVAL_DIR / "questions.yaml")
    parser.add_argument("--report", type=Path, default=EVAL_DIR / "results" / "latest.json")
    parser.add_argument("--check", type=Path, help="baseline JSON; exit 1 if any overall metric regresses")
    parser.add_argument("--write-baseline", type=Path, help="write the overall metrics as a new baseline")
    parser.add_argument("--answers", action="store_true", help="also generate and grade answers (real LLM)")
    args = parser.parse_args()

    questions = load_questions(args.questions)
    tenant_id, _ = setup_tenant()
    try:
        report = asyncio.run(evaluate(questions, tenant_id, with_answers=args.answers))
    finally:
        teardown_tenant(tenant_id)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))
    print_report(report)

    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps({"config": report["config"], "overall": report["overall"]}, indent=2) + "\n"
        )
        print(f"Baseline written to {args.write_baseline}")
    if args.check:
        failures = check_regression(report, args.check)
        if failures:
            print("\nRETRIEVAL REGRESSION:\n  " + "\n  ".join(failures))
            return 1
        print(f"\nNo regression against {args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
