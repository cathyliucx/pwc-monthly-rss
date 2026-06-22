from __future__ import annotations

import hashlib
import html
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import yaml
from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


BASE_URL = "https://paperswithcode.co"

MONTH_NAMES = (
    "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)

DATE_PATTERNS = (
    re.compile(
        rf"\b(?:{MONTH_NAMES})\s+\d{{1,2}},\s+\d{{4}}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b\d{{1,2}}\s+(?:{MONTH_NAMES})\s+\d{{4}}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{4}/\d{2}/\d{2}\b"),
)


@dataclass(frozen=True)
class Paper:
    title: str
    url: str
    topics: tuple[str, ...]
    published: datetime
    description: str


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("config.yaml must contain a YAML mapping.")

    return config


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"

    return urlunparse(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def parse_date(text: str, timezone: ZoneInfo) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)

        if match is None:
            continue

        try:
            value = date_parser.parse(match.group(0), fuzzy=False)
        except (ValueError, OverflowError):
            continue

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone)

        return value.astimezone(timezone)

    return None


def matches_filter(text: str, task: dict) -> bool:
    if task.get("mode", "broad") == "broad":
        return True

    searchable = text.casefold()

    return any(
        str(keyword).casefold() in searchable
        for keyword in task.get("include", [])
    )


def looks_like_paper_link(href: str) -> bool:
    if not href:
        return False

    path = urlparse(urljoin(BASE_URL, href)).path.casefold()

    return any(
        fragment in path
        for fragment in (
            "/paper/",
            "/papers/",
            "/publication/",
            "/publications/",
        )
    )


def looks_like_title(title: str) -> bool:
    if len(title) < 12 or len(title) > 400:
        return False

    rejected = {
        "paper",
        "papers",
        "read more",
        "view paper",
        "code",
        "github",
        "arxiv",
        "project page",
    }

    return (
        title.casefold() not in rejected
        and re.search(r"[A-Za-z]", title) is not None
    )


def find_card(
    anchor: Tag,
    timezone: ZoneInfo,
) -> tuple[Tag, datetime] | None:
    current: Tag | None = anchor

    for _ in range(12):
        parent = current.parent

        if not isinstance(parent, Tag):
            break

        current = parent
        text = normalize_space(current.get_text(" ", strip=True))

        if len(text) > 10_000:
            break

        published = parse_date(text, timezone)

        if published is not None and len(text) >= 30:
            return current, published

    return None


def extract_papers(
    page_html: str,
    task: dict,
    timezone: ZoneInfo,
) -> list[Paper]:
    soup = BeautifulSoup(page_html, "html.parser")
    papers: list[Paper] = []

    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue

        href = normalize_space(str(anchor.get("href", "")))

        if not looks_like_paper_link(href):
            continue

        title = normalize_space(anchor.get_text(" ", strip=True))

        if not looks_like_title(title):
            continue

        card_result = find_card(anchor, timezone)

        if card_result is None:
            continue

        card, published = card_result
        card_text = normalize_space(card.get_text(" ", strip=True))

        if not matches_filter(card_text, task):
            continue

        papers.append(
            Paper(
                title=title,
                url=urljoin(task["url"], href),
                topics=(task["name"],),
                published=published,
                description=card_text[:4_000],
            )
        )

    return papers


def scroll_page(page, rounds: int) -> None:
    for _ in range(rounds):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)


