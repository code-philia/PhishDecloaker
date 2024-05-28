from __future__ import annotations
import os

import easyocr
import torch
import torch.nn as nn
import numpy as np
from PIL import Image
from torch.utils.data import DataLoader
from easyocr.utils import reformat_input, get_image_list

from .utils import AlignCollate, ListDataset


class Config:
    CURRENT_DIR = os.path.dirname(__file__)


class TextEncoder(easyocr.Reader):
    def __init__(
        self,
        lang_list,
        gpu=True,
        model_storage_directory=None,
        user_network_directory=None,
        detect_network="craft",
        recog_network="standard",
        download_enabled=False,
        detector=True,
        recognizer=True,
        verbose=False,
        quantize=True,
        cudnn_benchmark=False,
    ):
        super().__init__(
            lang_list,
            gpu,
            model_storage_directory,
            user_network_directory,
            detect_network,
            recog_network,
            download_enabled,
            detector,
            recognizer,
            verbose,
            quantize,
            cudnn_benchmark,
        )
        self.detector_params = {
            "min_size": 20,
            "text_threshold": 0.7,
            "low_text": 0.4,
            "link_threshold": 0.4,
            "canvas_size": 2560,
            "mag_ratio": 1.0,
            "slope_ths": 0.1,
            "ycenter_ths": 0.5,
            "height_ths": 0.5,
            "width_ths": 0.5,
            "add_margin": 0.1,
            "reformat": False,
            "threshold": 0.2,
            "bbox_min_score": 0.2,
            "bbox_min_size": 3,
            "max_candidates": 0,
        }
        self.features = 512
        self.imgH = 64

    def __call__(self, image: Image) -> torch.Tensor:
        """
        Extract text features from a given input image.

        Args:
            image: PIL Image.

        Returns:
            text features of shape (1, 512).
        """
        image = np.array(image)
        img, img_cv_grey = reformat_input(image)

        horizontal_list, free_list = self.detect(img, **self.detector_params)
        horizontal_list, free_list = horizontal_list[0], free_list[0]

        if (horizontal_list == None) and (free_list == None):
            y_max, x_max = img_cv_grey.shape
            horizontal_list = [[0, x_max, 0, y_max]]
            free_list = []

        visual_features_list = []
        contextual_features_list = []
        for bbox in horizontal_list:
            h_list = [bbox]
            f_list = []
            image_list, max_width = get_image_list(
                h_list, f_list, img_cv_grey, model_height=self.imgH
            )
            visual_features, contextual_features = self.get_feature(
                self.imgH,
                int(max_width),
                image_list,
            )
            visual_features_list += visual_features
            contextual_features_list += contextual_features

        for bbox in free_list:
            h_list = []
            f_list = [bbox]
            image_list, max_width = get_image_list(
                h_list, f_list, img_cv_grey, model_height=self.imgH
            )
            visual_features, contextual_features = self.get_feature(
                self.imgH,
                int(max_width),
                image_list,
            )
            visual_features_list += visual_features
            contextual_features_list += contextual_features

        if len(visual_features_list) == 0:
            visual_features_list.append(torch.zeros(1, 256, 1))

        if len(contextual_features_list) == 0:
            contextual_features_list.append(torch.zeros(1, 256, 1))

        image_visual_feature = torch.cat(visual_features_list, dim=2)
        image_contextual_feature = torch.cat(contextual_features_list, dim=2)

        assert image_visual_feature.size(2) == image_contextual_feature.size(2)
        pool = nn.AvgPool1d(kernel_size=image_visual_feature.size(2), stride=1)
        image_visual_feature = pool(image_visual_feature)
        image_contextual_feature = pool(image_contextual_feature)

        text_features = torch.cat(
            (image_visual_feature, image_contextual_feature), dim=1
        ).squeeze(2)

        assert self.features == text_features.size(1)
        return text_features

    def get_feature(
        self, imgH: int, imgW: int, image_list: list
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """
        Extract visual and contextual features from each detected text bounding box.

        Args:
            imgH: bounding box maximum height.
            imgW: bounding box maximum width.
            image_list: list of detected text bounding box images.

        Returns:
            list of visual and contextual features for each bounding box.
        """
        img_list = [item[1] for item in image_list]
        AlignCollate_normal = AlignCollate(
            imgH=imgH, imgW=imgW, keep_ratio_with_pad=True
        )
        test_data = ListDataset(img_list)
        test_loader = DataLoader(
            test_data,
            shuffle=False,
            collate_fn=AlignCollate_normal,
            pin_memory=True,
        )

        visual_features, contextual_features = self.recognizer_predict(test_loader)

        return visual_features, contextual_features

    def recognizer_predict(
        self, test_loader: DataLoader
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """
        Recognizer feature extraction pipeline.

        Args:
            test_loader: Detected bounding box images dataloader.

        Returns:
            list of visual and contextual features for each bounding box.
        """
        self.recognizer.eval()
        visual_features = []
        contextual_features = []
        with torch.no_grad():
            for image_tensors in test_loader:
                image = image_tensors.to(self.device)

                """Feature extraction stage"""
                visual_feature = self.recognizer.module.FeatureExtraction(image)
                visual_feature = self.recognizer.module.AdaptiveAvgPool(
                    visual_feature.permute(0, 3, 1, 2)
                )
                visual_feature = visual_feature.squeeze(3)

                """ Sequence modeling stage """
                contextual_feature = self.recognizer.module.SequenceModeling(visual_feature)

                visual_feature = visual_feature.permute(0, 2, 1)
                visual_features.append(visual_feature)
                contextual_feature = contextual_feature.permute(0, 2, 1)
                contextual_features.append(contextual_feature)

        return visual_features, contextual_features
    
text_encoder = TextEncoder(
    ["ch_sim", "en"], gpu=True, model_storage_directory=Config.CURRENT_DIR
)