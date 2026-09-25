"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Strategy
--------
LEGAL:
- PDF  -> OCRmyPDF (Vietnamese + English) -> sidecar text -> Markdown
- DOC/DOCX -> MarkItDown -> Markdown

NEWS:
- JSON -> Markdown
- Preserve url, title, date_crawled metadata

Properties
----------
- Keep legal/ and news/ directory structure.
- Do not create empty Markdown files.
- Deterministic filenames: running again does not create duplicates.
- Overwrite only when content changes.
- Keep traceability back to the landing file.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from markitdown import MarkItDown


# ============================================================
# Paths
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

LANDING_DIR = PROJECT_DIR / "data" / "landing"
OUTPUT_DIR = PROJECT_DIR / "data" / "standardized"

LEGAL_INPUT_DIR = LANDING_DIR / "legal"
NEWS_INPUT_DIR = LANDING_DIR / "news"

LEGAL_OUTPUT_DIR = OUTPUT_DIR / "legal"
NEWS_OUTPUT_DIR = OUTPUT_DIR / "news"

SUPPORTED_LEGAL_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
}

MIN_CONTENT_LENGTH = 100


# ============================================================
# Common helpers
# ============================================================

def relative_project_path(path: Path) -> str:
    """Return a readable project-relative path."""
    try:
        return path.relative_to(PROJECT_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def clean_markdown(text: str) -> str:
    """Minimal cleanup without changing document meaning."""

    if not text:
        return ""

    text = text.replace("\x00", "")

    # Normalize line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # OCR sidecar normally uses form-feed between pages.
    # Convert it into Markdown page separators.
    text = text.replace(
        "\f",
        "\n\n---\n\n",
    )

    # Remove trailing spaces.
    lines = [
        line.rstrip()
        for line in text.splitlines()
    ]

    text = "\n".join(lines)

    # Avoid huge numbers of blank lines.
    text = re.sub(
        r"\n{4,}",
        "\n\n\n",
        text,
    )

    return text.strip()


def validate_content(
    content: str,
    source_name: str,
) -> None:
    """Reject empty or obviously unusable output."""

    if not content:
        raise ValueError(
            f"Empty content: {source_name}"
        )

    if len(content) < MIN_CONTENT_LENGTH:
        raise ValueError(
            f"Content too short: {source_name} "
            f"({len(content)} characters)"
        )


def write_if_changed(
    output_path: Path,
    content: str,
) -> bool:
    """
    Write deterministic output.

    - Same content -> leave existing file untouched.
    - Changed content -> replace same .md file.
    - Never creates duplicate names.
    """

    content = content.strip()

    if not content:
        raise ValueError(
            f"Refusing to write empty file: "
            f"{output_path}"
        )

    content += "\n"

    if output_path.exists():
        old_content = output_path.read_text(
            encoding="utf-8"
        )

        if old_content == content:
            print(
                f"Unchanged: {output_path.name}"
            )
            return False

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Atomic-ish write through temporary file.
    temp_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    temp_path.write_text(
        content,
        encoding="utf-8",
    )

    temp_path.replace(output_path)

    print(f"Saved: {output_path}")

    return True


# ============================================================
# OCR helpers
# ============================================================

def check_ocr_dependencies() -> None:
    """
    Check OCRmyPDF, Tesseract and Vietnamese language support.
    """

    if shutil.which("ocrmypdf") is None:
        raise RuntimeError(
            "ocrmypdf was not found.\n"
            "On macOS install it with:\n\n"
            "    brew install ocrmypdf\n"
        )

    if shutil.which("tesseract") is None:
        raise RuntimeError(
            "tesseract was not found."
        )

    result = subprocess.run(
        [
            "tesseract",
            "--list-langs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    languages = {
        line.strip()
        for line in result.stdout.splitlines()
    }

    if "vie" not in languages:
        raise RuntimeError(
            "Vietnamese Tesseract language pack "
            "('vie') is not installed.\n\n"
            "On macOS run:\n"
            "    brew install tesseract-lang\n\n"
            "Then verify:\n"
            "    tesseract --list-langs"
        )

    print(
        "OCR ready: Vietnamese language "
        "pack detected."
    )


def ocr_pdf_to_text(path: Path) -> str:
    """
    Force OCR a PDF and return OCR sidecar text.

    Why force OCR?
    Government PDFs sometimes have a broken or incorrect
    Unicode text layer. Visually they look correct, while
    PDF text extraction produces garbage.

    --force-ocr ignores that broken text layer and recognizes
    the visible page instead.
    """

    with tempfile.TemporaryDirectory(
        prefix="rag_ocr_"
    ) as temp_dir_string:

        temp_dir = Path(temp_dir_string)

        ocr_pdf_path = (
            temp_dir
            / f"{path.stem}_ocr.pdf"
        )

        sidecar_path = (
            temp_dir
            / f"{path.stem}.txt"
        )

        command = [
            "ocrmypdf",

            # Re-render all pages and OCR visible content.
            "--force-ocr",

            # Vietnamese + occasional English.
            "--language",
            "vie+eng",

            # Correct rotated scanned pages.
            "--rotate-pages",

            # Correct slightly skewed scans.
            "--deskew",

            # We only need OCR; avoid expensive optimization.
            "--optimize",
            "0",

            # No need for PDF/A for temporary file.
            "--output-type",
            "pdf",

            # Sidecar gives OCR text directly.
            "--sidecar",
            str(sidecar_path),

            str(path),
            str(ocr_pdf_path),
        ]

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            error_message = (
                process.stderr.strip()
                or process.stdout.strip()
                or "Unknown OCRmyPDF error"
            )

            raise RuntimeError(
                "OCRmyPDF failed:\n"
                f"{error_message[-3000:]}"
            )

        if not sidecar_path.exists():
            raise RuntimeError(
                "OCR completed but sidecar "
                "text was not created."
            )

        text = sidecar_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return clean_markdown(text)


# ============================================================
# MarkItDown helpers for DOC/DOCX
# ============================================================

def get_markitdown_content(result) -> str:
    """
    Support different MarkItDown result APIs.
    """

    # Common/current API in several MarkItDown releases.
    text_content = getattr(
        result,
        "text_content",
        None,
    )

    if isinstance(text_content, str):
        content = clean_markdown(
            text_content
        )

        if content:
            return content

    # Some releases/interfaces expose `markdown`.
    markdown = getattr(
        result,
        "markdown",
        None,
    )

    if isinstance(markdown, str):
        content = clean_markdown(
            markdown
        )

        if content:
            return content

    if markdown is not None:
        raw_markdown = getattr(
            markdown,
            "raw_markdown",
            None,
        )

        if isinstance(raw_markdown, str):
            content = clean_markdown(
                raw_markdown
            )

            if content:
                return content

    raise ValueError(
        "MarkItDown returned no usable content."
    )


def convert_office_document(
    path: Path,
    converter: MarkItDown,
) -> str:
    """Convert DOC/DOCX using MarkItDown."""

    result = converter.convert(
        str(path)
    )

    return get_markitdown_content(
        result
    )


# ============================================================
# LEGAL
# ============================================================

def convert_legal_docs() -> tuple[int, int]:
    """
    Convert landing/legal to standardized/legal.

    PDF:
        OCRmyPDF -> sidecar -> Markdown

    DOC/DOCX:
        MarkItDown -> Markdown
    """

    print()
    print("=" * 60)
    print("Converting legal documents")
    print("=" * 60)

    LEGAL_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not LEGAL_INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Directory does not exist: "
            f"{LEGAL_INPUT_DIR}"
        )

    legal_files = sorted(
        path
        for path in LEGAL_INPUT_DIR.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_LEGAL_EXTENSIONS
        )
    )

    if not legal_files:
        raise RuntimeError(
            "No legal PDF/DOC/DOCX documents "
            f"found in {LEGAL_INPUT_DIR}"
        )

    # Only needed if at least one PDF exists.
    if any(
        path.suffix.lower() == ".pdf"
        for path in legal_files
    ):
        check_ocr_dependencies()

    converter = MarkItDown()

    successful = 0
    failed = 0

    # Prevent abc.pdf + abc.docx -> abc.md collision.
    output_names = set()

    for path in legal_files:

        output_name = (
            f"{path.stem}.md"
        )

        if output_name in output_names:
            print(
                f"FAILED: {path.name}"
            )
            print(
                "Reason: Duplicate output name "
                f"{output_name}"
            )

            failed += 1
            continue

        output_names.add(
            output_name
        )

        output_path = (
            LEGAL_OUTPUT_DIR
            / output_name
        )

        print()
        print(
            f"Converting: {path.name}"
        )

        try:

            if path.suffix.lower() == ".pdf":

                print(
                    "  Method: OCRmyPDF "
                    "(force OCR, vie+eng)"
                )

                content = (
                    ocr_pdf_to_text(path)
                )

                conversion_method = (
                    "OCRmyPDF force OCR "
                    "(vie+eng)"
                )

            else:

                print(
                    "  Method: MarkItDown"
                )

                content = (
                    convert_office_document(
                        path,
                        converter,
                    )
                )

                conversion_method = (
                    "MarkItDown"
                )

            validate_content(
                content,
                path.name,
            )

            header = (
                f"**Source file:** "
                f"`{relative_project_path(path)}`\n\n"
                f"**Document type:** "
                f"Legal / policy document\n\n"
                f"**Conversion:** "
                f"{conversion_method}\n\n"
                f"---\n\n"
            )

            markdown = (
                header
                + content
            )

            write_if_changed(
                output_path,
                markdown,
            )

            print(
                f"  Content length: "
                f"{len(content):,} characters"
            )

            successful += 1

        except Exception as error:

            failed += 1

            print(
                f"FAILED: {path.name}"
            )

            print(
                f"Reason: {error}"
            )

    print()
    print(
        "Legal conversion summary"
    )
    print("-" * 40)
    print(
        f"Input documents : "
        f"{len(legal_files)}"
    )
    print(
        f"Converted       : "
        f"{successful}"
    )
    print(
        f"Failed          : "
        f"{failed}"
    )

    return successful, failed


