import os
import sys
import json
import logging
import traceback
from datetime import datetime
from bson.objectid import ObjectId

import pika

import utils
from connector import phishdecloaker
from connector import phishintention
from connector.database import Client, BaselineSample, CaptchaSample

# Configurations
DATABASE_URL = os.getenv("DATABASE_URL", None)
QUEUE_URL = os.getenv("QUEUE_URL", None)
QUEUE_NAME = "crawled"
CAPTCHA_SOLVER_QUEUE_NAME = "captcha_solver"
GROUP_CRAWLER_QUEUE_NAME = "group"

# Initialize queue
url_parameters = pika.URLParameters(QUEUE_URL)
connection = pika.BlockingConnection(url_parameters)
channel = connection.channel()
channel.queue_declare(queue=QUEUE_NAME, arguments={"x-max-priority": 5})
channel.queue_declare(queue=GROUP_CRAWLER_QUEUE_NAME, arguments={"x-max-priority": 1})
channel.queue_declare(queue=CAPTCHA_SOLVER_QUEUE_NAME)
channel.basic_qos(prefetch_count=1)

# Initialize database
database = Client(DATABASE_URL)

# Initialize logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def callback(ch, method, properties, body: bytes):
    ch.basic_ack(delivery_tag=method.delivery_tag)
    message: dict = json.loads(body)
    crawl_mode = message.get("crawl_mode", None)
    domain = message.get("domain", None)
    score = message.get("score", 0)
    logging.info(f"[+] {crawl_mode.lower()}: ({score}) {domain}")

    if crawl_mode == "BASELINE":
        process_baseline(message)
    elif crawl_mode == "GROUP":
        process_group(message)
    elif crawl_mode == "CAPTCHA":
        process_captcha(message)
    elif crawl_mode == "CAPTCHA_SOLVED":
        process_solved_captcha(message)
    else:
        raise NotImplementedError(f"Unknown crawl mode: {crawl_mode}")


def process_baseline(message: dict):
    domain = message.get("domain", None)
    effective_domains = message.get("effective_domains", [])
    screenshots = message.get("screenshots", [])
    html_codes = message.get("html_codes", [])
    
    try:
        # Full phishing detection (vision + interaction)
        phish_categories, phish_target, has_crp, _ = phishintention.detect(domain, effective_domains, screenshots, html_codes)
        if has_crp and any(phish_categories) and phish_target != "Microsoft":
            logging.info(f"\t[>] phishing detected: {phish_target}")
            message["phish_pred"] = True
            message["phish_target"] = phish_target

            logging.info(f"\t[>] submit to virustotal")
            message["vt_analysis_id"] = utils.submit_virustotal(domain)
            message["vt_analysis_times"] = 1

            logging.info(f"\t[>] deploying group crawler, will come back later")
            channel.basic_publish(
                exchange='',
                routing_key=GROUP_CRAWLER_QUEUE_NAME,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )

    except Exception as e:
        logging.debug(traceback.format_exc())
        logging.error(f"{e}")


def process_group(message: dict):
    domain = message.get("domain", None)
    ip = message.get("ip", None)
    tld = message.get("tld", None)
    effective_domains = message.get("effective_domains", [])
    crawl_times = message.get("crawl_times", [])
    screenshots = message.get("screenshots", [])
    html_codes = message.get("html_codes", [])
    phish_pred = message.get("phish_pred", False)
    phish_target = message.get("phish_target", None)
    vt_analysis_times = message.get("vt_analysis_times", 0)
    vt_analysis_id = message.get("vt_analysis_id", None)
    groups = len(screenshots)

    sample = BaselineSample()
    sample._id = ObjectId()
    sample.domain = domain
    sample.ip = ip
    sample.tld = tld
    sample.timestamp = datetime.now()
    sample.phish_pred = phish_pred
    sample.phish_target = phish_target
    sample.vt_analysis_times = vt_analysis_times
    sample.vt_analysis_id = vt_analysis_id
    for i in range(groups): setattr(sample, f"crawl_time_{i+1}", crawl_times[i])
    
    try:
        # Full phishing detection (vision + interaction)
        phish_categories, _, _, sample.phish_det_time = phishintention.detect(domain, effective_domains, screenshots, html_codes)
        for i in range(groups): setattr(sample, f"group_{i+1}", phish_categories[i])
        logging.info(f"\t[>] group crawler verdicts: {phish_categories}")

        # Create poll, save sample to database
        sample.poll_open = True
        for i in range(groups): setattr(sample, f"screenshot_{i+1}", f"data:image/png;base64,{screenshots[i]}")
        logging.info("\t[>] save to database")
        database.insert_baseline(sample.__dict__)
        logging.info("\t[>] create poll")
        utils.create_poll("BASELINE", str(sample._id))

    except Exception as e:
        logging.debug(traceback.format_exc())
        logging.error(f"{e}")


