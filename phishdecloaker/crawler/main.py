import os
import json

import pika
import requests
from playwright.sync_api import sync_playwright, Browser

from crawler_captcha import Crawler as CaptchaCrawler
from crawler_baseline import Crawler as BaselineCrawler
from crawler_group import Crawler as GroupCrawler

# Configurations
CRAWL_MODE = os.getenv("CRAWL_MODE", "").upper()
BROWSER_HOST = os.getenv("BROWSER_HOST", "localhost:3000")
DOMAIN_WHITELIST = os.getenv("DOMAIN_WHITELIST").split("|")
SUBDOMAIN_WHITELIST = os.getenv("SUBDOMAIN_WHITELIST", "").split("|")
KEYWORD_WHITELIST = os.getenv("KEYWORD_WHITELIST", "").split("|")
QUEUE_URL = os.getenv("QUEUE_URL", "amqp://localhost?heartbeat=0")
INPUT_QUEUE_NAME = CRAWL_MODE.lower()
OUTPUT_QUEUE_NAME = "crawled"

# Initialize crawler
if CRAWL_MODE == "BASELINE":
    in_priority, out_priority, crawler, whitelist, timeout = 6, 0, BaselineCrawler(), True, 30000
elif CRAWL_MODE == "CAPTCHA":
    in_priority, out_priority, crawler, whitelist, timeout = 6, 1, CaptchaCrawler(), False, 30000
elif CRAWL_MODE == "GROUP":
    in_priority, out_priority, crawler, whitelist, timeout = 1, 2, GroupCrawler(), False, 150000
else:
    raise NotImplementedError(f"Unknown crawl mode: {CRAWL_MODE}")

# Initialize queue
url_parameters = pika.URLParameters(QUEUE_URL)
connection = pika.BlockingConnection(url_parameters)
channel = connection.channel()
channel.queue_declare(queue=INPUT_QUEUE_NAME, arguments={"x-max-priority": in_priority})
channel.queue_declare(queue=OUTPUT_QUEUE_NAME, arguments={"x-max-priority": 5})
channel.basic_qos(prefetch_count=1)


def callback(ch, method, properties, body: bytes):
    try: message: dict = json.loads(body)
    except: return
    domain: str = message.get("domain", None)
    score: int = message.get("score", 0)
    print(f"[+] {domain}")

    try:
        if whitelist:
            if any([domain.endswith(x) for x in DOMAIN_WHITELIST]): return
            if any([domain.startswith(x) for x in SUBDOMAIN_WHITELIST]): return
            response = requests.head(f"https://{domain}", timeout=3)
            if response.status_code < 200 or response.status_code >= 404: return

        with sync_playwright() as p:
            browser: Browser = p.chromium.connect_over_cdp(f"ws://{BROWSER_HOST}?stealth&timeout={timeout}")
            message = crawler.crawl(message, browser, domain)
            if not message: return
            message["score"] = score
            channel.basic_publish(
                exchange='',
                routing_key=OUTPUT_QUEUE_NAME,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent, priority=out_priority)
            )

    except Exception as e:
        print(f"\t[>] callback error: {e}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    print(f"[+] whitelisted HTML keywords: {KEYWORD_WHITELIST}")
    print(f"[+] whitelisted subdomains: {SUBDOMAIN_WHITELIST}")
    print(f"[+] whitelisted domains: {DOMAIN_WHITELIST}")
    channel.basic_consume(queue=INPUT_QUEUE_NAME, on_message_callback=callback)
    channel.start_consuming()