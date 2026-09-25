"""Run measured dense-only versus hybrid-RRF Ragas evaluation."""

import json
import os
import statistics
import subprocess
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    AnswerRelevancy,
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)

from src.task10_generation import SYSTEM_PROMPT, call_llm, format_context, reorder_for_llm
from src.task5_semantic_search import semantic_search
from src.task6_lexical_search import lexical_search
from src.task7_reranking import rerank_rrf


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DATASET = ROOT / "group_project" / "evaluation" / "golden_dataset.json"
PER_CASE_RESULTS = ROOT / "group_project" / "evaluation" / "ab_evaluation_results.json"
REPORT = ROOT / "reports" / "RESULT.md"
TOP_K = 5
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gpt-4o-mini")
EVALUATOR_EMBEDDING_MODEL = os.getenv(
    "EVALUATOR_EMBEDDING_MODEL", "text-embedding-3-small"
)


def retrieve_dense_only(query: str) -> list[dict]:
    return semantic_search(query, top_k=TOP_K)


def retrieve_hybrid_rrf(query: str) -> list[dict]:
    dense = semantic_search(query, top_k=TOP_K * 2)
    sparse = lexical_search(query, top_k=TOP_K * 2)
    return rerank_rrf([dense, sparse], top_k=TOP_K)


def generate_answer(query: str, chunks: list[dict]) -> str:
    if not chunks:
        raise RuntimeError(f"No retrieved evidence for evaluation query: {query}")
    message = f"Context:\n{format_context(reorder_for_llm(chunks))}\n\nQuestion: {query}"
    answer = call_llm(SYSTEM_PROMPT, message)
    if not answer:
        raise RuntimeError(f"Generator returned an empty answer for: {query}")
    return answer


def build_dataset(cases: list[dict], retrieval) -> EvaluationDataset:
    samples = []
    for case in cases:
        chunks = retrieval(case["question"])
        samples.append(
            SingleTurnSample(
                user_input=case["question"],
                response=generate_answer(case["question"], chunks),
                reference=case["expected_answer"],
                retrieved_contexts=[chunk["content"] for chunk in chunks],
                reference_contexts=[case["expected_context"]],
            )
        )
    return EvaluationDataset(samples=samples)


def measured_scores(dataset: EvaluationDataset) -> tuple[dict[str, float], list[dict]]:
    llm = LangchainLLMWrapper(ChatOpenAI(model=EVALUATOR_MODEL, temperature=0))
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=EVALUATOR_EMBEDDING_MODEL)
    )
    result = evaluate(
        dataset,
        metrics=[
            Faithfulness(),
            AnswerRelevancy(),
            LLMContextRecall(),
            LLMContextPrecisionWithReference(),
        ],
        llm=llm,
        embeddings=embeddings,
        show_progress=True,
        raise_exceptions=True,
    )
    rows = result.to_pandas().to_dict(orient="records")
    scores = {
        "faithfulness": statistics.fmean(result["faithfulness"]),
        "answer_relevancy": statistics.fmean(result["answer_relevancy"]),
        "context_recall": statistics.fmean(result["context_recall"]),
        "context_precision": statistics.fmean(
            result["llm_context_precision_with_reference"]
        ),
    }
    return scores, rows


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()[:7]


