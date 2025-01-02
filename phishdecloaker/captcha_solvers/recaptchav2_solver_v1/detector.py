import os

import darknet
from darknet_images import load_images, image_detection, batch_detection


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    CUSTOM_DETECTOR_DIR = os.path.join(CURRENT_DIR, "detector_custom")
    COCO_DETECTOR_DIR = os.path.join(CURRENT_DIR, "detector_coco")
    CUSTOM_DETECTOR = {
        "cfg": os.path.join(CUSTOM_DETECTOR_DIR, "yolov3.cfg"),
        "data_file": os.path.join(CUSTOM_DETECTOR_DIR, "custom4.data"),
        "weights": os.path.join(CUSTOM_DETECTOR_DIR, "yolov3_final.weights"),
    }
    COCO_DETECTOR = {
        "cfg": os.path.join(COCO_DETECTOR_DIR, "yolov7.cfg"),
        "data_file": os.path.join(COCO_DETECTOR_DIR, "coco.data"),
        "weights": os.path.join(COCO_DETECTOR_DIR, "yolov7.weights"),
    }


class YoloDetector:
    def __init__(self):
        self.classes = None
        self.model = None
        self.class_colors = None
        self.H = None
        self.W = None

    def get_clicks(self, detection, gw, gh, img_shape):
        w, h, c = img_shape
        clicks = set()

        cw = w / gw
        ch = h / gh

        l, t, r, b = detection[2]

        l = (l / self.W) * w
        t = (t / self.H) * h
        r = (r / self.W) * w
        b = (b / self.H) * h

        l, r = (l + 5) / cw, (r - 5) / cw
        t, b = (t + 5) / ch, (b - 5) / ch

        for i in range(gw):
            for j in range(gh):
                if not (i + 1 <= l or i > r or j + 1 <= t or j > b):
                    clicks.add(j * gh + i)
        return clicks

    def get_model(self, cfg, data_file, weights):
        network, class_names, class_colors = darknet.load_network(
            cfg, data_file, weights, batch_size=1
        )

        self.W = darknet.network_width(network)
        self.H = darknet.network_height(network)

        self.class_colors = class_colors

        return network, class_names

    def detect_on_images(self, images, threshold=0.2, mini_batch=3):
        detections = []
        for i in range(0, len(images), mini_batch):
            r = min(i + mini_batch, len(images))
            detections.extend(
                batch_detection(
                    self.model,
                    images[i:r],
                    self.classes,
                    thresh=threshold,
                    batch_size=r - i,
                )
            )

        detections = [
            [(x, y, darknet.bbox2points(z)) for (x, y, z) in detection]
            for detection in detections
        ]

        return detections

    def detect_on_image(self, img, threshold=0.2):
        image = img
        if isinstance(img, str):
            images = load_images(img)
            image = images[0]

        detections = image_detection(image, self.model, self.classes, thresh=threshold)

        detections = [(x, y, darknet.bbox2points(z)) for (x, y, z) in detections]
        return detections


class CustomDetector(YoloDetector):
    def __init__(self) -> None:
        super().__init__()
        darknet.set_gpu(0)
        config = Config.CUSTOM_DETECTOR

        self.model, self.classes = self.get_model(
            config["cfg"], config["data_file"], config["weights"]
        )


class CocoDetector(YoloDetector):
    def __init__(self) -> None:
        super().__init__()
        darknet.set_gpu(0)
        config = Config.COCO_DETECTOR

        self.model, self.classes = self.get_model(
            config["cfg"], config["data_file"], config["weights"]
        )
