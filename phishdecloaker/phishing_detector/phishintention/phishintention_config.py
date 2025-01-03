import logging

from phishintention.src.AWL_detector import *
from phishintention.src.crp_classifier import *
from phishintention.src.crp_locator import *

# Global configuration
from phishintention.src.OCR_aided_siamese import *
from phishintention.src.util.chrome import *


class Config:
    CURRENT_DIR = os.path.dirname(__file__)


def load_config(device="cuda"):
    configs = {
        "AWL_MODEL": {
            "CFG_PATH": f"{Config.CURRENT_DIR}/src/AWL_detector_utils/configs/faster_rcnn_web.yaml",
            "WEIGHTS_PATH": f"{Config.CURRENT_DIR}/src/AWL_detector_utils/output/website_lr0.001/model_final.pth",
        },
        "CRP_CLASSIFIER": {
            "WEIGHTS_PATH": f"{Config.CURRENT_DIR}/src/crp_classifier_utils/output/Increase_resolution_lr0.005/BiT-M-R50x1V2_0.005.pth.tar",
            "MODEL_TYPE": "mixed",
        },
        "CRP_LOCATOR": {
            "CFG_PATH": f"{Config.CURRENT_DIR}/src/crp_locator_utils/login_finder/configs/faster_rcnn_login_lr0.001_finetune.yaml",
            "WEIGHTS_PATH": f"{Config.CURRENT_DIR}/src/crp_locator_utils/login_finder/output/lr0.001_finetune/model_final.pth",
        },
        "SIAMESE_MODEL": {
            "NUM_CLASSES": 277,
            "WEIGHTS_PATH": f"{Config.CURRENT_DIR}/src/OCR_siamese_utils/output/targetlist_lr0.01/bit.pth.tar",
            "OCR_WEIGHTS_PATH": f"{Config.CURRENT_DIR}/src/OCR_siamese_utils/demo_downgrade.pth.tar",
            "TARGETLIST_PATH": f"{Config.CURRENT_DIR}/src/phishpedia_siamese/",
            "MATCH_THRE": 0.87,
            "DOMAIN_MAP_PATH": f"{Config.CURRENT_DIR}/src/phishpedia_siamese/domain_map.pkl",
        },
    }

    # element recognition model
    AWL_CFG_PATH = configs["AWL_MODEL"]["CFG_PATH"]
    AWL_WEIGHTS_PATH = configs["AWL_MODEL"]["WEIGHTS_PATH"]
    AWL_CONFIG, AWL_MODEL = element_config(
        rcnn_weights_path=AWL_WEIGHTS_PATH, rcnn_cfg_path=AWL_CFG_PATH, device=device
    )

    CRP_CLASSIFIER = credential_config(
        checkpoint=configs["CRP_CLASSIFIER"]["WEIGHTS_PATH"],
        model_type=configs["CRP_CLASSIFIER"]["MODEL_TYPE"],
    )

    CRP_LOCATOR_CONFIG, CRP_LOCATOR_MODEL = login_config(
        rcnn_weights_path=configs["CRP_LOCATOR"]["WEIGHTS_PATH"],
        rcnn_cfg_path=configs["CRP_LOCATOR"]["CFG_PATH"],
        device=device,
    )

    # siamese model
    logging.info("Load protected logo list")

    SIAMESE_MODEL, OCR_MODEL = phishpedia_config_OCR_easy(
        num_classes=configs["SIAMESE_MODEL"]["NUM_CLASSES"],
        weights_path=configs["SIAMESE_MODEL"]["WEIGHTS_PATH"],
        ocr_weights_path=configs["SIAMESE_MODEL"]["OCR_WEIGHTS_PATH"],
    )
    LOGO_FEATS = np.load(
        os.path.join(
            os.path.dirname(configs["SIAMESE_MODEL"]["TARGETLIST_PATH"]),
            "LOGO_FEATS.npy",
        )
    )
    LOGO_FILES = np.load(
        os.path.join(
            os.path.dirname(configs["SIAMESE_MODEL"]["TARGETLIST_PATH"]),
            "LOGO_FILES.npy",
        )
    )

    logging.info("Finish loading protected logo list")

    SIAMESE_THRE = configs["SIAMESE_MODEL"]["MATCH_THRE"]

    # brand-domain dictionary
    DOMAIN_MAP_PATH = configs["SIAMESE_MODEL"]["DOMAIN_MAP_PATH"]
    with open(DOMAIN_MAP_PATH, "rb") as handle:
        DOMAIN_MAP = pickle.load(handle)

    return (
        AWL_MODEL,
        CRP_CLASSIFIER,
        CRP_LOCATOR_MODEL,
        SIAMESE_MODEL,
        OCR_MODEL,
        SIAMESE_THRE,
        LOGO_FEATS,
        LOGO_FILES,
        DOMAIN_MAP,
    )
