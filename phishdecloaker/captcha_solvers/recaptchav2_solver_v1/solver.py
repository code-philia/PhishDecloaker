import asyncio
import base64
import io
import json
import logging
import random
import re
from dataclasses import dataclass

import numpy as np
import utils
from detector import CocoDetector, CustomDetector, YoloDetector
from PIL import Image
from playwright.async_api import FrameLocator, Locator, Page, Response, TimeoutError

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
    def __init__(self):
        self.sitekey_pattern = re.compile(r"&k=(.*?)&co=")
        self.coco_detector = CocoDetector()
        self.custom_detector = CustomDetector()

    def set_page(self, page: Page):
        """Prepare to interact with reCAPTCHAv2 widget on page, use hook to listen to responses."""
        self.page = page
        self.r_queue = asyncio.Queue()
        self.img_queue = asyncio.Queue()

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

    async def handle_response(self, response: Response):
        """Intercept responses to determine current state of reCAPTCHAv2 challenge."""
        if "recaptcha/api2/payload" in response.url:
            img_data = await response.body()
            img_bytes = io.BytesIO(img_data)
            img_size = Image.open(img_bytes).size
            img_b64 = base64.b64encode(img_bytes.getvalue()).decode("ascii")
            self.img_queue.put_nowait(img_b64)
            logger.info(f"\t[>] /payload [image {img_size}]")

        if "recaptcha/api2/reload" in response.url:
            r_data = await response.text()
            r_data = json.loads(r_data.replace(")]}'\n", ""))
            r = ReloadResponse(next_challenge_type=r_data[5])
            self.r_queue.put_nowait(r)
            logger.info(f"\t[>] /reload (next: {r_data[5]})")

    async def handle_label(self, challenge_frame: FrameLocator):
        """Extract target object from challenge instruction text"""
        label_elements: list[Locator] = await challenge_frame.locator(
            "//div[starts-with(normalize-space(@class), 'rc-imageselect-desc')]"
        ).all()
        label: str = await label_elements[0].inner_text()
        label = label.split(":")[-1]
        obj = label.split("\n")[1].lower()
        return obj

    async def handle_reload(self, challenge_frame: FrameLocator):
        """Click on reload button in reCAPTCHAv2 challenge frame."""
        reload_button = await challenge_frame.locator(
            "//button[contains(@id, 'recaptcha-reload-button')]"
        ).element_handle()
        await reload_button.click()
        logger.info("\t[>] clicked reload button")

    async def _handle_imageselect_challenge(
        self, frame: FrameLocator, detector: YoloDetector, obj: str
    ):
        """Select all images with X"""

        async def _get_tiles(frame: FrameLocator):
            tr = await frame.locator(".rc-imageselect-table-33").locator("tr").all()
            full_table = [await x.locator("td").all() for x in tr]
            return [x for xs in full_table for x in xs]

        tiles: list[Locator] = await _get_tiles(frame)
        img_full: np.ndarray = await self.img_queue.get()
        imgs = utils.divide_image(img_full, 3, 3)
        indices = [i for i in range(9)]
        detections = [detector.detect_on_image(img, threshold=0.2) for img in imgs]
        clicks = set(
            [
                i
                for i, detection in zip(indices, detections)
                if obj in [det[0] for det in detection]
            ]
        )

        clicks = list(clicks)
        random.shuffle(clicks)

        for pos in clicks:
            tile = await tiles[pos].element_handle()
            await tile.click(delay=1000)
            logger.info(f"\t[>] clicked {pos}")
            utils.random_sleep(0.2)

    async def _handle_dynamic_challenge(
        self, frame: FrameLocator, detector: YoloDetector, obj: str
    ):
        """Select all images with X, click verify once there are none left"""
        img_full: np.ndarray = await self.img_queue.get()
        imgs = utils.divide_image(img_full, 3, 3)
        indices = [i for i in range(9)]

        while True:
            tiles = await frame.locator(".rc-imageselect-tile").all()
            detections = [detector.detect_on_image(img, threshold=0.2) for img in imgs]
            clicks = set(
                [
                    i
                    for i, detection in zip(indices, detections)
                    if obj in [det[0] for det in detection]
                ]
            )

            clicks = list(clicks)
            random.shuffle(clicks)

            for pos in clicks:
                while True:
                    try:
                        async with self.page.expect_request(
                            lambda request: "recaptcha/api2/replaceimage"
                            in request.url,
                            timeout=3000,
                        ) as request_info:
                            tile = await tiles[pos].element_handle()
                            await tile.click(delay=1000)
                            logger.info(f"\t[>] clicked {pos}")
                            await request_info.value
                    except:
                        continue
                    else:
                        break

                imgs[pos] = await self.img_queue.get()

            if not clicks:
                break

    async def _handle_tileset_challenge(
        self, frame: FrameLocator, detector: YoloDetector, obj: str
    ):
        """Select all squares with X"""
        tiles = await frame.locator(".rc-imageselect-tile").all()
        img: np.ndarray = await self.img_queue.get()
        detections = detector.detect_on_image(img, threshold=0.2)
        detections = [det for det in detections if det[0] == obj]
        clicks = set()

        for detection in detections:
            clicks = clicks.union(detector.get_clicks(detection, 4, 4, img.shape))

        clicks = list(clicks)
        random.shuffle(clicks)

        for pos in clicks:
            tile = await tiles[pos].element_handle()
            await self.cursor.click(tile, wait_for_click=1000)
            logger.info(f"\t[>] clicked {pos}")
            utils.random_sleep(0.2)

    def _clear_img_queue(self):
        while not self.img_queue.empty():
            self.img_queue.get_nowait()
            self.img_queue.task_done()

    async def solve(self):
        # Get challenge frame
        challenge_frame = self.page.frame_locator(
            "//iframe[contains(@title,'recaptcha challenge expires in two minutes')]"
        )

        # Reset state
        r: ReloadResponse = await self.r_queue.get()
        logger.info(f"\t[>] challenge: {r.next_challenge_type}")
        if r.next_challenge_type == "nocaptcha":
            return Status.SUCCESS
        elif r.next_challenge_type == "doscaptcha":
            return Status.BLOCKED

        # Get target object in challenge
        obj = await self.handle_label(challenge_frame)
        logger.info(f"\t[>] target object: {obj}")

        # Get detector depending on target object
        if obj in CAPTCHA_TO_COCO:
            detector = self.coco_detector
            obj = CAPTCHA_TO_COCO[obj]
        elif obj in CAPTCHA_TO_CUSTOM:
            detector = self.custom_detector
            obj = CAPTCHA_TO_CUSTOM[obj]
        else:
            await self.handle_reload(challenge_frame)
            return Status.UNSEEN

        # Solve challenge depending on its type (detect & click)
        if r.next_challenge_type == "imageselect":
            await self._handle_imageselect_challenge(challenge_frame, detector, obj)
        elif r.next_challenge_type == "dynamic":
            await self._handle_dynamic_challenge(challenge_frame, detector, obj)
        elif (
            r.next_challenge_type == "multicaptcha"
            or r.next_challenge_type == "tileselect"
        ):
            await self._handle_tileset_challenge(challenge_frame, detector, obj)

        # Clear image queue
        self._clear_img_queue()

        # Check challenge status
        logger.info("\t[>] waiting for /userverify (request)")
        try:
            async with self.page.expect_request(
                lambda request: "recaptcha/api2/userverify" in request.url, timeout=3000
            ) as request_info:
                verify_button = await challenge_frame.locator(
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
                        logger.info("\t[>] /userverify (success)")
                        return Status.SUCCESS
                    else:
                        r_data = uv_data[7]
                        r = ReloadResponse(next_challenge_type=r_data[5])
                        self.r_queue.put_nowait(r)
                        logger.info("\t[>] new challenge, please try again.")
                        logger.info(f"\t[>] /userverify (fail, next: {r_data[5]})")
                        return Status.CONTINUE

        except TimeoutError:
            logger.info("\t[>] no /userverify (request)")
            if (
                r.next_challenge_type == "multicaptcha"
                or r.next_challenge_type == "tileselect"
            ):
                logger.info("\t[>] new challenge shown, same type")
                await self.r_queue.put(r)
                return Status.CONTINUE
            else:
                logger.info("\t[>] please select all matching images.")
                await self.handle_reload(challenge_frame)
                return Status.RELOAD
