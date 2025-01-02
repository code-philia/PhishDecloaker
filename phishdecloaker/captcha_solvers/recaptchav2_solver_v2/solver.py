import io
import re
import json
import time
import random
import asyncio
import logging
from dataclasses import dataclass

import base64
from openai import OpenAI
from openai.types.audio import Transcription
from PIL import Image
from playwright.async_api import Page, Response, FrameLocator, Locator, TimeoutError

logger = logging.getLogger("solver")

RECAPTCHA_IMAGES = "images"
RECAPTCHA_SQUARES = "squares"

CAPTCHA_TO_CUSTOM = {
    "crosswalks": "crosswalk",
    "mountains or hills": "mountain",
    "chimneys": "chimney",
    "palm trees": "tree",
    "stairs": "stair",
    "tractors": "tractor",
    "taxis": "taxi",
    "boats": "boat",
    "bridges": "bridge",
}

CAPTCHA_TO_COCO = {
    "parking meters": "parking meter",
    "parking meter": "parking meter",
    "traffic lights": "traffic light",
    "bicycles": "bicycle",
    "a fire hydrant": "fire hydrant",
    "buses": "bus",
    "bus": "bus",
    "motorcycles": "motorbike",
    "motorcycle": "motorbike",
    "fire hydrants": "fire hydrant",
    "cars": "car",
    "vehicles": "car",
}

SELECTORS = {
    "widget": 'iframe[src*="api2/anchor"]',
    "checkbox": "#recaptcha-anchor",
    "challenge": 'iframe[src*="api2/bframe"]',
    "is_detected": ".rc-doscaptcha-header-text",
    "is_solved": "//span[contains(@class, 'recaptcha-checkbox-checked')]",
    "is_repeat": "//div[contains(@class, 'rc-imageselect-error-')]",
    "is_type_3": "//div[@class='rc-imageselect-checkbox']",
    "tiles_3x3": ".rc-imageselect-table-33",
    "tiles_4x4": ".rc-imageselect-tile",
    "prompt": "//div[starts-with(normalize-space(@class), 'rc-imageselect-desc')]",
    "verify": "#recaptcha-verify-button",
    "reload": "//div[contains(@class, 'reload-button-holder')]",
}


@dataclass
class ReloadResponse:
    next_challenge_type: str = None


@dataclass
class UserVerifyResponse:
    solved: bool = False


@dataclass
class Status:
    SUCCESS = "success"  # CAPTCHA solved, all challenges completed
    RELOAD = "reload"  # CAPTCHA not solved yet, please select all matching images error
    CONTINUE = "continue"  # CAPTCHA not solved yet, there are new challenges / please try again error
    UNSEEN = "unseen"  # CAPTCHA not solved yet, new target object detected
    BLOCKED = "blocked"  # CAPTCHA failed, solver is detected/blocked


