import re
import io
import random
import asyncio
import logging
from PIL import Image
from dataclasses import dataclass

from playwright.async_api import Page, Response, ElementHandle, TimeoutError

from ofa_vqa import OfaVqa

logger = logging.getLogger('solver')

@dataclass
class Status:
    SUCCESS = "success"           # CAPTCHA solved, all challenges completed
    CONTINUE = "continue"         # CAPTCHA not solved yet, multiple correct solutions required - please solve more

@dataclass
class GetCaptchaResponse:
    request_type: str = None

class Solver:
    def __init__(self):
        self.vqa = OfaVqa()
        self.sitekey_pattern = re.compile(r'&sitekey=(.*?)&theme=')

    def set_page(self, page: Page):
        """Prepare to interact with hCaptcha widget on page.
        """
        self.page = page
        self.challenge_loaded = asyncio.Future()
        self.challenge_type = None
        self.challenge_tile_images = []
        self.challenge_area_images = []

    def set_hook(self):
        """Set hooks to start listening for responses.
        """
        self.page.on("response", self.handle_response)

    async def __call__(self, *args, **kwargs):
        """Solve hCaptcha
        """
        return await self.solve(**kwargs)
    
    async def get_sitekey(self):
        """Get sitekey of CAPTCHA.
        """
        src = await self.page.get_attribute("//iframe[contains(@title,'Widget containing checkbox for hCaptcha security challenge')]", "src")
        sitekey = self.sitekey_pattern.search(src)
        if sitekey:
            sitekey: str = sitekey.group()
            sitekey = sitekey.replace("&sitekey=", "")
            sitekey = sitekey.replace("&theme=", "")
        return sitekey
    
    async def handle_response(self, response: Response):
        if response.url.startswith("https://imgs"):
            img_data = await response.body()
            img = Image.open(io.BytesIO(img_data))
            logger.info(f"\t[>] /payload [image {img.size}]")
            if img.size == (128, 128) or img.size == (144, 144):
                self.challenge_tile_images.append(img)
            elif img.size == (256, 256) or img.size == (512, 512) or img.size == (384, 256):
                self.challenge_area_images.append(img)

            if not self.challenge_loaded.done() and len(self.challenge_tile_images) >= 9:
                self.challenge_loaded.set_result("image_label_binary")
            elif not self.challenge_loaded.done() and len(self.challenge_area_images) == 1:
                self.challenge_loaded.set_result("image_label_area_select")

    async def handle_checkbox(self):
        """Click on checkbox in hCaptcha widget frame.
        """
        checkbox = self.page.frame_locator("//iframe[contains(@title,'Widget containing checkbox for hCaptcha security challenge')]")
        checkbox = await checkbox.locator("#checkbox").element_handle()
        await checkbox.click(timeout=3000)
        logger.info("\t[>] clicked checkbox")

    async def handle_refresh(self):
        """Get a new challenge.
        """
        challenge_frame = self.page.frame_locator("//iframe[contains(@title, 'hCaptcha challenge')]")
        skip_button = await challenge_frame.locator(".refresh").element_handle()
        await skip_button.click()
        logger.info("\t[>] clicked refresh")

    async def solve_image_label_binary(self):
        challenge_frame = self.page.frame_locator("//iframe[contains(@title, 'hCaptcha challenge')]")
        choice_elements: list[ElementHandle] = await challenge_frame.locator(".task").element_handles()
        assert len(choice_elements) == 9   

        async def _get_images() -> list[Image.Image]:
            images = []
            for choice in choice_elements:
                image_bytes = choice.screenshot()
                images.append(Image.open(io.BytesIO(image_bytes)))
            return images
        
        async def _get_instruction() -> str:
            instruction_element = await challenge_frame.locator(".prompt-text").element_handle()
            instruction: str = await instruction_element.inner_text()
            logger.info(f"\t[>] instruction: {instruction}")
            instruction = instruction.lower().split("click on ")[-1]
            return f"Is this {instruction}?"

        instruction  = await _get_instruction()
        images = await _get_images()

        results = []
        for i, image in enumerate(images):
            res = self.vqa.answer_question(image, instruction)
            logger.info(f"\t[>] {i}: {res}")
            results.append(res)

        choices = [i for i in range(len(choice_elements)) if str(results[i]).startswith("yes")]
        if not choices:
            logger.info(f"\t[>] empty, randomly select")
            choices = random.sample([1, 2, 3, 4, 5, 6, 7, 8, 9], k=random.randint(3, 9))
        logger.info(f"\t[>] answer: {choices}")

        for choice in choices:
            index = int(choice) - 1
            if 0 <= index <= 8:
                await choice_elements[index].click(delay=200)
    
    async def solve(self):
        challenge_type = await self.challenge_loaded

        # Solve challenge
        if challenge_type == "image_label_binary":
            await self.solve_image_label_binary()
            await asyncio.sleep(random.uniform(0.1, 0.3))
        else:
            self.challenge_loaded = asyncio.Future()
            self.challenge_type = None
            self.challenge_tile_images = []
            self.challenge_area_images = []
            await self.handle_refresh()
            return Status.CONTINUE

        # Check challenge status
        logger.info("\t[>] waiting for /checkcaptcha")
        challenge_frame = self.page.frame_locator("//iframe[contains(@title, 'hCaptcha challenge')]")
        verify_button = challenge_frame.locator("//div[@class='button-submit button']")
        try:
            async with self.page.expect_response(lambda response: "/checkcaptcha" in response.url, timeout=3000) as response_info:

                # Click on verify button
                button_text = await verify_button.get_attribute("title")
                await verify_button.click(force=True, delay=200)
                logger.info(f"\t[>] clicked button: {button_text}")

                response = await response_info.value
                data: dict = await response.json()
                if data.get("pass", False):
                    return Status.SUCCESS
                else:
                    self.challenge_loaded = asyncio.Future()
                    self.challenge_type = None
                    self.challenge_tile_images = []
                    self.challenge_area_images = []
                    return Status.CONTINUE
                
        except TimeoutError:
            logger.info("\t[>] no /checkcaptcha, new challenge shown, same type")
            return Status.CONTINUE