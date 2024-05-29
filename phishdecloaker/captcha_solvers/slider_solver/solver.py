import logging
from dataclasses import dataclass

import cv2
import numpy as np
from playwright.async_api import Page, ElementHandle

from trajectory import Trajectory

logger = logging.getLogger('solver')


@dataclass
class Config:
    OFFSET: int
    
    WINDOW: str
    PUZZLE_PIECE: str
    BACKGROUND: str
    SLIDER: str

    VERIFY_URL: str
    VERIFY_SUCCESS_KEYWORD: str


class Solver:
    async def __call__(self, *args, **kwargs):
        return await self.solve(**kwargs)
    
    async def find_distance(self, puzzle_piece: ElementHandle, background: ElementHandle) -> int:
        """Calculate the distance between puzzle piece and gap.
        """
        def _detect_edges(img: cv2.Mat) -> cv2.Mat:
            """Edge detection algorithm.
            """
            scale = 1
            delta = 0
            ddepth = cv2.CV_16S

            img = cv2.GaussianBlur(img, (3, 3), 0)
            img_grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            grad_x = cv2.Sobel(
                img_grayscale,
                ddepth,
                1,
                0,
                ksize=3,
                scale=scale,
                delta=delta,
                borderType=cv2.BORDER_DEFAULT,
            )
            grad_y = cv2.Sobel(
                img_grayscale,
                ddepth,
                0,
                1,
                ksize=3,
                scale=scale,
                delta=delta,
                borderType=cv2.BORDER_DEFAULT,
            )
            abs_grad_x = cv2.convertScaleAbs(grad_x)
            abs_grad_y = cv2.convertScaleAbs(grad_y)
            grad = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)

            return grad
        
        puzzle_piece = puzzle_piece.screenshot()
        puzzle_piece = np.frombuffer(puzzle_piece, dtype=np.uint8)
        puzzle_piece = cv2.imdecode(puzzle_piece, cv2.IMREAD_COLOR)
        puzzle_piece = _detect_edges(puzzle_piece)

        background = background.screenshot()
        background = np.frombuffer(background, dtype=np.uint8)
        background = cv2.imdecode(background, cv2.IMREAD_COLOR)
        background = _detect_edges(background)

        matches = cv2.matchTemplate(background, puzzle_piece, cv2.TM_CCOEFF_NORMED)
        points = []

        for _ in range(2):
            _, _, _, max_loc = cv2.minMaxLoc(matches)
            points.append(max_loc)

        begin = points[0][0]
        end = points[1][0]

        return abs(end - begin)
    
    async def drag_slider(self, page: Page, slider: ElementHandle, distance: int):
        slider_bbox = await slider.bounding_box()
        x = slider_bbox["x"] + slider_bbox["width"] / 2
        y = slider_bbox["y"] + slider_bbox["height"] / 2
        top = slider_bbox["y"] + slider_bbox["height"]
        bottom = slider_bbox["y"]
        await page.mouse.move(x, y, steps=25)
        await page.mouse.down()

        traj = Trajectory(x, x + distance, top, bottom)
        for p in traj.generate(steps=100):
            px, py = p
            await page.mouse.move(px, py)

        await page.mouse.up()

    async def solve(self, page: Page, config: Config) -> bool:
        page.wait_for_selector(config.WINDOW)
        background = page.locator(config.BACKGROUND)
        slider = await page.query_selector(config.SLIDER)

        pieces: list[ElementHandle] = page.query_selector_all(config.PUZZLE_PIECE)
        puzzle_piece = None
        if len(pieces) > 1:
            for piece in pieces:
                bbox = piece.bounding_box()
                if bbox["width"] == bbox["height"]:
                    puzzle_piece = pieces
                    break
        else:
            puzzle_piece = pieces[-1]

        distance = await self.find_distance(puzzle_piece, background)

        try:
            async with page.expect_response(
                lambda response: response.url.startswith(config.VERIFY_URL),
                timeout=3000
            ) as response_info:
                await self.drag_slider(page, slider, distance)
                response = await response_info.value
                data = await response.text()
                if config.VERIFY_SUCCESS_KEYWORD in data: return True
                else: return False
        except:
            return False