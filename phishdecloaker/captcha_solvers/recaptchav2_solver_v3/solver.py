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
from PIL import Image
from playwright.async_api import Page, Response, FrameLocator, Locator, TimeoutError

logger = logging.getLogger('solver')

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
    SUCCESS = "success"           # CAPTCHA solved, all challenges completed
    RELOAD = "reload"             # CAPTCHA not solved yet, please select all matching images error
    CONTINUE = "continue"         # CAPTCHA not solved yet, there are new challenges / please try again error
    UNSEEN = "unseen"             # CAPTCHA not solved yet, new target object detected
    BLOCKED = "blocked"           # CAPTCHA failed, solver is detected/blocked

class Solver:
    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(
            api_key=openai_api_key
        )
        self.sitekey_pattern = re.compile(r'&k=(.*?)&co=')

    def set_page(self, page: Page):
        """Prepare to interact with reCAPTCHAv2 widget on page, use hook to listen to responses.
        """
        self.page = page
        self.r_queue = asyncio.Queue()
        self.img_queue = asyncio.Queue()

    def set_hook(self):
        """Set hooks to start listening for responses.
        """
        self.page.on("response", self.handle_response)

    async def __call__(self, *args, **kwargs):
        """Solve reCAPTCHAv2
        """
        return await self.solve(**kwargs)

    async def get_sitekey(self):
        """Get sitekey of CAPTCHA.
        """
        src = await self.page.get_attribute("//iframe[contains(@title,'reCAPTCHA')]", "src")
        sitekey = self.sitekey_pattern.search(src)
        if sitekey: 
            sitekey = sitekey.group()
            sitekey = sitekey.replace("&k=", "")
            sitekey = sitekey.replace("&co=", "")
        return sitekey

    async def handle_checkbox(self):
        """Click on checkbox in reCAPTCHAv2 widget frame.
        """
        checkbox = self.page.frame_locator("//iframe[contains(@title,'reCAPTCHA')]")
        checkbox = await checkbox.locator("#recaptcha-anchor").element_handle()
        await checkbox.click(timeout=3000)
        logger.info("\t[>] clicked checkbox")

    async def handle_response(self, response: Response):
        """Intercept responses to determine current state of reCAPTCHAv2 challenge.
        """
        if "recaptcha/api2/payload" in response.url:
            img_data = await response.body()
            img_bytes = io.BytesIO(img_data)
            img_size = Image.open(img_bytes).size
            img_b64 = base64.b64encode(img_bytes.getvalue()).decode("ascii")
            self.img_queue.put_nowait(img_b64)
            logger.info(f"\t[>] /payload [image {img_size}]")

        if "recaptcha/api2/reload" in response.url:
            r_data = await response.text()
            r_data = json.loads(r_data.replace(")]}\'\n", ""))
            r = ReloadResponse(next_challenge_type=r_data[5])
            self.r_queue.put_nowait(r)
            logger.info(f"\t[>] /reload (next: {r_data[5]})")

    async def handle_label(self, challenge_frame: FrameLocator):
        """Extract target object from challenge instruction text 
        """
        label_elements: list[Locator] = await challenge_frame.locator("//div[starts-with(normalize-space(@class), 'rc-imageselect-desc')]").all()
        label: str = await label_elements[0].inner_text()
        label = label.split(":")[-1]
        obj = label.split("\n")[1].lower()
        return obj
    
    async def handle_reload(self, challenge_frame: FrameLocator):
        """Click on reload button in reCAPTCHAv2 challenge frame.
        """
        reload_button = await challenge_frame.locator("//button[contains(@id, 'recaptcha-reload-button')]").element_handle()
        await reload_button.click()
        logger.info("\t[>] clicked reload button")

    async def _handle_imageselect_challenge(self, frame: FrameLocator, obj: str):
        """Select all images with X
        """
        async def _get_tiles(frame: FrameLocator):
            tr = await frame.locator(".rc-imageselect-table-33").locator("tr").all()
            full_table = [await x.locator("td").all() for x in tr]
            return [x for xs in full_table for x in xs]

        tiles: list[Locator] = await _get_tiles(frame)
        tile_images = [await tile.screenshot(type="jpeg") for tile in tiles]
        tile_images_b64 = [base64.b64encode(tile_image).decode('ascii') for tile_image in tile_images]
        tile_images_messages = []
        for tile_image_b64 in tile_images_b64:
            tile_images_messages.append({
                "type": "image",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{tile_image_b64}"
                }
            })

        logger.info(f"\t[>] instruction: select all images with {obj}")
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are an expert in objection detection. Given images, your task is to only\
                            give the choices (from 1 to 9) that matches the instruction.\
                            Do not give any explanation. Select all images with {obj}."
                    },
                    *tile_images
                ]
            }],
            max_tokens=128
        )

        choices = re.findall(r'\d+', response.choices[0].message.content)
        if not choices:
            logger.info(f"\t[>] empty, randomly select")
            choices = random.sample([x + 1 for x in range(9)], k=random.randint(2, 4))
        logger.info(f"Answer: {choices}")
        random.shuffle(choices)

        for choice in choices:
            index = int(choice) - 1
            await tiles[index].click(delay=1000)
            logger.info(f"\t[>] clicked {index}")
            self.random_sleep(0.2)

    async def _handle_dynamic_challenge(self, frame: FrameLocator, obj: str):
        """Select all images with X, click verify once there are none left
        """
        img_b64: str = await self.img_queue.get()
        tiles: list[Locator] = await frame.locator(".rc-imageselect-tile").all()
        logger.info(f"\t[>] instruction: select all images with {obj}, click verify once there are none left.")
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are an expert in object detection. Given an image, your task is to only\
                            give the choices (from 1 to 9) that matches the instruction.\
                            Do not give any explanation. Select all images with {obj}."
                    },
                    {
                        "type": "image",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    }
                ]
            }],
            max_tokens=128
        )
        choices = re.findall(r'\d+', response.choices[0].message.content)
        logger.info(f"\t[>] answer: {choices}")
        random.shuffle(choices)
        
        for _ in range(3):
            new_images = []
            new_positions = []

            for choice in choices:
                index = int(choice) - 1

                while True:
                    try:
                        async with self.page.expect_request(
                            lambda request: "recaptcha/api2/replaceimage" in request.url,
                            timeout=3000
                        ) as request_info:
                            
                            await tiles[index].click(delay=1000)
                            logger.info(f"\t[>] clicked {index}")
                            self.random_sleep(0.2)
                            await request_info.value
                    except:
                        continue
                    else:
                        break

                img_b64 = await self.img_queue.get()
                new_images.append({
                    "type": "image",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    }
                })
                new_positions.append(choice)

            response = self.openai_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"You are an expert in object detection. Given image(s), your task is to only\
                                give 1 (YES) or 0 (NO) for each image according to instruction.\
                                Do not give any explanation. Do they contain {obj}?"
                        },
                        *new_images
                    ]
                }],
                max_tokens=128
            )

            choices = []
            new_choices = re.findall(r'\d+', response.choices[0].message.content)
            for choice, new_position in zip(new_choices, new_positions):
                if int(choice) == 1: choices.append(new_position)

            logger.info(f"\t[>] answer: {new_choices}, {choices}")
            if not choices:
                break

    async def _handle_tileset_challenge(self, frame: FrameLocator, obj: str):
        """Select all squares with X
        """
        tiles: list[Locator] = await frame.locator(".rc-imageselect-tile").all()
        img_b64: str = await self.img_queue.get()
        logger.info(f"\t[>] instruction: select all squares with {obj}.")
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are an expert in object detection. Given a 4x4 grid, your task is to only\
                            give the choices (from 1 to 16) that matches the instruction.\
                            Do not give any explanation. Select all tiles with {obj}."
                    },
                    {
                        "type": "image",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    }
                ]
            }],
            max_tokens=128
        )
        choices = re.findall(r'\d+', response.choices[0].message.content)
        if not choices:
            logger.info(f"\t[>] empty, randomly select")
            choices = random.sample([x + 1 for x in range(15)], k=random.randint(3, 8))
        logger.info(f"\t[>] answer: {choices}")
        random.shuffle(choices)

        for choice in choices:
            index = int(choice) - 1
            await tiles[index].click(delay=1000)
            logger.info(f"\t[>] clicked {index}")
            self.random_sleep(0.2)

    def _clear_img_queue(self):
        while not self.img_queue.empty():
            self.img_queue.get_nowait()
            self.img_queue.task_done()

    async def solve(self):
        # Get challenge frame
        challenge_frame = self.page.frame_locator("//iframe[contains(@title,'recaptcha challenge expires in two minutes')]")

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
            obj = CAPTCHA_TO_COCO[obj]
        elif obj in CAPTCHA_TO_CUSTOM:
            obj = CAPTCHA_TO_CUSTOM[obj]
        else:
            await self.handle_reload(challenge_frame)
            return Status.UNSEEN
        
        # Solve challenge depending on its type (detect & click)
        if r.next_challenge_type == "imageselect":
            await self._handle_imageselect_challenge(challenge_frame, obj)
        elif r.next_challenge_type == "dynamic":
            await self._handle_dynamic_challenge(challenge_frame, obj)
        elif r.next_challenge_type == "multicaptcha" or r.next_challenge_type == "tileselect":
            await self._handle_tileset_challenge(challenge_frame, obj)

        # Clear image queue
        self._clear_img_queue()

        # Check challenge status
        logger.info("\t[>] waiting for /userverify (request)")
        try:
            async with self.page.expect_request(
                lambda request: "recaptcha/api2/userverify" in request.url,
                timeout=3000
            ) as request_info:
                verify_button = await challenge_frame.locator("#recaptcha-verify-button").element_handle()
                await verify_button.click()
                logger.info("\t[>] clicked verify button")
                await request_info.value

                async with self.page.expect_response(
                    lambda response: "recaptcha/api2/userverify" in response.url
                ) as response_info:
                    response = await response_info.value
                    uv_data = await response.text()
                    uv_data = json.loads(uv_data.replace(")]}\'\n", ""))
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
            if r.next_challenge_type == "multicaptcha" or r.next_challenge_type == "tileselect":
                logger.info("\t[>] new challenge shown, same type")
                await self.r_queue.put(r)
                return Status.CONTINUE
            else:
                logger.info("\t[>] please select all matching images.")
                await self.handle_reload(challenge_frame)
                return Status.RELOAD
            
    def random_sleep(self, amount):
        time.sleep(amount * (1 + random.uniform(-0.2, 0.2)))