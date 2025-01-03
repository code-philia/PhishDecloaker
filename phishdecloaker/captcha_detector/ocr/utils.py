import math

import torch
import numpy as np
from PIL import Image
from torchvision.transforms import transforms


class NormalizePAD(object):
    def __init__(self, max_size, PAD_type="right"):
        self.toTensor = transforms.ToTensor()
        self.max_size = max_size
        self.max_width_half = math.floor(max_size[2] / 2)
        self.PAD_type = PAD_type

    def __call__(self, img):
        img = self.toTensor(img)
        img.sub_(0.5).div_(0.5)
        c, h, w = img.size()
        Pad_img = torch.FloatTensor(*self.max_size).fill_(0)
        Pad_img[:, :, :w] = img  # right pad
        if self.max_size[2] != w:  # add border Pad
            Pad_img[:, :, w:] = (
                img[:, :, w - 1].unsqueeze(2).expand(c, h, self.max_size[2] - w)
            )

        return Pad_img


class AlignCollate(object):
    def __init__(
        self, imgH=32, imgW=100, keep_ratio_with_pad=False, adjust_contrast=0.0
    ):
        self.imgH = imgH
        self.imgW = imgW
        self.keep_ratio_with_pad = keep_ratio_with_pad
        self.adjust_contrast = adjust_contrast

    def __call__(self, batch):
        batch = filter(lambda x: x is not None, batch)
        images = batch

        resized_max_w = self.imgW
        input_channel = 1
        transform = NormalizePAD((input_channel, self.imgH, resized_max_w))

        resized_images = []
        for image in images:
            w, h = image.size
            #### augmentation here - change contrast
            if self.adjust_contrast > 0:
                image = np.array(image.convert("L"))
                image = self.adjust_contrast_grey(image, target=self.adjust_contrast)
                image = Image.fromarray(image, "L")

            ratio = w / float(h)
            if math.ceil(self.imgH * ratio) > self.imgW:
                resized_w = self.imgW
            else:
                resized_w = math.ceil(self.imgH * ratio)

            resized_image = image.resize((resized_w, self.imgH), Image.BICUBIC)
            resized_images.append(transform(resized_image))

        image_tensors = torch.cat([t.unsqueeze(0) for t in resized_images], 0)
        return image_tensors

    def contrast_grey(self, img):
        high = np.percentile(img, 90)
        low = np.percentile(img, 10)
        return (high - low) / np.maximum(10, high + low), high, low

    def adjust_contrast_grey(self, img, target=0.4):
        contrast, high, low = self.contrast_grey(img)
        if contrast < target:
            img = img.astype(int)
            ratio = 200.0 / np.maximum(10, high - low)
            img = (img - low + 25) * ratio
            img = np.maximum(
                np.full(img.shape, 0), np.minimum(np.full(img.shape, 255), img)
            ).astype(np.uint8)
        return img


class ListDataset(torch.utils.data.Dataset):
    def __init__(self, image_list):
        self.image_list = image_list
        self.nSamples = len(image_list)

    def __len__(self):
        return self.nSamples

    def __getitem__(self, index):
        img = self.image_list[index]
        return Image.fromarray(img, "L")
