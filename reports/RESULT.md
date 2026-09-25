# Kết quả đánh giá RAG

## Thông tin lần chạy

| Trường | Giá trị |
| --- | --- |
| Ngày đánh giá | 2026-09-25 |
| Framework và phiên bản | Ragas 0.4.3 |
| Mô hình đánh giá | OpenAI `gpt-4o-mini` |
| Mô hình sinh câu trả lời | OpenAI `gpt-4o-mini` |
| Mô hình embedding | Sentence Transformers `BAAI/bge-m3` |
| Phiên bản/commit corpus | `4b5fabb` |
| Số lượng bộ dữ liệu golden | 15 |
| `top_k` | 5 |
| Ngưỡng fallback và hiệu chỉnh | `SCORE_THRESHOLD=0.3`; không dùng fallback trong A/B; chunk size 500, overlap 50, recursive chunking. |

## Cấu hình

- **Cấu hình A — dense-only:** Truy xuất cosine bằng BAAI/bge-m3, `top_k=5`.
- **Cấu hình B — hybrid + RRF:** Cùng dense retriever, bổ sung BM25 và gộp bằng RRF (`k=60`), `top_k=5`.

Hai cấu hình dùng cùng golden dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

## Điểm tổng thể

| Chỉ số | Cấu hình A | Cấu hình B | Chênh lệch B−A |
| --- | ---: | ---: | ---: |
| Tính trung thực | 0.922 | 0.917 | -0.006 |
| Mức độ liên quan của câu trả lời | 0.515 | 0.560 | +0.045 |
| Khả năng thu hồi ngữ cảnh | 1.000 | 0.933 | -0.067 |
| Độ chính xác ngữ cảnh | 0.872 | 0.826 | -0.046 |
| **Trung bình** | 0.827 | 0.809 | -0.018 |

## So sánh A/B

- Cấu hình tốt hơn: Cấu hình A — dense-only.
- Bằng chứng: Điểm Ragas tổng hợp từ cùng 15 trường hợp cho thấy A cao hơn B 0.018 điểm trung bình.
- Trade-off về latency/cost: Chưa đo trong lần chạy này.

## Trường hợp kém nhất

| # | Câu hỏi | Cấu hình | Trung thực | Liên quan | Thu hồi | Chính xác | Giai đoạn lỗi | Nguyên nhân gốc |
| --: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | Du khách muốn đến gần các khối đá vôi ở Vịnh Hạ Long nên chọn hoạt động nào? | B — hybrid + RRF | 0.750 | 0.521 | 0.000 | 1.000 | truy xuất | Context recall bằng 0.000: RRF không thu hồi context tham chiếu về kayaking. |
| 2 | Nghị định 348/2025/NĐ-CP bãi bỏ cụm từ nào tại Điều 6? | B — hybrid + RRF | 0.000 | 0.586 | 1.000 | 1.000 | sinh câu trả lời | Faithfulness bằng 0.000 dù ngữ cảnh có độ chính xác 1.000. |
| 3 | Theo kế hoạch thực hiện quy hoạch du lịch, nhiệm vụ chuyển đổi số trong ngành du lịch được thực hiện trong thời gian nào? | A — dense-only | 0.667 | 0.000 | 1.000 | 1.000 | sinh câu trả lời | Answer relevance bằng 0.000 dù ngữ cảnh phù hợp đã được thu hồi. |

## Khuyến nghị

| Ưu tiên | Hành động | Bằng chứng từ phân tích lỗi | Tác động kỳ vọng | Cách xác minh |
| ---: | --- | --- | --- | --- |
| 1 | Điều chỉnh BM25/RRF cho truy vấn hoạt động tại địa danh. | Hạ Long với RRF có context recall 0.000. | Tăng khả năng thu hồi context cho truy vấn du lịch cụ thể. | Chạy lại 15 trường hợp và kiểm tra context recall của truy vấn Hạ Long. |
| 2 | Ràng buộc generator trích xuất nguyên văn khi hỏi về điều khoản pháp lý và thời hạn. | Nghị định 348 có faithfulness 0.000; chuyển đổi số có answer relevance 0.000. | Giảm câu trả lời không bám ngữ cảnh. | Chạy lại hai trường hợp và kiểm tra faithfulness/relevance. |
| 3 | Đo độ trễ của cả hai cấu hình. | Lần chạy này chỉ ghi nhận chất lượng. | Làm rõ trade-off chất lượng/chi phí. | Ghi nhận thời gian thực thi của từng truy vấn cho cả hai cấu hình. |

## Thí nghiệm bonus

| Thí nghiệm | Baseline | Chênh lệch chỉ số | Chênh lệch độ trễ/chi phí | Kết luận |
| --- | --- | ---: | ---: | --- |
| Chưa chạy | Không áp dụng | Không áp dụng | Không áp dụng | Chưa có thí nghiệm bonus nào được đo. |