def write_report(dense: dict[str, float], hybrid: dict[str, float], cases: int) -> None:
    metric_rows = [
        ("Faithfulness", "faithfulness"),
        ("Answer relevance", "answer_relevancy"),
        ("Context recall", "context_recall"),
        ("Context precision", "context_precision"),
    ]
    dense_average = sum(dense.values()) / len(dense)
    hybrid_average = sum(hybrid.values()) / len(hybrid)
    score_lines = []
    for label, key in metric_rows:
        score_lines.append(
            f"| {label} | {dense[key]:.3f} | {hybrid[key]:.3f} | {hybrid[key] - dense[key]:+.3f} |"
        )
    score_lines.append(
        f"| **Average** | {dense_average:.3f} | {hybrid_average:.3f} | {hybrid_average - dense_average:+.3f} |"
    )
    winner = "Config B — hybrid + RRF" if hybrid_average >= dense_average else "Config A — dense-only"
    REPORT.write_text(
        "# RAG evaluation results\n\n"
        "## Run information\n\n"
        "| Field | Value |\n| --- | --- |\n"
        f"| Evaluation date | {date.today().isoformat()} |\n"
        "| Framework and version | Ragas 0.4.3 |\n"
        f"| Evaluator model | OpenAI `{EVALUATOR_MODEL}` |\n"
        f"| Generator model | OpenAI `{os.getenv('LLM_MODEL', 'not configured')}` |\n"
        "| Embedding model | Sentence Transformers `BAAI/bge-m3` |\n"
        f"| Corpus version/commit | `{git_commit()}` |\n"
        f"| Golden dataset size | {cases} |\n"
        f"| `top_k` | {TOP_K} |\n"
        "| Fallback threshold and calibration | Not used in this A/B run; both configurations evaluate their listed retrieval strategy directly. |\n\n"
        "## Configurations\n\n"
        "- **Config A — dense-only:** BAAI/bge-m3 cosine retrieval, `top_k=5`.\n"
        "- **Config B — hybrid + RRF:** the same dense retriever plus BM25, fused with RRF (`k=60`), `top_k=5`.\n\n"
        "Hai config dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.\n\n"
        "## Overall scores\n\n"
        "| Metric | Config A | Config B | Delta B−A |\n| --- | ---: | ---: | ---: |\n"
        + "\n".join(score_lines)
        + "\n\n## A/B comparison\n\n"
        f"- Cấu hình tốt hơn: {winner}.\n"
        "- Evidence: The table contains Ragas aggregate scores from the same 15 cases.\n"
        "- Trade-off về latency/cost: Not measured in this run.\n\n"
        "## Worst performers\n\n"
        "| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |\n"
        "| --: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |\n"
        "| 1 | Not recorded in this aggregate run. | N/A | N/A | N/A | N/A | N/A | evaluation | Per-case metric rows were not persisted. |\n"
        "| 2 | Not recorded in this aggregate run. | N/A | N/A | N/A | N/A | N/A | evaluation | Per-case metric rows were not persisted. |\n"
        "| 3 | Not recorded in this aggregate run. | N/A | N/A | N/A | N/A | N/A | evaluation | Per-case metric rows were not persisted. |\n\n"
        "## Recommendations\n\n"
        "| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |\n"
        "| ---: | --- | --- | --- | --- |\n"
        "| 1 | Persist per-case Ragas rows in the next run. | This run records aggregate metrics only. | Enables grounded failure analysis. | Save and inspect the per-case score table. |\n"
        "| 2 | Measure latency for both configurations. | This run records quality only. | Make the quality/cost trade-off explicit. | Record per-query wall-clock time. |\n"
        "| 3 | Expand the golden dataset with additional legal questions. | The current set is small. | Improve evaluation coverage. | Validate new cases against the standardized corpus. |\n\n"
        "## Bonus experiments\n\n"
        "| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |\n"
        "| --- | --- | ---: | ---: | --- |\n"
        "| Not run | N/A | N/A | N/A | No bonus experiment was measured. |\n",
        encoding="utf-8",
    )


def save_per_case_results(cases: list[dict], dense_rows: list[dict], hybrid_rows: list[dict]) -> None:
    """Persist measured rows so failure analysis remains reproducible."""
    metric_keys = {
        "faithfulness": "faithfulness",
        "answer_relevancy": "answer_relevancy",
        "context_recall": "context_recall",
        "context_precision": "llm_context_precision_with_reference",
    }
    output = []
    for index, case in enumerate(cases):
        output.append(
            {
                "question": case["question"],
                "dense_only": {
                    name: float(dense_rows[index][key])
                    for name, key in metric_keys.items()
                },
                "hybrid_rrf": {
                    name: float(hybrid_rows[index][key])
                    for name, key in metric_keys.items()
                },
            }
        )
    PER_CASE_RESULTS.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for measured Ragas evaluation.")
    cases = json.loads(GOLDEN_DATASET.read_text(encoding="utf-8"))
    dense_scores, dense_rows = measured_scores(build_dataset(cases, retrieve_dense_only))
    hybrid_scores, hybrid_rows = measured_scores(build_dataset(cases, retrieve_hybrid_rrf))
    save_per_case_results(cases, dense_rows, hybrid_rows)
    write_report(dense_scores, hybrid_scores, len(cases))
    print(json.dumps({"dense": dense_scores, "hybrid": hybrid_scores}, indent=2))


if __name__ == "__main__":
    main()
