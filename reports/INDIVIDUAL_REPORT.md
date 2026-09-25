# Individual contribution report

Mỗi thành viên copy template này thành:

```text
reports/<student-id>-<short-name>.md
```

Giới hạn khuyến nghị: 1 trang, không chép lại README hoặc mô tả lý thuyết chung. Báo cáo không phải một bài pipeline cá nhân; mục đích là ghi nhận ownership và bằng chứng đóng góp trong sản phẩm nhóm.

---

## Thông tin

- Họ và tên: Đào Gia Bảo
- Mã học viên: 2A202602793
- Nhóm: FourGuys
- Repository/branch: https://github.com/dotrongbinhf/K4-L3B-RAG-Pipeline/tree/main

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 6 — BM25 lexical retrieval | Hoàn thiện xử lý query rỗng, chỉ xếp hạng chunk có token giao với query và thêm tie-break theo ID để kết quả ổn định. Loại bỏ điều kiện `score <= 0` vì BM25 trên corpus nhỏ có thể cho IDF bằng hoặc nhỏ hơn 0 dù chunk vẫn phù hợp. | `src/task6_lexical_search.py`, commit `426ddb0` (`feat: task 6`) | Done |

Chỉ kê khai công việc có thể đối chiếu bằng file, commit, pull request, test hoặc kết quả evaluation.

## Quyết định kỹ thuật quan trọng

Mô tả tối đa hai quyết định mà bạn trực tiếp tham gia:

1. **Quyết định:** Dùng token overlap làm điều kiện giữ ứng viên thay cho điều kiện BM25 score dương.
   **Lý do/evidence:** Commit `426ddb0` ghi nhận BM25 có thể cho IDF bằng hoặc âm trên corpus nhỏ; overlap vẫn bảo toàn chunk có thuật ngữ của query.
   **Trade-off:** Overlap từ vựng không nhận diện đồng nghĩa; semantic search trong pipeline bù cho giới hạn này.

2. **Quyết định:** Sắp xếp ứng viên theo BM25 score giảm dần, sau đó theo ID.
   **Lý do/evidence:** `lexical_search()` dùng khóa `(-score, id)`, giúp kết quả lặp lại có thứ tự xác định khi điểm bằng nhau.
   **Trade-off:** Tie-break theo ID không biểu đạt mức độ liên quan ngoài trường hợp điểm bằng nhau.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: `HF_HUB_OFFLINE=1 .venv/bin/python -m pytest tests/test_contracts.py -q` và query `Vietnam tourism food` qua `python -m src.task6_lexical_search`.
- Kết quả trước/sau nếu có: 15 contract tests passed; query trả về tối đa `top_k` kết quả BM25 có metadata và `retrieval_method="bm25"`.
- Lỗi đã phát hiện và cách xử lý: Điều kiện lọc `score <= 0` có thể loại kết quả phù hợp khi IDF của corpus nhỏ không dương; thay bằng kiểm tra token overlap.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: BM25 dựa trên token nên chưa xử lý tốt truy vấn diễn đạt khác từ vựng tài liệu.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: Thêm bộ test tiếng Việt cho từ đồng nghĩa, dấu câu và truy vấn không có token giao để đánh giá rõ điểm yếu lexical retrieval.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 2026-09-25
- Tên thành viên: Đào Gia Bảo
