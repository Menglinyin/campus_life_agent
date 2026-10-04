"""Measure the actual HybridRetriever against labeled synthetic chunks."""
import argparse
from tempfile import TemporaryDirectory
from time import perf_counter
from evaluation.common import ROOT, read_jsonl, ranking_metrics, report_base, write_report, percentile
from evaluation.fixtures import isolated_settings, knowledge_chunks
from app.storage.mysql import Database
from app.storage.repositories.knowledge import Knowledge
from app.rag.embedding import Embedding
from app.rag.hybrid_retrieval import HybridRetriever


def run(dataset, embedding_backend="demo", chroma=False, reranker="", k=4):
    cases = read_jsonl(dataset, ("query", "user", "relevant_ids"))
    chunks = knowledge_chunks()
    by_id = {x["id"]: x for x in chunks}
    for case in cases:
        if not isinstance(case["query"], str) or not case["query"].strip():
            raise ValueError("Invalid query")
        if not isinstance(case["relevant_ids"], list) or not isinstance(case["user"], str):
            raise ValueError("Invalid relevance labels")
        for identifier in case["relevant_ids"]:
            if identifier not in by_id or by_id[identifier]["owner"] not in ("public", case["user"]):
                raise ValueError("Relevance labels refer to missing or unauthorized chunks")
    if not 1 <= k <= 20:
        raise ValueError("k must be 1..20")
    report = report_base("rag", embedding_backend, dataset)
    results, latencies, scored = [], [], []
    with TemporaryDirectory(prefix="campus-rag-eval-") as directory:
        settings = isolated_settings(directory, embedding_backend=embedding_backend, chroma=chroma, reranker=reranker)
        settings.retrieval_k = k
        db = Database(settings.database_url)
        try:
            db.initialize()
            repo = Knowledge(db)
            repo.upsert(chunks)
            begin = perf_counter()
            retriever = HybridRetriever(repo, Embedding(settings), settings)
            build_ms = (perf_counter() - begin) * 1000
            for case in cases:
                start = perf_counter()
                try:
                    found = retriever.search(case["query"], case["user"])
                    elapsed = (perf_counter() - start) * 1000
                    latencies.append(elapsed)
                    ids = [x["id"] for x in found]
                    unauthorized = [x["id"] for x in found if x["owner"] not in ("public", case["user"])]
                    metrics = ranking_metrics(ids, case["relevant_ids"], k) if case["relevant_ids"] else None
                    if metrics:
                        scored.append(metrics)
                    results.append({"id": case["id"], "status": "ok", "retrieved_ids": ids,
                                    "unauthorized_count": len(unauthorized), "latency_ms": elapsed,
                                    "metrics": metrics,
                                    "no_answer_returns": len(ids) if not case["relevant_ids"] else None})
                except Exception as exc:
                    if case["relevant_ids"]:
                        scored.append({key: 0.0 for key in ("recall_at_k", "precision_at_k", "mrr_at_k", "hit_at_k")})
                    results.append({"id": case["id"], "status": "error", "error_type": type(exc).__name__})
        finally:
            db.close()
    errors = sum(x["status"] == "error" for x in results)
    leaks = sum(x.get("unauthorized_count", 0) for x in results)
    aggregate = {key: sum(x[key] for x in scored) / len(scored) if scored else None
                 for key in ("recall_at_k", "precision_at_k", "mrr_at_k", "hit_at_k")}
    aggregate.update(cases_total=len(cases), scored_queries=len(scored), errors=errors,
                     unauthorized_returns=leaks, latency_p50_ms=percentile(latencies, .5),
                     latency_p95_ms=percentile(latencies, .95))
    report.update(status="failed" if errors or leaks else "completed", metrics=aggregate, cases=results,
                  configuration={"k": k, "chroma": chroma, "embedding_model": "BAAI/bge-m3",
                                 "embedding_revision": None, "reranker": reranker or None,
                                 "embedding_fp16": settings.embedding_fp16,
                                 "embedding_max_tokens": settings.embedding_max_tokens,
                                 "chunk_count": len(chunks), "build_ms": build_ms},
                  limitations=["Synthetic pre-chunked corpus; not document parsing evaluation.",
                               "Demo character hashing is not BGE semantic quality.",
                               "No-answer returned count is diagnostic, not a guaranteed rejection threshold.",
                               "Recall means macro mean over all labeled queries; retrieval errors count as zero.",
                               "Latency is local sequential search including embedding; not production capacity."])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=ROOT / "rag/dataset.jsonl")
    p.add_argument("--embedding", choices=["demo", "bge"], default="demo")
    p.add_argument("--chroma", action="store_true")
    p.add_argument("--reranker", default="")
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--output", default=ROOT / "reports/rag.json")
    a = p.parse_args()
    try:
        report = run(a.dataset, a.embedding, a.chroma, a.reranker, a.k)
        write_report(a.output, report)
    except (ValueError, OSError) as exc:
        p.exit(2, f"Evaluation could not start: {type(exc).__name__}\n")
    print(f"RAG: {report['status']}; scored={report['metrics']['scored_queries']}; errors={report['metrics']['errors']}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
