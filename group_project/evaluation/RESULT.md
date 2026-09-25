# Kết quả đánh giá RAG

Báo cáo đầy đủ bằng tiếng Việt được lưu tại `reports/RESULT.md`.

## Overall scores

| Chỉ số | Cấu hình A | Cấu hình B | Chênh lệch B−A |
| --- | ---: | ---: | ---: |
| Tính trung thực | 0.922 | 0.917 | -0.006 |
| Mức độ liên quan của câu trả lời | 0.515 | 0.560 | +0.045 |
| Khả năng thu hồi ngữ cảnh | 1.000 | 0.933 | -0.067 |
| Độ chính xác ngữ cảnh | 0.872 | 0.826 | -0.046 |
| **Trung bình** | 0.827 | 0.809 | -0.018 |

## A/B comparison

Cấu hình A (dense-only) có điểm trung bình cao hơn 0.018. Cấu hình B (hybrid + RRF) có mức độ liên quan cao hơn nhưng thấp hơn về tính trung thực và độ chính xác ngữ cảnh.

## Worst performers

Truy vấn kayaking ở Vịnh Hạ Long với Cấu hình B có context recall 0.000; truy vấn Nghị định 348 với Cấu hình B có faithfulness 0.000. Chi tiết số đo và nguyên nhân được ghi trong `reports/RESULT.md`.

## Recommendations

Điều chỉnh BM25/RRF cho truy vấn hoạt động tại địa danh, ràng buộc generator trích xuất chính xác cho điều khoản pháp lý, và đo độ trễ của hai cấu hình.
