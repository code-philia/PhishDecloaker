import io
import base64

from flask import Blueprint, Response, request, jsonify
from PIL import Image

from database.client import client
from siamese.model import embedder
from ocr.model import text_encoder

db = Blueprint("database", __name__)


@db.route("/reset", methods=["POST"])
def reset():
    client.reset()
    return Response(status=200)


@db.route("/points")
def get_points_by_type():
    type = request.args.get("type", type=str)
    limit = request.args.get("limit", default=10, type=int)
    offset = request.args.get("offset", default=None, type=str)
    ids, next_offset = client.get_points_by_type(type, limit, offset)
    return jsonify({"ids": ids, "offset": next_offset}), 200


@db.route("/points", methods=["POST"])
def add_points():
    content = request.json
    types = content["types"]
    captcha_regions = content["captcha_regions"]

    vectors = []
    payloads = []
    for type, captcha_region in zip(types, captcha_regions):
        captcha_region = Image.open(
            io.BytesIO(base64.b64decode(captcha_region))
        ).convert("RGB")
        captcha_text_feature = text_encoder(captcha_region)
        vector = embedder(captcha_region, captcha_text_feature)
        payload = {"type": type}
        vectors.append(vector)
        payloads.append(payload)

    client.insert(payloads, vectors)
    return Response(status=202)


@db.route("/points", methods=["DELETE"])
def delete_points():
    content = request.json
    ids = content["ids"]
    client.delete(ids)
    return Response(status=204)
