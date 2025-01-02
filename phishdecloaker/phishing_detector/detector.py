import os
import io
import sys
import time
import base64
import tempfile
import traceback
import logging

import torch
from PIL import Image
from flask import Flask, jsonify, request, Response
from phishintention.phishintention_main import load_config, test

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.info(f"CUDA: {torch.cuda.is_available()}, {torch.cuda.device_count()} devices")

app = Flask(__name__)
BROWSER_HOST = os.getenv("BROWSER_HOST", None)
(
    AWL_MODEL,
    CRP_CLASSIFIER,
    CRP_LOCATOR,
    SIAMESE_MODEL,
    OCR_MODEL,
    SIAMESE_THRE,
    LOGO_FEATS,
    LOGO_FILES,
    DOMAIN_MAP,
) = load_config(device="cuda")


@app.route("/health", methods=["GET"])
def health():
    return Response(status=200)


@app.route("/predict", methods=["POST"])
def predict():
    content = request.json
    domain: str = content["domain"]
    effective_domains: list = content["effective_domains"]
    screenshots: list = content["screenshots"]
    html_codes: list = content["html_codes"]
    verdict = False
    results = []
    url = f"https://{domain}"

    for effective_domain, screenshot, html_code in zip(
        effective_domains, screenshots, html_codes
    ):
        has_crp, pred_category, pred_target, pred_time = None, False, False, -1

        if screenshot:
            start_time = time.process_time()
            screenshot = Image.open(io.BytesIO(base64.b64decode(screenshot))).convert(
                "RGB"
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                screenshot.save(os.path.join(temp_dir, "screenshot.png"), format="png")
                pred_category, pred_target, has_crp = test(
                    url,
                    effective_domain,
                    html_code,
                    temp_dir,
                    AWL_MODEL,
                    CRP_CLASSIFIER,
                    CRP_LOCATOR,
                    SIAMESE_MODEL,
                    OCR_MODEL,
                    SIAMESE_THRE,
                    LOGO_FEATS,
                    LOGO_FILES,
                    DOMAIN_MAP,
                    BROWSER_HOST,
                )
                pred_time = time.process_time() - start_time

        verdict = verdict | pred_category

        results.append(
            {
                "pred_time": pred_time,
                "pred_category": pred_category,
                "pred_target": pred_target,
                "has_crp": has_crp,
            }
        )

    return jsonify({"verdict": verdict, "results": results}), 200


def handle_exception(e: Exception):
    logging.info(traceback.print_exc())
    return jsonify(message=str(e)), 500


app.register_error_handler(Exception, handle_exception)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
