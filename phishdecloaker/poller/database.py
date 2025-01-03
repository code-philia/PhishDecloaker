from bson.objectid import ObjectId

from pymongo import MongoClient
    

class Database:
    def __init__(self, database_url: str) -> None:
        self.client = MongoClient(database_url)
        self.db = self.client["phishdecloaker"]
        self.collections = {
            "BASELINE": self.db["baseline"],
            "CAPTCHA": self.db["captcha"]
        }
        self.projections = {
            "BASELINE": {
                "_id": 1,
                "poll_id": 1,
                "domain": 1,
                "screenshot_1": 1,
                "screenshot_2": 1,
                "screenshot_3": 1,
                "screenshot_4": 1,
                "screenshot_5": 1,
                "group_1": 1,
                "group_2": 1,
                "group_3": 1,
                "group_4": 1,
                "group_5": 1,
                "phish_pred": 1,
                "phish_target": 1,
            },
            "CAPTCHA": {
                "_id": 1,
                "poll_id": 1,
                "domain": 1,
                "screenshot": 1,
                "phish_pred": 1,
                "phish_target": 1,
                "has_captcha": 1,
                "captcha_type": 1,
                "captcha_solved": 1
            }
        }

    def update_poll_id(self, crawl_mode: str, sample_id: str, poll_id: str):
        self.collections[crawl_mode].find_one_and_update({"_id": ObjectId(sample_id)}, {"$set": {"poll_id": poll_id}})

    def update_ground_truth(self, crawl_mode: str, sample_id: str, verdict: str):
        choice_to_ground_truth = {
            "Yes": True,
            "No": False,
        }
        choices = verdict.split(", ")
        choices.reverse()
        ground_truth = {"poll_open": False}

        for choice, label in zip(choices, ["ground_phishing", "ground_captcha"]):
            ground_truth |= {label: choice_to_ground_truth[choice]}

        if not ground_truth["ground_phishing"]:
            ground_truth |= {"is_monitoring": False}

        self.collections[crawl_mode].find_one_and_update({"_id": ObjectId(sample_id)}, {"$set": ground_truth})

    def get_sample(self, crawl_mode: str, sample_id: str):
        projection = self.projections[crawl_mode]
        sample = self.collections[crawl_mode].find_one({"_id": ObjectId(sample_id)}, projection)
        return sample