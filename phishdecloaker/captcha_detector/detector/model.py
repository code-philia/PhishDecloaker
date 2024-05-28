from __future__ import annotations
import os

import mmcv
import torch
import numpy as np
import numpy.typing as npt
from PIL import Image
from mmdet.apis import init_detector, inference_detector


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    CONFIG_PATH = os.path.join(CURRENT_DIR, "config.py")
    DETECTOR_PATH = os.path.join(CURRENT_DIR, "oln_detector.pth")


class Detector:
    def __init__(self) -> None:
        self.device = "cuda"
        self.detector = init_detector(
            Config.CONFIG_PATH, Config.DETECTOR_PATH, device=self.device
        )
        self.threshold = 0.6

    def __call__(self, screenshot: Image) -> list:
        """
        MMDetection trained Object Localization Network (OLN) model.
        Detects CAPTCHA regions in an image.

        Args:
            screenshot: PIL image of webpage screenshot.

        Returns:
            A list of bounding boxes (x_min, y_min, x_max, y_max).
        """
        screenshot = np.array(screenshot, dtype=np.float32)
        result = inference_detector(self.detector, screenshot)
        bboxes = [x.tolist() for x in result[0] if x[-1] >= self.threshold]
        return [bboxes[0]] if bboxes else []

detector = Detector()