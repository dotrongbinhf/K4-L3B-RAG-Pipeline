"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Hướng dẫn:
    1. Chọn chủ đề của nhóm.
    2. Tìm tối thiểu 3 tài liệu PDF/DOCX từ nguồn công khai.
    3. Lưu file gốc vào data/landing/legal/.
    4. Đặt tên không dấu và thể hiện đúng nội dung.

Ví dụ tài liệu: học phí, học bổng, ký túc xá, quy trình đăng ký.
Nếu website chặn crawler, hãy chọn nguồn công khai khác; không vượt WAF.
"""

from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

DOCUMENT_SOURCES = {
    "luat_du_lich_2017.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2017/07/09.signed.pdf"
    ),
    "nghi_dinh_168_2017.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2018/03/168.signed.pdf"
    ),
    "quyet_dinh_509_quy_hoach_du_lich.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/6/509-ttg.signed.pdf"
    ),
    "quyet_dinh_382_ke_hoach_thuc_hien_quy_hoach.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/02/382-qd-ttg.signed.pdf"
    ),
    "nghi_dinh_348_xu_phat_du_lich.pdf": (
        "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/12/348-ndcp.signed.pdf"
    ),
}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def download_documents() -> None:
    """Download stable, official tourism-law PDFs into the landing area."""
    import requests

    setup_directory()
    headers = {"User-Agent": "K4-L3B-RAG-Pipeline/1.0 (educational project)"}

    for filename, url in DOCUMENT_SOURCES.items():
        output = DATA_DIR / filename
        if output.exists() and output.stat().st_size > 1024:
            print(f"Already exists: {output}")
            continue

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.content
        if len(content) <= 1024 or not content.startswith(b"%PDF-"):
            raise ValueError(f"Expected a valid PDF from {url}")

        output.write_bytes(content)
        print(f"Saved: {output}")


if __name__ == "__main__":
    download_documents()
