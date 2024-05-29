import os
import logging
import statistics

import requests

# Configurations
PHISHING_DETECTOR_URL = os.getenv("PHISHING_DETECTOR_URL")

def detect(domain: str, effective_domains: list[str], screenshot_b64s: list[str], html_codes: list[str]):
    """
    Check session for phishing

    Returns:
        phish_category: if session webpage contains phishing
        phish_target: target brand of phishing
    """
    response = requests.post(
        url=f"{PHISHING_DETECTOR_URL}/predict", 
        json={
            "domain": domain,
            "effective_domains": effective_domains,
            "html_codes": html_codes,
            "screenshots": screenshot_b64s,
        },
        timeout=300
    )
    
    if response.status_code != 200:
        logging.error(f"\t[>] phishing detector returned status code: {response.status_code}")

    res_json: dict = response.json()
    if not res_json or "verdict" not in res_json.keys():
        logging.error(f"\t[>] phishing detector returned value: {res_json}")
    
    pred_times = [0 for _ in screenshot_b64s]
    pred_targets = [None for _ in screenshot_b64s]
    pred_categories = [False for _ in screenshot_b64s]
    has_crps = [False for _ in screenshot_b64s]
    
    verdict = bool(res_json.get("verdict", False))
    if verdict:
        results: list[dict] = res_json.get("results", [])
        for i, result in enumerate(results):
            pred_categories[i] = bool(result.get("pred_category", False))
            pred_targets[i] = result.get("pred_target", None)
            pred_times[i] = float(result.get("pred_time", 0))
            has_crps[i] = bool(result.get("has_crp", False))

    return pred_categories, pred_targets[-1], any(has_crps), statistics.fmean(pred_times)