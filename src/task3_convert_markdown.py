"""Task 3 — Convert landing legal documents and news into Markdown."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from markitdown import MarkItDown

PROJECT_DIR = Path(__file__).resolve().parent.parent
LEGAL_INPUT_DIR = PROJECT_DIR / "data/landing/legal"
NEWS_INPUT_DIR = PROJECT_DIR / "data/landing/news"
LEGAL_OUTPUT_DIR = PROJECT_DIR / "data/standardized/legal"
NEWS_OUTPUT_DIR = PROJECT_DIR / "data/standardized/news"
MIN_CONTENT_LENGTH = 100


def _clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\f", "\n\n---\n\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def _write(path: Path, content: str) -> None:
    content = content.strip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
        print(f"Saved: {path.relative_to(PROJECT_DIR)}")


def _ocr_pdf(path: Path) -> str:
    """OCR only when MarkItDown extracts too little usable text."""
    with tempfile.TemporaryDirectory(prefix="rag-ocr-") as temporary:
        sidecar = Path(temporary) / "document.txt"
        output = Path(temporary) / "document.pdf"
        command = [
            "ocrmypdf", "--force-ocr", "--language", "vie+eng",
            "--rotate-pages", "--deskew", "--optimize", "0",
            "--output-type", "pdf", "--sidecar", str(sidecar),
            str(path), str(output),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("Install OCRmyPDF and Tesseract with the Vietnamese (vie) language pack.") from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(error.stderr[-2000:] or "OCRmyPDF failed") from error
        return _clean(sidecar.read_text(encoding="utf-8", errors="replace"))


def convert_legal_docs() -> tuple[int, int]:
    """Convert each legal source, using OCR as a fallback for scanned PDFs."""
    files = sorted(path for path in LEGAL_INPUT_DIR.iterdir() if path.suffix.lower() in {".pdf", ".doc", ".docx"})
    if not files:
        raise FileNotFoundError(f"No legal documents found in {LEGAL_INPUT_DIR}")
    converter = MarkItDown()
    succeeded = failed = 0
    for path in files:
        try:
            text = _clean(converter.convert(str(path)).text_content)
            if path.suffix.lower() == ".pdf" and len(text) < 1000:
                text = _ocr_pdf(path)
            if len(text) < MIN_CONTENT_LENGTH:
                raise ValueError(f"Extracted content is too short ({len(text)} characters)")
            output = LEGAL_OUTPUT_DIR / f"{path.stem}.md"
            _write(output, f"**Source file:** `{path.relative_to(PROJECT_DIR).as_posix()}`\n\n**Document type:** Legal / policy document\n\n---\n\n{text}")
            succeeded += 1
        except Exception as error:
            print(f"Failed: {path.name} — {error}")
            failed += 1
    return succeeded, failed


def convert_news_articles() -> tuple[int, int]:
    """Convert landing news JSON while retaining its URL and crawl metadata."""
    files = sorted(NEWS_INPUT_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No news JSON files found in {NEWS_INPUT_DIR}")
    succeeded = failed = 0
    required = {"url", "title", "date_crawled", "content_markdown"}
    for path in files:
        try:
            article = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(article, dict) or not required <= article.keys():
                raise ValueError(f"Expected fields: {', '.join(sorted(required))}")
            if not all(isinstance(article[key], str) and article[key].strip() for key in required):
                raise ValueError("Article metadata and content must be non-empty strings")
            body = _clean(article["content_markdown"])
            if len(body) < MIN_CONTENT_LENGTH:
                raise ValueError("Article content is too short")
            title = " ".join(article["title"].split())
            content = (
                f"# {title}\n\n**Source:** {article['url'].strip()}\n\n"
                f"**Crawled:** {' '.join(article['date_crawled'].split())}\n\n"
                f"**Landing file:** `{path.relative_to(PROJECT_DIR).as_posix()}`\n\n---\n\n{body}"
            )
            _write(NEWS_OUTPUT_DIR / f"{path.stem}.md", content)
            succeeded += 1
        except Exception as error:
            print(f"Failed: {path.name} — {error}")
            failed += 1
    return succeeded, failed


def convert_all() -> None:
    """Convert both source types and report any failures."""
    legal_ok, legal_failed = convert_legal_docs()
    news_ok, news_failed = convert_news_articles()
    print(f"Legal: {legal_ok} converted, {legal_failed} failed")
    print(f"News: {news_ok} converted, {news_failed} failed")
    if legal_failed or news_failed:
        raise RuntimeError("Task 3 had conversion failures")


if __name__ == "__main__":
    convert_all()
