"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Hướng dẫn:
    1. Dùng MarkItDown để convert PDF/DOCX.
    2. Đọc JSON và giữ metadata ở đầu file Markdown.
    3. Giữ cấu trúc thư mục legal/ và news/.
    4. Không tạo file rỗng hoặc file trùng khi chạy lại.

Cài đặt:
    Dependency MarkItDown đã được khai báo trong pyproject.toml.
    
-> Hoặc dùng công cụ nào bạn quen khác Markitdown
"""
import json
from pathlib import Path


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs() -> None:
    """Convert legal PDF/DOC/DOCX files into stable Markdown output files."""
    from markitdown import MarkItDown

    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not legal_dir.is_dir():
        print(f"No legal landing directory: {legal_dir}")
        return

    converter = MarkItDown()
    for path in sorted(legal_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            continue
        content = converter.convert(str(path)).text_content.strip()
        if not content:
            raise ValueError(f"Conversion returned empty content: {path}")
        output = output_dir / f"{path.stem}.md"
        header = f"# {path.stem.replace('_', ' ').title()}\n\n"
        output.write_text(header + content + "\n", encoding="utf-8")
        print(f"Saved: {output}")


def convert_news_articles() -> None:
    """Convert crawled JSON articles into Markdown with source metadata."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not news_dir.is_dir():
        print(f"No news landing directory: {news_dir}")
        return

    required_fields = ("url", "title", "date_crawled", "content_markdown")
    for path in sorted(news_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [field for field in required_fields if not str(data.get(field, "")).strip()]
        if missing:
            raise ValueError(f"{path.name} is missing required fields: {', '.join(missing)}")
        header = (
            f"# {str(data['title']).strip()}\n\n"
            f"**Source:** {str(data['url']).strip()}\n\n"
            f"**Crawled:** {str(data['date_crawled']).strip()}\n\n---\n\n"
        )
        output = output_dir / f"{path.stem}.md"
        output.write_text(header + str(data["content_markdown"]).strip() + "\n", encoding="utf-8")
        print(f"Saved: {output}")


def convert_all() -> None:
    """Convert all landing data while preserving legal/news branches."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
