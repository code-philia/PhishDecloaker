import asyncio
import json
import logging
import os
import re
import sys
import time

import aiormq
from aiormq.abc import DeliveredMessage
from playwright.async_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Page,
    async_playwright,
)
from solver import Config, Solver

# Configurations
BROWSER_HOST = os.getenv("BROWSER_HOST", None)
QUEUE_URL = os.getenv("QUEUE_URL", None)
INPUT_QUEUE_NAME = "rotation_solver"
OUTPUT_QUEUE_NAME = "crawled"

# Initialize logging
logger = logging.getLogger("solver")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

# Initialize solver
rotation_solver = Solver()

# Initialize queue channel
channel = None


# Initialize queue
async def main():
    global channel
    connection = await aiormq.connect(QUEUE_URL)
    channel = await connection.channel()
    in_queue = await channel.queue_declare(queue=INPUT_QUEUE_NAME)
    await channel.queue_declare(
        queue=OUTPUT_QUEUE_NAME, arguments={"x-max-priority": 5}
    )
    await channel.basic_qos(prefetch_count=1)
    await channel.basic_consume(in_queue.queue, callback)


async def callback(in_message: DeliveredMessage):
    message: dict = json.loads(in_message.body)
    url = message.get("url", None)
    captcha_type = message.get("captcha_type", None)
    screenshots = message.get("screenshots", [])
    html_codes = message.get("html_codes", [])
    logger.info(f"[+] {url}, {captcha_type}")

    start_time = time.process_time()
    solved, sitekey, screenshot, html_code, sol_time = (
        False,
        None,
        screenshots[-1],
        html_codes[-1],
        0,
    )

    async with async_playwright() as p:
        browser: Browser = await p.chromium.connect_over_cdp(
            f"ws://{BROWSER_HOST}?stealth&timeout=1800000"
        )
        context: BrowserContext = await browser.new_context(
            java_script_enabled=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.3",
            viewport={"width": 1920, "height": 1080},
        )
        page: Page = await context.new_page()
        cdp: CDPSession = await context.new_cdp_session(page)

        try:
            await page.goto(url, wait_until="domcontentloaded")
        except:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass

        try:
            config = None
            if captcha_type == "baidu_slide_rotate":
                config = Config(
                    WINDOW=".rv-root",
                    IMAGE=".rv-image",
                    SLIDER=".rv-slider",
                    SLIDER_LENGTH=238,
                    VERIFY_URL="/cap/style",
                    VERIFY_SUCCESS_KEYWORD='"msg": "Success"',
                )
            solved = await solve_rotation(rotation_solver, page, config)

        except Exception as e:
            if (
                str(e)
                == "Execution context was destroyed, most likely because of a navigation"
            ):
                solved = True
            else:
                logger.info(f"\t[>] rotation solver error: {e}")

        if solved:
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            try:
                cdp_response: dict = await cdp.send("Page.captureScreenshot")
                screenshot = cdp_response["data"]
                html_code = await page.content()
            except Exception as e:
                logger.info(f"\t[>] post-solve error: {e}")

        await cdp.detach()
        await page.close()
        await context.close()
        await browser.close()

    sol_time = time.process_time() - start_time
    message["captcha_solved"] = solved
    message["captcha_sitekey"] = sitekey
    message["captcha_sol_time"] = sol_time
    message["screenshots"] = [screenshot]
    message["html_codes"] = [html_code]
    message["crawl_mode"] = "CAPTCHA_SOLVED"

    try:
        await channel.basic_publish(
            body=json.dumps(message).encode(),
            routing_key=OUTPUT_QUEUE_NAME,
            properties=aiormq.spec.Basic.Properties(delivery_mode=1, priority=2),
        )
        await in_message.channel.basic_ack(in_message.delivery.delivery_tag)
        logger.info("\t[>] done")
    except Exception as e:
        logger.info(f"\t[>] publish to queue error: {e}")


async def solve_rotation(solver: Solver, page: Page, config: Config) -> bool:
    solved = await solver(page=page, config=config)

    if solved:
        logger.info("\t[>] success")
        await submit_captcha(page)
    else:
        logger.info("\t[>] failed")

    return solved


# Some CAPTCHA cloaking pages may include a button that must be clicked to submit the CAPTCHA
async def submit_captcha(page: Page):
    buttons = await page.get_by_text(
        re.compile("(submit)|(verify)|(continue)|(unblock)|(next)", re.IGNORECASE)
    ).all()

    for button in buttons:
        try:
            await button.click(force=True)
        except:
            continue


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_forever()
