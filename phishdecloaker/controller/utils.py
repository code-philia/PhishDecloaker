import logging
import os

import requests

VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", None)
POLLER_URL = os.getenv("POLLER_URL", None)


def create_poll(crawl_mode: str, sample_id: str):
    """
    Signal telegram bot to create a poll(s) for newly detected phishing websites and unsolvable CAPTCHAs.
    """
    payload = {"crawl_mode": crawl_mode, "sample_id": sample_id}
    response = requests.post(f"{POLLER_URL}/poll", json=payload, timeout=30)

    if response.status_code != 200:
        logging.error(f"Telegram bot returned status code: {response.status_code}")


def submit_virustotal(domain: str):
    """
    Submit url to VirusTotal

    Args:
        domain: domain

    Returns:
        analysis_id: id to query virustotal for analysis report
    """
    url = f"https://{domain}"
    analysis_id = None
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "x-apikey": VIRUSTOTAL_API_KEY,
    }
    payload = {"url": url}
    url = "https://www.virustotal.com/api/v3/urls"
    response = requests.post(url, data=payload, headers=headers)
    if response.ok:
        response = response.json()
        analysis_id: str = response["data"]["id"]
    else:
        logging.error(f"\t[>] virustotal error {response.status_code}: {response.text}")

    return analysis_id
