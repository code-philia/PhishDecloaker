import re
import io
import random
import base64
import asyncio
import logging
from PIL import Image
from dataclasses import dataclass

import openai
from openai import OpenAI
from playwright.async_api import Page, Response, ElementHandle, TimeoutError

logger = logging.getLogger('solver')

@dataclass
class Status:
    SUCCESS = "success"           # CAPTCHA solved, all challenges completed
    CONTINUE = "continue"         # CAPTCHA not solved yet, multiple correct solutions required - please solve more

@dataclass
class GetCaptchaResponse:
    request_type: str = None

class Solver:
    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(
            api_key=openai_api_key
        )
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
            elif img.size == (256, 256) or img.size == (512, 512) or img.size == (384, 256) or img.size == (400, 280):
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

        instruction_element = await challenge_frame.locator(".prompt-text").element_handle()
        instruction: str = await instruction_element.inner_text()
        instruction = instruction.lower().replace("click on", "pick").replace("please", "")

        task_grid_element = await challenge_frame.locator(".challenge-container").element_handle()
        task_grid = await task_grid_element.screenshot(type="jpeg")
        task_grid_b64 = base64.b64encode(task_grid).decode('ascii')

        choice_elements: list[ElementHandle] = await challenge_frame.locator(".task").element_handles()
        assert len(choice_elements) == 9   

        logger.info(f"\t[>] instruction: {instruction}")
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are an expert in puzzles. Given a puzzle, your task is to only\
                            give the choices (from 1 to 9) that matches the instruction.\
                            Do not give any explanation. {instruction}."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{task_grid_b64}"
                        }
                    }
                ]
            }],
            max_tokens=128
        )
        
        choices = re.findall(r'\d+', response.choices[0].message.content)
        if not choices:
            logger.info(f"\t[>] empty, randomly select")
            choices = random.sample([1, 2, 3, 4, 5, 6, 7, 8, 9], k=random.randint(3, 9))
        logger.info(f"\t[>] {instruction}: {choices}")

        for choice in choices:
            index = int(choice) - 1
            if 0 <= index <= 8:
                await choice_elements[index].click(delay=200)

    async def solve_image_label_area_select(self):
        challenge_frame = self.page.frame_locator("//iframe[contains(@title, 'hCaptcha challenge')]")
        canvas = challenge_frame.locator("//div[@class='challenge-view']//canvas")
        await canvas.wait_for(state="visible")

        instruction_element = await challenge_frame.locator(".prompt-text").element_handle()
        instruction: str = await instruction_element.inner_text()
        instruction = instruction.lower().replace("click on", "where is").replace("please", "")

        canvas_screenshot = await canvas.screenshot(type="jpeg")
        canvas_b64 = base64.b64encode(canvas_screenshot).decode('ascii')

        logger.info(f"\t[>] instruction: {instruction}")
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are an expert in puzzles. Given a puzzle, your task is to only\
                            give the position (x, y) in Cartesian pixel coordinate system according to instruction, with (0,0) in the upper left corner.\
                            Do not give any explanation. {instruction}."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{canvas_b64}"
                        }
                    }
                ]
            }],
            max_tokens=128
        )
        
        choices: list = re.findall(r'\d+', response.choices[0].message.content)
        if len(choices) != 2:
            logger.info(f"\t[>] bad gpt response: {response.choices[0].message.content}, random override")
            box = await canvas.bounding_box()
            choices = [random.randint(70, box["width"] - 70), random.randint(box["height"] - 50 - 256, box["height"] - 50)]
        logger.info(f"\t[>] {instruction}: {choices}")
        await canvas.click(position={"x": int(choices[0]), "y": int(choices[1])}, delay=200)
    
    async def solve(self):
        challenge_type = await self.challenge_loaded

        # Solve challenge
        try:
            if challenge_type == "image_label_binary":
                await self.solve_image_label_binary()
                await asyncio.sleep(random.uniform(0.1, 0.3))
            elif challenge_type == "image_label_area_select":
                await self.solve_image_label_area_select()
                await self.page.wait_for_timeout(1000)
        except openai.APIConnectionError as e:
            logger.info("\t[!] openai server could not be reached")
            logger.info(e.__cause__)
        except openai.RateLimitError as e:
            logger.info("\t[!] openai server rate limited")
        except openai.APIStatusError as e:
            logger.info(f"\t[!] openai server returned status code {e.status_code}")
            logger.info(e.response.text)
        except Exception as e:
            logger.info(e)

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