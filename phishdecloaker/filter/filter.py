import os
import re
import math
import yaml
import json
from datetime import datetime, timedelta

import pika
import tqdm
import certstream
from tld import get_tld
from Levenshtein import distance
from confusables import unconfuse
from cachetools import TTLCache

# Configurations
EXCHANGE_NAME = "urls"
QUEUE_URL = os.getenv("QUEUE_URL", None)
CERTSTREAM_URL = os.getenv("CERTSTREAM_URL", None)
FILTER_THRESHOLD = int(os.getenv("FILTER_THRESHOLD", 0))
SUSPICIOUS_YAML = os.path.join(os.path.dirname(__file__), "suspicious.yml")

# Initialize queue
url_parameters = pika.URLParameters(QUEUE_URL)
connection = pika.BlockingConnection(url_parameters)
channel = connection.channel()
channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="fanout")
baseline_queue = channel.queue_declare(
    queue="baseline", arguments={"x-max-priority": 6}
)
captcha_queue = channel.queue_declare(queue="captcha", arguments={"x-max-priority": 6})
channel.queue_bind(exchange=EXCHANGE_NAME, queue=baseline_queue.method.queue)
channel.queue_bind(exchange=EXCHANGE_NAME, queue=captcha_queue.method.queue)

# Initialize progress bar
pbar = tqdm.tqdm(desc="certificate_update", unit="cert")

# Initialize URL duplicate cheker
cache = TTLCache(maxsize=1000000, ttl=timedelta(hours=12), timer=datetime.now)


def score_domain(domain: str):
    """Score `domain`.

    The highest score, the most probable `domain` is a phishing site.

    Args:
        domain (str): the domain to check.

    Returns:
        int: the score of `domain`.
    """

    def entropy(string):
        """Calculates the Shannon entropy of a string"""
        prob = [
            float(string.count(c)) / len(string) for c in dict.fromkeys(list(string))
        ]
        entropy = -sum([p * math.log(p) / math.log(2.0) for p in prob])
        return entropy

    score = 0

    # Ignore domains with many subdomains
    if domain.count(".") > 3:
        return score

    # Ignore domains with whitelisted keywords
    for word in suspicious["whitelist"]:
        if word in domain:
            return score

    for t in suspicious[
        "tlds"
    ]:  # tld is in suspicious tld list, increase suspiciousness score
        if domain.endswith(t):
            score += 20

    # Removing TLD to catch inner TLD in subdomain (ie. paypal.com.domain.com)
    try:
        res = get_tld(domain, as_object=True, fail_silently=True, fix_protocol=True)
        domain = ".".join([res.subdomain, res.domain])
    except Exception:
        pass

    # Higer entropy is kind of suspicious
    score += int(round(entropy(domain) * 10))

    # Remove lookalike characters using list from http://www.unicode.org/reports/tr39
    domain = unconfuse(domain)

    words_in_domain = re.split("\W+", domain)

    # ie. detect fake .com (ie. *.com-account-management.info)
    if words_in_domain[0] in ["com", "net", "org", "mil", "gov"]:
        score += 10

    # Testing keywords
    for word in suspicious["keywords"]:
        if word in domain:
            score += suspicious["keywords"][word]

    # Testing Levenshtein distance for strong keywords (>= 70 points) (ie. paypol)
    for key in [k for (k, s) in suspicious["keywords"].items() if s >= 70]:
        # Removing too generic keywords (ie. mail.domain.com)
        for word in [w for w in words_in_domain if w not in ["email", "mail", "cloud"]]:
            if distance(str(word), str(key)) == 1:
                score += 70

    # Lots of '-' (ie. www.paypal-datacenter.com-acccount-alert.com)
    if "xn--" not in domain and domain.count("-") >= 4:
        score += domain.count("-") * 3

    # Deeply nested subdomains (ie. www.paypal.com.security.accountupdate.gq)
    score += domain.count(".") * 3

    return score


def callback(message, context):
    if message["message_type"] == "heartbeat":
        return

    if message["message_type"] == "certificate_update":
        all_domains = message["data"]["leaf_cert"]["all_domains"]

        for domain in all_domains:
            if "STH" in domain:
                continue

            domain: str = domain.lstrip().lower()
            for suffix in [
                "*.",
                "www.",
                "cpanel.",
                "cpcalendars.",
                "cpcontacts.",
                "mail.",
                "webdisk.",
                "webmail.",
            ]:
                if domain.startswith(suffix):
                    domain = domain.replace(suffix, "", 1)

            pbar.update(1)

            score = score_domain(domain)
            # If issued from a free CA = more suspicious
            if "Let's Encrypt" == message["data"]["leaf_cert"]["issuer"]["O"]:
                score += 10
            elif "ZeroSSL" == message["data"]["leaf_cert"]["issuer"]["O"]:
                score += 10

            if score >= FILTER_THRESHOLD and domain not in cache:
                priority = min(int(score / 10) - 6, 5)
                cache[domain] = True
                channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key="",
                    body=json.dumps({"domain": domain, "score": score}),
                    properties=pika.BasicProperties(
                        delivery_mode=pika.DeliveryMode.Persistent, priority=priority
                    ),
                )


if __name__ == "__main__":
    with open(SUSPICIOUS_YAML, "r") as f:
        suspicious = yaml.safe_load(f)

    certstream.listen_for_events(callback, url=CERTSTREAM_URL)
