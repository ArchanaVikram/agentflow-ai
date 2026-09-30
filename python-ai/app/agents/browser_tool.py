import re

from playwright.async_api import async_playwright

from app.config import settings

URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


async def read_page(url: str, logs: list[str]) -> dict:
    """Open a real browser, visit the page and return what it contains."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.browser_headless)
        try:
            page = await browser.new_page()
            logs.append(f"Opening {url} in a real browser")
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            title = await page.title()
            text = await page.inner_text("body")
            emails = sorted(set(EMAIL_PATTERN.findall(text)))
            logs.append(f"Read page '{title}' and found {len(emails)} email(s)")
            return {
                "url": url,
                "title": title,
                "text_preview": text[:500],
                "emails_found": emails,
            }
        finally:
            await browser.close()