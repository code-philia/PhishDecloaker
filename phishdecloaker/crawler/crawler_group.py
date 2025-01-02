import base64
import io
import time
from enum import Flag, auto

import tldextract
import utils
from PIL import Image
from playwright.sync_api import (Browser, BrowserContext, CDPSession, Dialog,
                                 Page)

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
BLANK_PAGE_UPPER_BOUND = int(SCREEN_WIDTH * SCREEN_HEIGHT * 0.90)


class Plugin(Flag):
    NONE = 0
    BASICS = auto()
    ANTI_INTERACTION_CLOAKING = auto()
    ANTI_FINGERPRINT_CLOAKING = auto()
    ANTI_BEHAVIOR_CLOAKING = auto()


class Crawler:
    def __init__(self) -> None:
        self.groups = {
            "group_1": Plugin.NONE,
            "group_2": Plugin.BASICS,
            "group_3": Plugin.BASICS | Plugin.ANTI_INTERACTION_CLOAKING,
            "group_4": Plugin.BASICS | Plugin.ANTI_FINGERPRINT_CLOAKING,
            "group_5": Plugin.BASICS | Plugin.ANTI_BEHAVIOR_CLOAKING,
        }

    def _crawl(self, browser: Browser, domain: str, plugins: Plugin):
        url = f"https://{domain}"
        dialogs = []

        def detect_dialog(dialog: Dialog):
            print(f"\t[>] dialog: {dialog}")
            dialogs.append(dialog)
            dialog.dismiss()

        if Plugin.BASICS in plugins:
            java_script_enabled = True  # [Basics] Enabled JS-rendering
        else:
            java_script_enabled = False

        if Plugin.ANTI_FINGERPRINT_CLOAKING in plugins:
            user_agent = utils.random_user_agent()  # [Fingerprint] Random user agent
        else:
            user_agent = "Googlebot/2.1"

        context: BrowserContext = browser.new_context(
            java_script_enabled=java_script_enabled,
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
        )

        if Plugin.ANTI_FINGERPRINT_CLOAKING in plugins:  # [Fingerprint] Disable cookies
            context.route("**/*", utils.disable_cookies)

        page: Page = context.new_page()
        cdp: CDPSession = context.new_cdp_session(page)

        if Plugin.ANTI_INTERACTION_CLOAKING in plugins:
            context.grant_permissions(
                utils.PERMISSION_LIST
            )  # [Interaction] Handle permission windows
            page.on(
                "dialog", lambda dialog: dialog.dismiss()
            )  # [Interaction] Handle alert/dialog windows
        else:
            context.grant_permissions([])
            page.on("dialog", detect_dialog)

        if Plugin.ANTI_BEHAVIOR_CLOAKING not in plugins:
            page.route("**", utils.ignore_redirects)  # [Behavior] Follow redirects

        if Plugin.ANTI_FINGERPRINT_CLOAKING in plugins:
            referer = utils.random_referer(domain)  # [Fingerprint] Spoof referrer
        else:
            referer = None

        if Plugin.ANTI_BEHAVIOR_CLOAKING in plugins:
            retries = 3  # [Behavior] Retry up to 3 times
            timeout = 15000
        else:
            retries = 1
            timeout = 30000

        fails = 0
        for _ in range(retries):
            try:
                page.goto(url, timeout=timeout, referer=referer)
            except Exception as e:
                print(f"\t[>] page.goto error: {e}")
                fails += 1
                continue
            break

        if fails >= retries:
            print("\t[>] failed to load page, abort")
            return None, None, None

        effective_url = page.url
        has_dialog = True if dialogs else False
        if has_dialog:
            print("\t[>] crawler cannot bypass dialog, abort")
            return None, None, None

        if (
            Plugin.ANTI_INTERACTION_CLOAKING in plugins
        ):  # [Interaction] Randomly move & click mouse
            utils.random_mouse_movement(page)

        html_code = page.content()
        screenshot_b64: str = cdp.send("Page.captureScreenshot")["data"]
        screenshot_bytes = base64.decodebytes(screenshot_b64.encode("ascii"))

        if (
            Plugin.ANTI_BEHAVIOR_CLOAKING in plugins
        ):  # [Behavior] Wait 5s after DOM is loaded
            greyscale = Image.open(io.BytesIO(screenshot_bytes)).convert("L")
            white_count = sum(
                greyscale.point(lambda pix: 1 if pix >= 250 else 0).getdata()
            )
            if white_count > BLANK_PAGE_UPPER_BOUND:
                page.wait_for_timeout(5000)
                html_code = page.content()
                screenshot_b64: str = cdp.send("Page.captureScreenshot")["data"]
                screenshot_bytes = base64.decodebytes(screenshot_b64.encode("ascii"))

        return effective_url, screenshot_b64, html_code

    def crawl(self, message: dict, browser: Browser, domain: str) -> dict:
        effective_domains = [None for _ in self.groups.keys()]
        screenshots = [None for _ in self.groups.keys()]
        html_codes = [None for _ in self.groups.keys()]
        crawl_times = [0 for _ in self.groups.keys()]

        for i, plugins in enumerate(self.groups.values()):
            print(f"\t[>] group {i+1}")

            try:
                start_time = time.process_time()
                effective_url, screenshots[i], html_codes[i] = self._crawl(
                    browser, domain, plugins
                )
                crawl_times[i] = time.process_time() - start_time
                if effective_url:
                    effective_domains[i] = tldextract.extract(
                        effective_url
                    ).registered_domain
            except Exception as e:
                print(f"\t[>] group crawler error: {e}")
                pass

        message["crawl_mode"] = "GROUP"
        message["effective_domains"] = effective_domains
        message["crawl_times"] = crawl_times
        message["screenshots"] = screenshots
        message["html_codes"] = html_codes
        return message