# ============================================================
# NEWS
# ============================================================

def validate_news_data(
    data: dict,
    filename: str,
) -> None:

    required_fields = {
        "url",
        "title",
        "date_crawled",
        "content_markdown",
    }

    missing = (
        required_fields
        - data.keys()
    )

    if missing:
        raise ValueError(
            f"Missing fields: "
            f"{sorted(missing)}"
        )

    for field in required_fields:

        value = data[field]

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field} must be a string"
            )

        if not value.strip():
            raise ValueError(
                f"{field} is empty"
            )

    validate_content(
        data[
            "content_markdown"
        ],
        filename,
    )


def one_line(text: str) -> str:
    """Make metadata suitable for a single Markdown line."""
    return " ".join(
        text.split()
    )


def convert_news_articles() -> tuple[int, int]:
    """
    Convert landing/news/*.json
    to standardized/news/*.md.
    """

    print()
    print("=" * 60)
    print("Converting news articles")
    print("=" * 60)

    NEWS_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not NEWS_INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Directory does not exist: "
            f"{NEWS_INPUT_DIR}"
        )

    json_files = sorted(
        NEWS_INPUT_DIR.glob(
            "*.json"
        )
    )

    if not json_files:
        raise RuntimeError(
            "No JSON files found in "
            f"{NEWS_INPUT_DIR}"
        )

    successful = 0
    failed = 0

    for path in json_files:

        print()
        print(
            f"Converting: {path.name}"
        )

        try:

            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(
                data,
                dict,
            ):
                raise ValueError(
                    "JSON root must "
                    "be an object."
                )

            validate_news_data(
                data,
                path.name,
            )

            title = one_line(
                data["title"]
            )

            url = (
                data["url"]
                .strip()
            )

            date_crawled = (
                one_line(
                    data[
                        "date_crawled"
                    ]
                )
            )

            content = clean_markdown(
                data[
                    "content_markdown"
                ]
            )

            header = (
                f"# {title}\n\n"
                f"**Source:** "
                f"{url}\n\n"
                f"**Crawled:** "
                f"{date_crawled}\n\n"
                f"**Landing file:** "
                f"`{relative_project_path(path)}`"
                f"\n\n"
                f"---\n\n"
            )

            markdown = (
                header
                + content
            )

            output_path = (
                NEWS_OUTPUT_DIR
                / f"{path.stem}.md"
            )

            write_if_changed(
                output_path,
                markdown,
            )

            print(
                f"  Content length: "
                f"{len(content):,} characters"
            )

            successful += 1

        except Exception as error:

            failed += 1

            print(
                f"FAILED: {path.name}"
            )

            print(
                f"Reason: {error}"
            )

    print()
    print(
        "News conversion summary"
    )
    print("-" * 40)
    print(
        f"Input JSON files : "
        f"{len(json_files)}"
    )
    print(
        f"Converted        : "
        f"{successful}"
    )
    print(
        f"Failed           : "
        f"{failed}"
    )

    return successful, failed


# ============================================================
# Main
# ============================================================

def convert_all() -> None:
<<<<<<< HEAD
    """Convert all landing data while preserving legal/news branches."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")
=======
    """
    Convert all landing data.

    Important:
    We process both legal and news before failing,
    so one bad legal document does not prevent
    standardized/news from being produced.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    legal_success, legal_failed = (
        convert_legal_docs()
    )

    news_success, news_failed = (
        convert_news_articles()
    )

    print()
    print("=" * 60)
    print("TASK 3 SUMMARY")
    print("=" * 60)

    print(
        f"Legal : "
        f"{legal_success} converted, "
        f"{legal_failed} failed"
    )

    print(
        f"News  : "
        f"{news_success} converted, "
        f"{news_failed} failed"
    )

    print(
        f"Output: {OUTPUT_DIR}"
    )

    total_failed = (
        legal_failed
        + news_failed
    )

    if total_failed:
        raise RuntimeError(
            f"Task 3 completed with "
            f"{total_failed} failure(s)."
        )

    print()
    print(
        "Task 3 completed successfully."
    )
>>>>>>> e8f7b62f5f6e497f594f5f2e165af18695eaabf3


if __name__ == "__main__":
    convert_all()