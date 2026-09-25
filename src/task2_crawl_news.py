"""
Task 2 — Crawl bài viết/thông báo.

Hướng dẫn:
    1. Điền tối thiểu 5 URL công khai vào ARTICLE_URLS.
    2. Crawl từng URL bằng Crawl4AI.
    3. Lưu mỗi bài thành một JSON trong data/landing/news/.
    4. Giữ đủ url, title, date_crawled và content_markdown.

Cài browser trước khi chạy:
    python -m playwright install chromium
    
-> Dùng Firecrawl or bất cứ công cụ nào bạn quen    
"""

import asyncio
import json
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

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


async def crawl_article(url: str) -> dict:
    """Crawl one public page and return the required landing-data schema."""
    from datetime import datetime, timezone

    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    run_config = CrawlerRunConfig(
        excluded_tags=["nav", "footer", "header"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter()
        ),
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not result.success:
        message = result.error_message or "Unknown Crawl4AI error"
        raise RuntimeError(f"Crawl failed: {message}")

    # Prefer filtered article content to exclude navigation and page chrome.
    markdown = result.markdown
    content_markdown = (
        getattr(markdown, "fit_markdown", None)
        or getattr(markdown, "raw_markdown", None)
        or str(markdown)
    ).strip()
    if not content_markdown:
        raise ValueError("Crawl succeeded but returned empty Markdown")

    metadata = result.metadata or {}
    return {
        "url": url,
        "title": str(metadata.get("title") or "Untitled article").strip(),
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content_markdown,
    }


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for index, url in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            print(f"Failed: {url} — {error}")


if __name__ == "__main__":
    asyncio.run(crawl_all())
