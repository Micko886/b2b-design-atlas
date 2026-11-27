#!/usr/bin/env python3
"""V77: Re-capture four homepage featured website screenshots at genuine 2x DPR.

Screenshots are evidence of the real public website at capture time, NOT AI art.
Only successful validated browser images replace the existing authentic captures.
This script captures images, it does not execute Playwright/browser tests.
"""
from __future__ import annotations

import asyncio
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageFilter, ImageOps, ImageStat
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "screenshots"
HOME = SCREENS / "sites"
FEATURED = SCREENS / "featured"
REPORT = SCREENS / "quality-v77" / "report.json"

TARGETS = (
    ("vast", "https://www.vastspace.com/", "vastspace.com"),
    ("figure-robotics", "https://www.figure.ai/", "figure.ai"),
    ("fictiv", "https://www.fictiv.com/", "fictiv.com"),
    ("skydio", "https://www.skydio.com/", "skydio.com"),
)
VIEWPORT = (1440, 920)
DPR = 2
QUALITY = 91
CHALLENGE = re.compile(
    r"just a moment|checking your browser|verify you are human|"
    r"access denied|captcha|robot check|enable javascript", re.I
)
CONSENT_REJECT = re.compile(
    r"^(reject all|reject optional|decline all|only necessary|"
    r"necessary only|essential only|do not accept|accept necessary)$", re.I
)
CONSENT_ACCEPT = re.compile(
    r"^(accept all|allow all|accept cookies|okay|got it|i agree)$", re.I
)


async def dismiss_consent(page):
    """Only click real UI controls; never erase an overlay from a screenshot."""
    for attempt in range(2):
        for pattern in (CONSENT_REJECT, CONSENT_ACCEPT):
            for frame in page.frames:
                try:
                    button = frame.get_by_role("button", name=pattern).first
                    if await button.count() and await button.is_visible(timeout=450):
                        await button.click(timeout=2200)
                        await page.wait_for_timeout(400)
                        return True
                except Exception:
                    pass
        if attempt == 0:
            await page.wait_for_timeout(500)
    return False


def validate_image(im):
    if im.size != (VIEWPORT[0] * DPR, VIEWPORT[1] * DPR):
        raise ValueError("Browser output did not preserve 2x viewport pixels")
    # Prevent blank or monochrome capture from overwriting a verified screenshot.
    sample = im.convert("RGB").resize((96, 64), Image.Resampling.BILINEAR)
    if max(ImageStat.Stat(sample).stddev) < 14:
        raise ValueError("Low-variation, possibly blank image")


def write_success(name, img):
    """Write both full-size detail and lighter Retina card image atomically."""
    full_path = HOME / (name + ".webp")
    card_path = FEATURED / (name + "-800.webp")
    assert full_path.is_file(), "Missing approved original capture"
    FEATURED.mkdir(parents=True, exist_ok=True)
    full_tmp = full_path.with_suffix(".v77.tmp")
    card_tmp = card_path.with_suffix(".v77.tmp")
    try:
        img.save(full_tmp, format="WEBP", quality=QUALITY, method=6)
        # The featured grid has a 1.64:1 viewport. Crop top-aligned so source
        # text/UI stays legible, then downsample from genuine 2880px input.
        card = ImageOps.fit(
            img, (800, 488), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.0)
        )
        card = card.filter(ImageFilter.UnsharpMask(radius=0.7, percent=95, threshold=2))
        card.save(card_tmp, format="WEBP", quality=QUALITY, method=6)
        with Image.open(full_tmp) as verified:
            if verified.size != (2880, 1840):
                raise ValueError("Full-resolution WebP does not retain required pixels")
        with Image.open(card_tmp) as verified:
            if verified.size != (800, 488):
                raise ValueError("Retina card WebP dimensions wrong")
        full_tmp.replace(full_path)
        card_tmp.replace(card_path)
    finally:
        full_tmp.unlink(missing_ok=True)
        card_tmp.unlink(missing_ok=True)
    return {"detail": "2880x1840", "card": "800x488",
            "detail_bytes": full_path.stat().st_size,
            "card_bytes": card_path.stat().st_size}


async def capture(browser, row):
    name, url, host = row
    page = await browser.new_page(
        viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]},
        device_scale_factor=DPR, locale="en-US", color_scheme="light",
    )
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=36000)
        if response is None or response.status >= 400:
            raise ValueError("Source HTTP status is unavailable or non-successful")
        final_host = urlparse(page.url).hostname or ""
        if final_host != host and not final_host.endswith("." + host):
            raise ValueError("Unexpected off-source redirect: " + final_host)
        await page.wait_for_timeout(2700)
        await dismiss_consent(page)
        await page.keyboard.press("Escape")
        await page.mouse.move(1420, 910)
        await page.evaluate("""async () => {
            document.querySelectorAll('img[loading="lazy"]').forEach(x => {
                x.loading = 'eager';
            });
            if (document.fonts && document.fonts.ready) {
                await document.fonts.ready;
            }
        }""")
        await page.wait_for_timeout(1400)
        title = (await page.title())[:150]
        body = (await page.locator("body").inner_text(timeout=4500))[:3200]
        if CHALLENGE.search(title + " " + body[:450]) or len(body.strip()) < 90:
            raise ValueError("Page content invalid, blocked or too sparse")
        # Real browser capture, not model synthesis, interpolation or a visual test.
        png = await page.screenshot(
            type="png", full_page=False, animations="disabled", timeout=20000,
        )
        with Image.open(io.BytesIO(png)) as raw:
            im = raw.convert("RGB")
        validate_image(im)
        result = write_success(name, im)
        print("V77_CAPTURED", name, result, flush=True)
        return {"site": name, "status": "captured", "source": url,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                **result}
    except Exception as exc:
        # A network/consent failure never overwrites the older real screenshot.
        reason = (str(exc) or type(exc).__name__)[:220]
        print("V77_KEPT_ORIGINAL", name, reason, flush=True)
        return {"site": name, "status": "kept-original",
                "source": url, "reason": reason}
    finally:
        await page.close()


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True, channel="chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            # Sequential requests avoid overwhelming the target websites.
            results = []
            for row in TARGETS:
                results.append(await capture(browser, row))
        finally:
            await browser.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "source": "real Chromium browser, 1440x920 CSS viewport, DPR 2",
        "results": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    success = sum(x["status"] == "captured" for x in results)
    print("V77_RESULT", success, "/", len(TARGETS), flush=True)
    if success == 0:
        raise RuntimeError("No source could be captured; originals preserved")


if __name__ == "__main__":
    asyncio.run(main())
