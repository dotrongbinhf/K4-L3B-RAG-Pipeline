"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Chủ đề: Du lịch Việt Nam

Mục tiêu:
- Thu thập tối thiểu 3 tài liệu PDF/DOC/DOCX từ nguồn công khai.
- Lưu file gốc vào data/landing/legal/.
- Giữ nguyên tài liệu gốc để sử dụng cho bước chuẩn hóa sau này.
"""

from pathlib import Path

import requests


# Folder lưu raw/legal documents
DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "landing"
    / "legal"
)


# Nguồn chính thức từ Cổng Thông tin điện tử Chính phủ
SOURCES = {
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
    """Tải tài liệu chính sách/quy định từ nguồn công khai."""

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for filename, url in SOURCES.items():
        output_path = DATA_DIR / filename

        # Không tải lại nếu file đã tồn tại
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"Exists: {filename}")
            continue

        print(f"Downloading: {filename}")

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            content = response.content

            # Kiểm tra cơ bản để tránh lưu HTML error page thành .pdf
            if not content.startswith(b"%PDF"):
                raise ValueError(
                    f"Downloaded content is not a valid PDF: {url}"
                )

            output_path.write_bytes(content)

            print(
                f"Saved: {output_path} "
                f"({len(content) / 1024:.1f} KB)"
            )

        except (requests.RequestException, ValueError) as exc:
            print(f"Failed: {filename}")
            print(f"Reason: {exc}")


def validate_documents() -> None:
    """Kiểm tra cơ bản các tài liệu đã tải."""

    documents = list(DATA_DIR.glob("*"))

    valid_extensions = {".pdf", ".doc", ".docx"}

    valid_documents = [
        path
        for path in documents
        if path.suffix.lower() in valid_extensions
        and path.stat().st_size > 0
    ]

    print("\nValidation")
    print("-" * 40)

    for path in valid_documents:
        print(
            f"OK: {path.name} "
            f"({path.stat().st_size / 1024:.1f} KB)"
        )

    print("-" * 40)
    print(f"Total valid documents: {len(valid_documents)}")

    if len(valid_documents) < 3:
        raise RuntimeError(
            "Task 1 requires at least 3 valid legal documents."
        )

    print("Task 1 requirement satisfied.")


if __name__ == "__main__":
    download_documents()
    validate_documents()