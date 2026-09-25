# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-25 |
| Framework and version              | Ragas 0.4.3 |
| Evaluator model                    | OpenAI `gpt-4o-mini` |
| Generator model                    | OpenAI `gpt-4o-mini` |
| Embedding model                    | Sentence Transformers `BAAI/bge-m3` |
| Corpus version/commit              | `4b5fabb` |
| Golden dataset size                | 15 |
| `top_k`                            | 5 |
| Fallback threshold and calibration | `SCORE_THRESHOLD=0.3`; fallback disabled during A/B; chunk size 500, overlap 50, recursive chunking. |

## Configurations

- **Config A — dense-only:** Cosine retrieval using BAAI/bge-m3, `top_k=5`.
- **Config B — hybrid + RRF:** Same dense retriever plus BM25, fused with RRF (`k=60`), `top_k=5`.

Hai config phải dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric            | Config A | Config B | Delta B−A |
| ----------------- | -------: | -------: | --------: |
| Faithfulness      |    0.922 |    0.917 |    -0.006 |
| Answer relevance  |    0.515 |    0.560 |    +0.045 |
| Context recall    |    1.000 |    0.933 |    -0.067 |
| Context precision |    0.872 |    0.826 |    -0.046 |
| **Average**       |    0.827 |    0.809 |    -0.018 |

## A/B comparison

- Cấu hình tốt hơn: Config A — dense-only.
- Bằng chứng: Điểm trung bình của bốn metric Ragas trên cùng 15 trường hợp cao hơn 0.018 cho A.
- Trade-off về latency/cost: Chưa đo trong lần chạy này.

## Worst performers

|   # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage             | Root cause |
| --: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------------------- | ---------- |
|   1 | Du khách muốn đến gần các khối đá vôi ở Vịnh Hạ Long nên chọn hoạt động nào? | B — hybrid + RRF | 0.750 | 0.521 | 0.000 | 1.000 | retrieval | Context recall was 0.000: RRF did not retrieve the reference context about kayaking. |
|   2 | Nghị định 348/2025/NĐ-CP bãi bỏ cụm từ nào tại Điều 6? | B — hybrid + RRF | 0.000 | 0.586 | 1.000 | 1.000 | generation | Faithfulness was 0.000 although the retrieved context had precision 1.000. |
|   3 | Theo kế hoạch thực hiện quy hoạch du lịch, nhiệm vụ chuyển đổi số trong ngành du lịch được thực hiện trong thời gian nào? | A — dense-only | 0.667 | 0.000 | 1.000 | 1.000 | generation | Answer relevance was 0.000 although relevant context was retrieved. |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
|        1 | Tune BM25/RRF for location-specific activity queries. | Ha Long hybrid case had context recall 0.000. | Improve recall for specific tourism queries. | Re-run all 15 cases and inspect Ha Long context recall. |
|        2 | Require the generator to extract exact wording for legal clauses and dates. | Decree 348 faithfulness was 0.000; digital-transformation relevance was 0.000. | Keep answers grounded and on-topic. | Re-run the two cases and inspect faithfulness and answer relevance. |
|        3 | Measure latency for both configurations. | This run recorded answer quality only. | Establish quality, latency, and cost trade-offs. | Record execution time for each query under both configurations. |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| None run | Not applicable | Not applicable | Not applicable | No bonus experiment has been measured. |
