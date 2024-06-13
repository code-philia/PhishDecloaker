import os
import io
import logging
from dataclasses import dataclass

import torch
from PIL import Image
from playwright.async_api import Page, ElementHandle
from torchvision.transforms import transforms

from trajectory import Trajectory
from model import RotModel

logger = logging.getLogger('solver')


@dataclass
class Config:
    WINDOW: str
    IMAGE: str
    SLIDER: str
    SLIDER_LENGTH: int

    VERIFY_URL: str
    VERIFY_SUCCESS_KEYWORD: str


class Solver:
    def __init__(self) -> None:
        self.image_size = 224
        self.device = "cpu"
        model_path = os.path.join(os.path.dirname(__file__), "rotmodel.pth")
        model_weights = torch.load(model_path, map_location=self.device)
        self.model = RotModel()
        self.model.load_state_dict(model_weights)
        self.model.eval()
        self.to_tensor = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

    async def __call__(self, *args, **kwargs):
        return await self.solve(**kwargs)
    
    async def drag_slider(self, page: Page, slider: ElementHandle, pred: float, max_length: int):
        slider_bbox = await slider.bounding_box()
        x = slider_bbox["x"] + slider_bbox["width"] / 2
        y = slider_bbox["y"] + slider_bbox["height"] / 2
        top = slider_bbox["y"] + slider_bbox["height"]
        bottom = slider_bbox["y"]
        await page.mouse.move(x, y, steps=25)
        await page.mouse.down()

        distance = pred * max_length
        traj = Trajectory(x, x + distance, top, bottom)
        for p in traj.generate(steps=100):
            px, py = p
            await page.mouse.move(px, py)

    async def solve(self, page: Page, config: Config) -> bool:
        await page.wait_for_selector(config.WINDOW, state="visible")

        # Capture challenge image.
        background = await page.query_selector(config.IMAGE)
        background = await background.screenshot(type="jpeg")
        image = Image.open(io.BytesIO(background))

        # Resize challenge image, convert to tensor.
        background = image.resize((self.image_size, self.image_size))
        background = self.to_tensor(background)
        background = torch.unsqueeze(background, 0)

        # Pass background image to model to predict rotation angle.
        pred: torch.Tensor = self.model(background)

        if pred < 0:
            pred = 1 - abs(pred.item())
        else:
            pred = pred.item()

        slider = await page.query_selector(config.SLIDER)
        await self.drag_slider(page, slider, pred, config.SLIDER_LENGTH)

        try:
            async with page.expect_response(
                lambda response: config.VERIFY_URL in response.url,
                timeout=5000
            ) as response_info:
                await page.mouse.up()
                response = await response_info.value
                data = await response.text()
                if config.VERIFY_SUCCESS_KEYWORD in data: return True
                else: return False
        except:
            return False