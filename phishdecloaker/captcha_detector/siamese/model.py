from __future__ import annotations

import os

import numpy.typing as npt
import torch
from PIL import Image
from torchvision.transforms import transforms


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    TRUNK_PATH = os.path.join(CURRENT_DIR, "trunk.ts")
    EMBEDDER_PATH = os.path.join(CURRENT_DIR, "embedder.ts")


class Embedder:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.trunk = (
            torch.jit.load(Config.TRUNK_PATH, map_location=self.device)
            .to(self.device)
            .eval()
        )
        self.embedder = (
            torch.jit.load(Config.EMBEDDER_PATH, map_location=self.device)
            .to(self.device)
            .eval()
        )
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

    def __call__(
        self, captcha_region: Image, captcha_text_feature: torch.Tensor
    ) -> npt.NDArray:
        """
        PyTorch metric learning model.
        Trunk is a ResNet-50 model, embedder is a feed-forward network.
        Converts CAPTCHA regions into vector embeddings.

        Args:
            captcha_region: PIL image of CAPTCHA region, cropped from webpage screenshot.
            captcha_text_feature: Text feature of CAPTCHA region, generated via OCR models.

        Returns:
            A vector embedding with 512 dimensions.
        """
        with torch.no_grad():
            captcha_image: torch.Tensor = self.transform(captcha_region)
            captcha_image = captcha_image.unsqueeze(0)
            captcha_image = captcha_image.to(self.device)
            captcha_text_feature = captcha_text_feature.to(self.device)
            captcha_feature = self.trunk(captcha_image, captcha_text_feature)
            vector: torch.Tensor = self.embedder(captcha_feature)
            return vector.cpu().squeeze().numpy()


embedder = Embedder()
