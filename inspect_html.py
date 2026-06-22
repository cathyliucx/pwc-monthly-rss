from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect one rendered Papers with Code task page."
    )
    parser.add_argument(
        "--task",
        default="Agents",
        help="Task name from config.yaml.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    return value.casefold().replace(" ", "-").replace("/", "-")


def scroll_page(page, rounds: int) -> None:
    for _ in range(rounds):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)


def main() -> None:
    config = load_config()
    args = parse_args()

    task = next(
        (
            item
            for item in config["tasks"]
            if item["name"].casefold() == args.task.casefold()
        ),
        None,
    )

    if task is None:
        available = ", ".join(item["name"] for item in config["tasks"])
        raise SystemExit(
            f"Unknown task: {args.task}. Available tasks: {available}"
        )

    browser_config = config.get("browser", {})
    timeout_ms = int(browser_config.get("timeout_ms", 90_000))
    render_wait_ms = int(browser_config.get("render_wait_ms", 5_000))
    scroll_rounds = int(browser_config.get("scroll_rounds", 5))
    headless = bool(browser_config.get("headless", True))

    debug_dir = Path("debug")
    debug_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(task["name"])
    html_path = debug_dir / f"{slug}.html"
    screenshot_path = debug_dir / f"{slug}.png"

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

        response = page.goto(
            task["url"],
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )

        page.wait_for_timeout(render_wait_ms)
        scroll_page(page, scroll_rounds)

        rendered_html = page.content()
        html_path.write_text(rendered_html, encoding="utf-8")

        page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

        status = response.status if response is not None else None

        print(f"Task: {task['name']}")
        print(f"HTTP status: {status}")
        print(f"Final URL: {page.url}")
        print(f"Page title: {page.title()}")
        print(f"HTML characters: {len(rendered_html):,}")
        print(f"All links: {page.locator('a').count()}")
        print(
            "Paper-like links: "
            f"{page.locator('a[href*=\"paper\"]').count()}"
        )
        print(f"HTML saved to: {html_path}")
        print(f"Screenshot saved to: {screenshot_path}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