def fetch_all(
    config: dict,
    timezone: ZoneInfo,
) -> list[Paper]:
    browser_config = config.get("browser", {})
    timeout_ms = int(browser_config.get("timeout_ms", 90_000))
    render_wait_ms = int(browser_config.get("render_wait_ms", 5_000))
    scroll_rounds = int(browser_config.get("scroll_rounds", 5))
    headless = bool(browser_config.get("headless", True))

    papers: list[Paper] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)

        context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        for task in config["tasks"]:
            print(f"\nFetching: {task['name']}")
            print(f"URL: {task['url']}")

            try:
                response = page.goto(
                    task["url"],
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )

                if response is None:
                    raise RuntimeError("No HTTP response returned.")

                print(f"HTTP status: {response.status}")

                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")

                page.wait_for_timeout(render_wait_ms)
                scroll_page(page, scroll_rounds)

                rendered_html = page.content()

                if re.search(
                    r"\b(403|forbidden|access denied|captcha)\b",
                    rendered_html,
                    re.IGNORECASE,
                ):
                    print(
                        "Warning: access-control text detected.",
                        file=sys.stderr,
                    )

                extracted = extract_papers(
                    rendered_html,
                    task,
                    timezone,
                )

                print(f"Extracted candidates: {len(extracted)}")
                papers.extend(extracted)

            except PlaywrightTimeoutError as error:
                print(f"Timeout: {error}", file=sys.stderr)

            except Exception as error:
                print(
                    f"Failed to fetch {task['name']}: {error}",
                    file=sys.stderr,
                )

        context.close()
        browser.close()

    return papers


def keep_current_month(
    papers: list[Paper],
    timezone: ZoneInfo,
) -> list[Paper]:
    now = datetime.now(timezone)

    return [
        paper
        for paper in papers
        if paper.published.year == now.year
        and paper.published.month == now.month
    ]


def deduplicate(papers: list[Paper]) -> list[Paper]:
    grouped: dict[str, Paper] = {}

    for paper in papers:
        key = normalize_url(paper.url)

        if key not in grouped:
            grouped[key] = paper
            continue

        existing = grouped[key]

        grouped[key] = Paper(
            title=existing.title,
            url=existing.url,
            topics=tuple(
                sorted(set(existing.topics) | set(paper.topics))
            ),
            published=max(existing.published, paper.published),
            description=(
                existing.description
                if len(existing.description) >= len(paper.description)
                else paper.description
            ),
        )

    return sorted(
        grouped.values(),
        key=lambda item: item.published,
        reverse=True,
    )


def create_guid(paper: Paper) -> str:
    source = (
        f"{normalize_url(paper.url)}|"
        f"{paper.published.date().isoformat()}"
    )

    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def write_feed(
    papers: list[Paper],
    config: dict,
    timezone: ZoneInfo,
) -> None:
    feed_config = config["feed"]
    output = Path(feed_config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)

    homepage = str(feed_config["homepage"])
    max_items = int(feed_config.get("max_items", 500))

    feed = FeedGenerator()
    feed.id(homepage)
    feed.title(str(feed_config["title"]))
    feed.description(str(feed_config["description"]))
    feed.language("en")
    feed.link(href=homepage, rel="alternate")
    feed.updated(datetime.now(timezone))

    for paper in papers[:max_items]:
        entry = feed.add_entry()
        entry.id(create_guid(paper))
        entry.title(paper.title)
        entry.link(href=paper.url)
        entry.published(paper.published)
        entry.updated(paper.published)

        content = (
            "<p><strong>Topics:</strong> "
            f"{html.escape(', '.join(paper.topics))}</p>"
            "<p><strong>Published:</strong> "
            f"{paper.published:%Y-%m-%d}</p>"
            f"<p>{html.escape(paper.description)}</p>"
        )

        entry.content(content, type="html")

    feed.atom_file(str(output), pretty=True)

    print(f"\nWrote {min(len(papers), max_items)} entries to {output}")

    if not papers:
        print(
            "WARNING: zero entries generated. "
            "Run inspect_html.py and inspect the actual HTML.",
            file=sys.stderr,
        )


def main() -> None:
    config = load_config()

    timezone = ZoneInfo(
        str(config["feed"].get("timezone", "Asia/Tokyo"))
    )

    papers = fetch_all(config, timezone)
    papers = keep_current_month(papers, timezone)
    papers = deduplicate(papers)

    print(f"\nCurrent-month unique papers: {len(papers)}")

    write_feed(papers, config, timezone)


if __name__ == "__main__":
    main()
