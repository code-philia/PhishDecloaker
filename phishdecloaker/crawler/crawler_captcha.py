import base64
import io
import os
import socket
import time

import tldextract
from PIL import Image
from playwright.sync_api import (Browser, BrowserContext, CDPSession, Page,
                                 Request)

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
CLOAKING_PAGE_LOWER_BOUND = int(SCREEN_WIDTH * SCREEN_HEIGHT * 0.15)
CLOAKING_PAGE_UPPER_BOUND = int(SCREEN_WIDTH * SCREEN_HEIGHT * 0.65)
KEYWORD_WHITELIST = os.getenv("KEYWORD_WHITELIST", "").split("|")


class Crawler:
    def _crawl(self, browser: Browser, domain: str):
        url = f"https://{domain}"
        captcha_requests = []
        suspects = set()

        def detect_captcha_request(request: Request):
            request_url = request.url.lower()
            print(f"\t[>] {request_url}")
            if "captcha" in request_url:
                if "hcaptcha.com" in request_url:
                    suspects.add("hcaptcha")
                elif "recaptcha" in request_url:
                    suspects.add("recaptchav2")
                captcha_requests.append(request_url)

        context: BrowserContext = browser.new_context(
            java_script_enabled=True, viewport={"width": 1920, "height": 1080}
        )
        page: Page = context.new_page()
        cdp: CDPSession = context.new_cdp_session(page)
        page.on("request", detect_captcha_request)

        try:
            page.goto(url, wait_until="domcontentloaded")
        except:
            pass

        ignore = False
        effective_url = None
        screenshot_b64 = None
        html_code = None
        has_captcha_request = True if captcha_requests else False
        suspect_captcha = None

        if has_captcha_request:
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            suspect_captcha = suspects.pop() if len(suspects) > 0 else None
            effective_url = page.url
            html_code = page.content()
            screenshot_b64: str = cdp.send("Page.captureScreenshot")["data"]
            screenshot_bytes = base64.decodebytes(screenshot_b64.encode("ascii"))
            greyscale = Image.open(io.BytesIO(screenshot_bytes)).convert("L")
            white_count = sum(
                greyscale.point(lambda pix: 1 if pix >= 250 else 0).getdata()
            )
            input_count = len(page.query_selector_all("input"))

            # if input_count > 1:
            #    ignore = True
            if CLOAKING_PAGE_LOWER_BOUND < white_count < CLOAKING_PAGE_UPPER_BOUND:
                ignore = True
            elif any(keyword in html_code.lower() for keyword in KEYWORD_WHITELIST):
                ignore = True

            print(
                f"\t[>] white count: {CLOAKING_PAGE_LOWER_BOUND} < {white_count} < {CLOAKING_PAGE_UPPER_BOUND}"
            )
            print(f"\t[>] input count: {input_count}")

        if ignore:
            return None, None, None, None
        else:
            return effective_url, screenshot_b64, html_code, suspect_captcha

    def crawl(self, message: dict, browser: Browser, domain: str) -> dict:
        ext = tldextract.extract(domain)
        ip = socket.gethostbyname(ext.fqdn)
        start_time = time.process_time()
        effective_url, screenshot, html_code, suspect_captcha = self._crawl(
            browser, domain
        )
        crawl_time = time.process_time() - start_time

        if not (effective_url and screenshot and html_code):
            return {}

        effective_domain = tldextract.extract(effective_url).registered_domain
        message["crawl_mode"] = "CAPTCHA"
        message["ip"] = ip
        message["tld"] = ext.suffix
        message["effective_domains"] = [effective_domain]
        message["crawl_times"] = [crawl_time]
        message["screenshots"] = [screenshot]
        message["html_codes"] = [html_code]
        message["suspect_captcha"] = suspect_captcha
        return message