class Solver:
    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.sitekey_pattern = re.compile(r"&k=(.*?)&co=")

    def set_page(self, page: Page):
        """Prepare to interact with reCAPTCHAv2 widget on page, use hook to listen to responses."""
        self.page = page
        self.r_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.challenge_frame = page.frame_locator(
            "//iframe[contains(@title,'recaptcha challenge expires in two minutes')]"
        )

    def set_hook(self):
        """Set hooks to start listening for responses."""
        self.page.on("response", self.handle_response)

    async def __call__(self, *args, **kwargs):
        """Solve reCAPTCHAv2"""
        return await self.solve(**kwargs)

    async def get_sitekey(self):
        """Get sitekey of CAPTCHA."""
        src = await self.page.get_attribute(
            "//iframe[contains(@title,'reCAPTCHA')]", "src"
        )
        sitekey = self.sitekey_pattern.search(src)
        if sitekey:
            sitekey: str = sitekey.group()
            sitekey = sitekey.replace("&k=", "")
            sitekey = sitekey.replace("&co=", "")
        return sitekey

    async def handle_checkbox(self):
        """Click on checkbox in reCAPTCHAv2 widget frame."""
        checkbox = self.page.frame_locator("//iframe[contains(@title,'reCAPTCHA')]")
        checkbox = await checkbox.locator("#recaptcha-anchor").element_handle()
        await checkbox.click(timeout=3000)
        logger.info("\t[>] clicked checkbox")

    async def handle_audio_button(self):
        """Click on audio icon to begin audio challenge in reCAPTCHAv2 challenge frame."""
        audio_button = await self.challenge_frame.locator(
            "//button[contains(@id, 'recaptcha-audio-button')]"
        ).element_handle()
        await audio_button.click()
        logger.info("\t[>] clicked audio icon (audio challenge)")

    async def handle_play_button(self):
        """Click on play button to mimic human listening to audio challenge."""
        play_button: Locator = self.challenge_frame.locator(
            "//button[contains(@aria-labelledby, 'audio-instructions')]"
        )
        await play_button.click()
        logger.info("\t[>] clicked play button")

    async def type_answer(self, answer: str):
        """Type answer of audio challenge into input."""
        input: Locator = self.challenge_frame.locator(
            "//input[contains(@id, 'audio-response')]"
        )
        await input.type(answer)
        logger.info("\t[>] typed answer")

    async def transcribe_audio(self):
        """Transcribe audio challenge."""
        audio_data = await self.audio_queue.get()
        transcription: Transcription = self.openai_client.audio.transcriptions.create(
            model="whisper-1", language="en", file=audio_data
        )
        logger.info(f"\t[>] raw audio transcription: {repr(transcription.text)}")
        pattern = re.compile("[^a-z0-9\s]+")
        text = transcription.text.lower()
        text = pattern.sub("", text)
        text = " ".join(text.split())
        logger.info(f"\t[>] processed transcription: {repr(text)}")
        return text

    async def handle_response(self, response: Response):
        """Intercept responses to determine current state of reCAPTCHAv2 challenge."""
        if "recaptcha/api2/payload" in response.url:
            content_type = await response.header_value("Content-Type")
            if "audio" in content_type:
                audio_data = await response.body()
                audio_data = io.BytesIO(audio_data)
                self.audio_queue.put_nowait(audio_data)
                logging.info("/payload (audio)")

        if "recaptcha/api2/reload" in response.url:
            r_data = await response.text()
            r_data = json.loads(r_data.replace(")]}'\n", ""))
            if r_data[5] in ["audio", "nocaptcha", "doscaptcha"]:
                r = ReloadResponse(next_challenge_type=r_data[5])
                self.r_queue.put_nowait(r)
                logging.info(f"/reload (next: {r_data[5]})")

    async def handle_reload(self):
        """Click on reload button in reCAPTCHAv2 challenge frame."""
        reload_button = await self.challenge_frame.locator(
            "//button[contains(@id, 'recaptcha-reload-button')]"
        ).element_handle()
        await reload_button.click()
        logger.info("\t[>] clicked reload button")

    async def solve(self):
        # Reset state
        r: ReloadResponse = await self.r_queue.get()
        logger.info(f"\t[>] challenge: {r.next_challenge_type}")
        if r.next_challenge_type == "nocaptcha":
            logging.info("\t[>] success w/o challenge")
            return Status.SUCCESS
        elif r.next_challenge_type == "doscaptcha":
            logging.info(
                "\t[>] your computer or network may be sending automated queries"
            )
            return Status.BLOCKED

        # Audio transcription
        answer = await self.transcribe_audio()
        self.random_sleep(5)

        # Type answer
        await self.type_answer(answer)

        # Check challenge status
        logger.info("\t[>] waiting for /userverify (request)")
        try:
            async with self.page.expect_request(
                lambda request: "recaptcha/api2/userverify" in request.url, timeout=3000
            ) as request_info:
                verify_button = await self.challenge_frame.locator(
                    "#recaptcha-verify-button"
                ).element_handle()
                await verify_button.click()
                logger.info("\t[>] clicked verify button")
                await request_info.value

                async with self.page.expect_response(
                    lambda response: "recaptcha/api2/userverify" in response.url
                ) as response_info:
                    response = await response_info.value
                    uv_data = await response.text()
                    uv_data = json.loads(uv_data.replace(")]}'\n", ""))
                    if str(uv_data[0]) == "uvresp" and str(uv_data[3]) == "120":
                        logging.info("\t[>] /userverify (success)")
                        return Status.SUCCESS
                    else:
                        r_data = uv_data[7]
                        r = ReloadResponse(next_challenge_type=r_data[5])
                        self.r_queue.put_nowait(r)
                        logging.info("\t[>] new challenge, please try again.")
                        logging.info(f"\t[>] /userverify (fail, next: {r_data[5]})")
                        return Status.CONTINUE

        except TimeoutError:
            logger.info("\t[>] no /userverify (request)")
            await self.handle_reload()
            return Status.RELOAD

    def random_sleep(self, amount):
        time.sleep(amount * (1 + random.uniform(-0.2, 0.2)))
