import base64
import io
import socket
import time

import tldextract
import utils
from PIL import Image
from playwright.sync_api import (Browser, BrowserContext, CDPSession, Page,
                                 Request)

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
BLANK_PAGE_UPPER_BOUND = int(SCREEN_WIDTH * SCREEN_HEIGHT * 0.90)


class Crawler:
    def _crawl(self, browser: Browser, domain: str):
        url = f"https://{domain}"
        captcha_requests = []

        def detect_captcha_request(request: Request):
            request_url = request.url
            if "captcha" in request_url.lower():
                captcha_requests.append(request_url)

        context: BrowserContext = browser.new_context(
            java_script_enabled=True,
            user_agent=utils.random_user_agent(),
            viewport={"width": 1920, "height": 1080},
        )

        page: Page = context.new_page()
        page.on("request", detect_captcha_request)
        page.on("dialog", lambda dialog: dialog.dismiss())
        cdp: CDPSession = context.new_cdp_session(page)
        referer = utils.random_referer(domain)

        fails = 0
        retries = 3
        timeout = 10000
        for _ in range(retries):
            try:
                page.goto(
                    url, wait_until="domcontentloaded", timeout=timeout, referer=referer
                )
            except Exception as e:
                print(f"\t[>] page.goto error: {e}")
                page.close()
                page: Page = context.new_page()
                fails += 1
                continue
            break

        if fails >= retries:
            print("\t[>] failed to load page, abort")
            return None, None, None

        effective_url = page.url
        has_captcha_request = True if captcha_requests else False
        if has_captcha_request:
            print("\t[>] captcha detected, abort")
            return None, None, None

        utils.random_mouse_movement(page)
        html_code = page.content()
        screenshot_b64: str = cdp.send("Page.captureScreenshot")["data"]
        screenshot_bytes = base64.decodebytes(screenshot_b64.encode("ascii"))
        greyscale = Image.open(io.BytesIO(screenshot_bytes)).convert("L")
        white_count = sum(greyscale.point(lambda pix: 1 if pix >= 250 else 0).getdata())
        if white_count > BLANK_PAGE_UPPER_BOUND:
            print("\t[>] page seems to be blank, wait for 5s")
            page.wait_for_timeout(5000)
            html_code = page.content()
            screenshot_b64: str = cdp.send("Page.captureScreenshot")["data"]
            screenshot_bytes = base64.decodebytes(screenshot_b64.encode("ascii"))

        return effective_url, screenshot_b64, html_code

    def crawl(self, message: dict, browser: Browser, domain: str) -> dict:
        ext = tldextract.extract(domain)
        ip = socket.gethostbyname(ext.fqdn)
        start_time = time.process_time()
        effective_url, screenshot, html_code = self._crawl(browser, domain)
        crawl_time = time.process_time() - start_time

        if not (effective_url and screenshot and html_code):
            return {}

        effective_domain = tldextract.extract(effective_url).registered_domain
        message["crawl_mode"] = "BASELINE"
        message["ip"] = ip
        message["tld"] = ext.suffix
        message["effective_domains"] = [effective_domain]
        message["crawl_times"] = [crawl_time]
        message["screenshots"] = [screenshot]
        message["html_codes"] = [html_code]
        return message
