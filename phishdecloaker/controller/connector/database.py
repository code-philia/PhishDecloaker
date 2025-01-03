from dataclasses import dataclass
from bson.objectid import ObjectId
from datetime import datetime

from pymongo import MongoClient

@dataclass
class BaselineSample:
    # --- metadata ---
    _id: ObjectId            = None
    domain: str              = None              # domain
    tld: str                 = None              # tld
    ip: str                  = None              # IP address
    timestamp: datetime      = None              # timestamp of sample creation
    
    # --- phishing detection ---
    group_1: bool            = False             # is group 1 positive?
    group_2: bool            = False             # is group 2 positive?
    group_3: bool            = False             # is group 3 positive?
    group_4: bool            = False             # is group 4 positive?
    group_5: bool            = False             # is group 5 positive?
    phish_pred: bool         = False             # phishintention prediction category
    phish_target: str        = None              # phishintention prediction target                   

    # --- timing ---
    crawl_time_1              = 0                # group 1 crawling time
    crawl_time_2              = 0                # group 2 crawling time
    crawl_time_3              = 0                # group 3 crawling time
    crawl_time_4              = 0                # group 4 crawling time
    crawl_time_5              = 0                # group 5 crawling time
    phish_det_time            = 0                # phishing detection time

    # --- telegram bot ---
    poll_open: bool           = False            # is the poll open
    poll_id: int              = None             # telegram poll id
    ground_phishing: bool     = False            # poll phishing verdict 

    # --- screenshots ---
    screenshot_1: str         = None             # group 1 screenshot
    screenshot_2: str         = None             # group 2 screenshot
    screenshot_3: str         = None             # group 3 screenshot
    screenshot_4: str         = None             # group 4 screenshot
    screenshot_5: str         = None             # group 5 screenshot

    # --- monitoring ---
    is_monitoring: bool       = True             # is it monitored? By default true unless confirmed not phishing
    is_down: bool             = False            # is it down?
    down_time: datetime       = None             # when it was no longer alive (hourly)
    vt_malicious: str         = None             # number of VT vendors reporting as malicious, format x|x|x|x... (daily)
    vt_suspicious: str        = None             # number of VT vendors reporting as suspicious, format x|x|x|x... (daily)
    vt_harmless: str          = None             # number of VT vendors reporting as harmless, format x|x|x|x... (daily)
    vt_undetected: str        = None             # number of VT vendors reporting as undetected, format x|x|x|x... (daily)
    vt_analysis_times: int    = 0                # number of times submitted to VT
    vt_analysis_id: str       = None             # last VT analysis ID
    vt_url_id: str            = None             # last VT url ID

    is_gsb_blacklisted: bool     = False         # is it blacklisted by GSB?
    is_ms_blacklisted: bool      = False         # is it blacklisted by SmartScreen?
    gsb_blacklist_time: datetime = None          # when it was first blacklisted by GSB (hourly)
    ms_blacklist_time: datetime  = None          # when it was first blacklisted by SmartScreen (hourly)


@dataclass
class CaptchaSample:
    # --- metadata ---
    _id: ObjectId            = None
    domain: str              = None              # domain
    tld: str                 = None              # tld
    ip: str                  = None              # IP address
    timestamp: datetime      = None              # timestamp of sample creation

    # --- captcha_det_reg ---
    has_captcha: bool        = False             # is captcha detected?
    captcha_type: str        = None              # detected captcha type
    captcha_solved: bool     = False             # is captcha auto-solved by solver?
    captcha_sitekey: str     = None              # captcha site key, if any
    
    # --- phishing detection ---
    phish_pred: bool         = False             # phishintention prediction category
    phish_target: str        = None              # phishintention prediction target                   

    # --- timing ---
    crawl_time                = 0                # crawling time
    captcha_det_time          = 0                # captcha detection time
    captcha_rec_time          = 0                # captcha recognition time
    captcha_sol_time          = 0                # captcha solving time
    phish_det_time            = 0                # phishing detection time

    # --- telegram bot ---
    poll_open: bool           = False            # is the poll open
    poll_id: int              = None             # telegram poll id
    ground_phishing: bool     = False            # poll phishing verdict 
    ground_captcha: bool      = False            # poll captcha verdict

    # --- screenshots ---
    screenshot: str           = None             # screenshot

    # --- monitoring ---
    is_monitoring: bool       = True             # is it monitored? By default true unless confirmed not phishing
    is_down: bool             = False            # is it down?
    down_time: datetime       = None             # when it was no longer alive (hourly)
    vt_malicious: str         = None             # number of VT vendors reporting as malicious, format x|x|x|x... (daily)
    vt_suspicious: str        = None             # number of VT vendors reporting as suspicious, format x|x|x|x... (daily)
    vt_harmless: str          = None             # number of VT vendors reporting as harmless, format x|x|x|x... (daily)
    vt_undetected: str        = None             # number of VT vendors reporting as undetected, format x|x|x|x... (daily)
    vt_analysis_times: int    = 0                # number of times submitted to VT
    vt_analysis_id: str       = None             # last VT analysis ID
    vt_url_id: str            = None             # last VT url ID

    is_gsb_blacklisted: bool     = False         # is it blacklisted by GSB?
    is_ms_blacklisted: bool      = False         # is it blacklisted by SmartScreen?
    gsb_blacklist_time: datetime = None          # when it was first blacklisted by GSB (hourly)
    ms_blacklist_time: datetime  = None          # when it was first blacklisted by SmartScreen (hourly)


class Client:
    def __init__(self, database_url: str) -> None:
        self.client  = MongoClient(database_url)
        self.db  = self.client['phishdecloaker']
        self.baseline_collection = self.db['baseline']
        self.captcha_collection = self.db['captcha']

    def insert_baseline(self, sample: dict):
        self.baseline_collection.insert_one(sample)

    def insert_captcha(self, sample: dict):
        self.captcha_collection.insert_one(sample)