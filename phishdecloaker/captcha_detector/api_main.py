import os
import io
import time
import base64

from PIL import Image, ImageDraw, ImageFont
from flask import Blueprint, request, jsonify, Response

from ocr.model import text_encoder
from database.client import client
from siamese.model import embedder
from detector.model import detector


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    FONT_PATH = os.path.join(CURRENT_DIR, "static", "font.ttf")


main = Blueprint("main", __name__)


@main.route("/health", methods=["GET"])
def health():
    return Response(status=200)


@main.route("/predict", methods=["POST"])
def predict():
    start_time = time.process_time()
    content = request.json
    screenshot = content["screenshot"]
    screenshot = Image.open(io.BytesIO(base64.b64decode(screenshot))).convert("RGB")

    bboxes = detector(screenshot)
    results = []
    det_time = time.process_time() - start_time

    print(bboxes)

    for bbox in bboxes:
        captcha_region = screenshot.crop(bbox[:-1])
        captcha_text_feature = text_encoder(captcha_region)
        vector = embedder(captcha_region, captcha_text_feature)
        captcha_type = client.search(vector)

        if captcha_type:
            results.append({"bbox": bbox, "type": captcha_type})

    detected = True if results else False
    rec_time = (time.process_time()  - start_time) - det_time
    return jsonify(
        detected=detected,
        results=results,
        det_time=det_time,
        rec_time=rec_time,
    ), 200