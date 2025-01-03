import os
import logging

import requests

# Configurations
CAPTCHA_DETECTOR_URL = os.getenv("CAPTCHA_DETECTOR_URL", None)
    

def check_captcha(screenshot_b64: str):
    """
    Check screenshot for any CAPTCHAs

    Args:
        screenshot_b64: webpage screenshot as base64 encoded string

    Returns:
        detected: if screenshot contains CAPTCHA
        pred_type: CAPTCHA type
        det_time: detection time in seconds
        rec_time: recognition time in seconds
    """
    detected, pred_types, det_time, rec_time = False, None, -1, -1

    try:
        response = requests.post(
            url=f"{CAPTCHA_DETECTOR_URL}/predict", 
            json={"screenshot": screenshot_b64},
            timeout=30
        )
    except Exception as e:
        logging.error(f"\t[>] captcha detector error: {e}")
        return detected, pred_types, det_time, rec_time

    if response.status_code != 200:
        logging.error(f"captcha detector returned status code: {response.status_code}")
        return detected, pred_types, det_time, rec_time

    res_json: dict = response.json()
    if not res_json or "detected" not in res_json:
        logging.error(f"captcha detector returned value: {res_json}")
        return detected, pred_types, det_time, rec_time

    logging.info(f"\t[>] {res_json}")
    
    detected = bool(res_json.get('detected', False))
    pred = res_json.get("results", None)
    pred_types = pred[-1]["type"] if pred else None
    det_time = float(res_json.get("det_time", 0))
    rec_time = float(res_json.get("rec_time", 0))
    return detected, pred_types, det_time, rec_time