"""
Task 2 — Crawl bài viết/thông báo.

Chủ đề: Du lịch Việt Nam

Mục tiêu:
- Crawl tối thiểu 5 URL công khai.
- Sử dụng Crawl4AI.
- Lưu mỗi bài thành JSON trong data/landing/news/.
- Mỗi JSON có:
    url
    title
    date_crawled
    content_markdown
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode


DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "landing"
    / "news"
)


ARTICLE_URLS = [
    "https://vietnam.travel/node/6",
    "https://www.vietnam.travel/things-to-do/food",
    "https://www.vietnam.travel/things-to-do/vietnam-foodie-guide-region",
    "https://www.vietnam.travel/things-to-do/21-must-try-vietnamese-dishes/",
    "https://vietnam.travel/places-to-go/northern-vietnam",
    "https://vietnam.travel/node/95",
    "https://vietnam.travel/places-to-go/northern-vietnam/ha-giang",
    "https://vietnam.travel/node/1368",
    "https://www.vietnam.travel/things-to-do/10-must-try-hanoi-dishes",
    "https://vietnam.travel/node/21",
    "https://vietnam.travel/node/101",
    "https://vietnam.travel/node/861",
    "https://vietnam.travel/node/1332",
    "https://vietnam.travel/node/1339",
    "https://vietnam.travel/places-to-go/southern-vietnam",
    "https://vietnam.travel/node/470",
    "https://vietnam.travel/places-to-go/southern-vietnam/phu-quoc",
]


def get_markdown(result) -> str:
    """
    Lấy raw Markdown từ Crawl4AI.

    Crawl4AI các version mới trả result.markdown
    dưới dạng MarkdownGenerationResult.
    """

    if not result.markdown:
        return ""

    # Crawl4AI version mới
    if hasattr(result.markdown, "raw_markdown"):
        return result.markdown.raw_markdown or ""

    # Fallback cho version cũ
    return str(result.markdown)


async def crawl_article(url: str) -> dict:
    """Crawl một URL và trả về dữ liệu chuẩn."""

    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        only_text=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
        exclude_all_images=True,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            config=config,
        )

    # Crawl thất bại
    if not result.success:
        raise RuntimeError(
            f"Crawl failed: {result.error_message}"
        )

    metadata = result.metadata or {}

    title = metadata.get("title") or "Unknown"

    content_markdown = get_markdown(result).strip()

    # Tránh lưu trang lỗi hoặc trang gần như rỗng
    if len(content_markdown) < 500:
        raise ValueError(
            f"Content too short: "
            f"{len(content_markdown)} characters"
        )

    return {
        "url": url,
        "title": title.strip(),
        "date_crawled": datetime.now(
            timezone.utc
        ).isoformat(),
        "content_markdown": content_markdown,
    }


def validate_article(article: dict) -> None:
    """Kiểm tra metadata tối thiểu trước khi lưu."""

    required_fields = {
        "url",
        "title",
        "date_crawled",
        "content_markdown",
    }

    missing_fields = required_fields - article.keys()

    if missing_fields:
        raise ValueError(
            f"Missing fields: {missing_fields}"
        )

    if not article["url"]:
        raise ValueError("url is empty")

    if not article["title"]:
        raise ValueError("title is empty")

    if not article["date_crawled"]:
        raise ValueError("date_crawled is empty")

    if len(article["content_markdown"]) < 500:
        raise ValueError("content_markdown is too short")


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Output directory: {DATA_DIR}")
    print(f"Number of URLs: {len(ARTICLE_URLS)}")
    print("-" * 60)

    success_count = 0

    for index, url in enumerate(
        ARTICLE_URLS,
        start=1,
    ):
        print(f"\n[{index}/{len(ARTICLE_URLS)}]")
        print(f"Crawling: {url}")

        try:
            article = await crawl_article(url)

            validate_article(article)

            output = (
                DATA_DIR
                / f"article_{index:02d}.json"
            )

            output.write_text(
                json.dumps(
                    article,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            success_count += 1

            print(f"Title: {article['title']}")
            print(
                "Content length: "
                f"{len(article['content_markdown'])} chars"
            )
            print(f"Saved: {output}")

        except Exception as error:
            print(f"FAILED: {url}")
            print(f"Reason: {error}")

    print("\n" + "=" * 60)
    print(
        f"Successfully crawled: "
        f"{success_count}/{len(ARTICLE_URLS)}"
    )

    if success_count < 5:
        raise RuntimeError(
            "Task 2 requires at least "
            "5 successfully crawled articles."
        )

    print("Task 2 requirement satisfied.")


if __name__ == "__main__":
    asyncio.run(crawl_all())