def process_captcha(message: dict):
    domain = message.get("domain", None)
    screenshots = message.get("screenshots", [])
    suspect_captcha = message.get("suspect_captcha", None)

    has_captcha, captcha_type, captcha_det_time, captcha_rec_time = phishdecloaker.check_captcha(screenshots[-1])
    logging.info(f"\t[>] captcha suspected: {suspect_captcha}, detected: {captcha_type}")

    if suspect_captcha == "hcaptcha":
        has_captcha = True
        captcha_type = "hcaptcha_checkbox"

    message["url"] = f"https://{domain}"
    message["has_captcha"] = has_captcha
    message["captcha_type"] = captcha_type
    message["captcha_det_time"] = captcha_det_time
    message["captcha_rec_time"] = captcha_rec_time

    if has_captcha: 
        queue = None
        match captcha_type:
            case "hcaptcha" | "hcaptcha_checkbox": queue = "hcaptcha_solver"
            case "recaptchav2" | "recaptchav2_checkbox": queue = "recaptchav2_solver"
            case "geetest_slide_puzzle" | "netease_slide" | "tencent_slide": queue = "slider_solver"
            case "baidu_slide_rotate": queue = "rotation_solver"

        if queue:
            logging.info(f"\t[>] deploying solver, will come back later")
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
            )
        else:
            logging.info(f"\t[>] no solver")
            process_solved_captcha(message)


def process_solved_captcha(message: dict):
    domain = message.get("domain", None)
    ip = message.get("ip", None)
    tld = message.get("tld", None)
    effective_domains = message.get("effective_domains", [])
    crawl_times = message.get("crawl_times", [])
    screenshots = message.get("screenshots", [])
    html_codes = message.get("html_codes", [])
    has_captcha = message.get("has_captcha", False)
    captcha_type = message.get("captcha_type", None)
    captcha_solved = message.get("captcha_solved", False)
    captcha_sitekey = message.get("captcha_sitekey", None)
    captcha_det_time = message.get("captcha_det_time", 0)
    captcha_rec_time = message.get("captcha_rec_time", 0)
    captcha_sol_time = message.get("captcha_sol_time", 0)

    logging.info(f"\t[>] captcha solved: {captcha_solved}, type: {captcha_type}")

    sample = CaptchaSample()
    sample._id = ObjectId()
    sample.domain = domain
    sample.ip = ip
    sample.tld = tld
    sample.timestamp = datetime.now()
    sample.crawl_time = crawl_times[-1]
    sample.screenshot = f"data:image/png;base64,{screenshots[-1]}"
    sample.has_captcha = has_captcha
    sample.captcha_type = captcha_type
    sample.captcha_solved = captcha_solved
    sample.captcha_sitekey = captcha_sitekey
    sample.captcha_det_time = captcha_det_time
    sample.captcha_rec_time = captcha_rec_time
    sample.captcha_sol_time = captcha_sol_time
    sample.ground_captcha = True if captcha_solved else False
    sample.poll_open = True

    try:
        # Phishing detection
        phish_categories, phish_target, has_crp, sample.phish_det_time = phishintention.detect(effective_domains, screenshots, html_codes, domain)
        if has_crp and any(phish_categories):
            logging.info(f"\t[>] phishing detected: {phish_target}")
            sample.phish_pred = True
            sample.phish_target = phish_target

        # Always scan CAPTCHA websites
        logging.info(f"\t[>] submit to virustotal")
        sample.vt_analysis_id = utils.submit_virustotal(domain)
        sample.vt_analysis_times += 1

        # Always insert CAPTCHA sites to database
        database.insert_captcha(sample.__dict__)
        logging.info("\t[>] create poll")
        utils.create_poll("CAPTCHA", str(sample._id))

    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"{e}")
    

if __name__ == "__main__":
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    channel.start_consuming()
