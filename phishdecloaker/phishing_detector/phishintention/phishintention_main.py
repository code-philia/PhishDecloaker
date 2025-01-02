import logging
import os

from phishintention.phishintention_config import *
from playwright.sync_api import (Browser, BrowserContext, CDPSession, Page,
                                 sync_playwright)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

#####################################################################################################################
# ** Step 1: Enter Layout detector, get predicted elements
# ** Step 2: Enter Siamese, siamese match a phishing target, get phishing target

# **         If Siamese report no target, Return Benign, None
# **         Else Siamese report a target, Enter CRP classifier(and HTML heuristic)

# ** Step 3: If CRP classifier(and heuristic) report it is non-CRP, go to step 4: Dynamic analysis, go back to step1
# **         Else CRP classifier(and heuristic) reports its a CRP page

# ** Step 5: If reach a CRP + Siamese report target: Return Phish, Phishing target
# ** Else: Return Benign
#####################################################################################################################


def test(
    url,
    domain,
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
    DOMAIN_MAP: dict,
    BROWSER_HOST,
):
    """
    Phish-discovery main script
    :return phish_category: 0 for benign, 1 for phish
    :return phish_target: None/brand name
    """

    # 0 for benign, 1 for phish, default is benign
    screenshot_path = os.path.join(temp_dir, "screenshot.png")
    pred_category = False
    pred_target = None
    has_crp = False
    logging.info("Entering phishintention")

    ####################### Step1: layout detector ##############################################
    pred_classes, pred_boxes, _ = element_recognition(
        img=screenshot_path, model=AWL_MODEL
    )

    # If no element is reported
    if pred_boxes is None or len(pred_boxes) == 0:
        logging.info("No element is detected, report as benign")
        return pred_category, pred_target, has_crp
    logging.info("Entering siamese")

    # domain already in targetlist
    existing_brands = DOMAIN_MAP.keys()
    existing_domains = [y for x in list(DOMAIN_MAP.values()) for y in x]
    if domain in existing_brands or domain in existing_domains:
        return pred_category, pred_target, has_crp

    ######################## Step2: Siamese (logo matcher) ########################################
    pred_target, _, _ = phishpedia_classifier_OCR(
        pred_classes=pred_classes,
        pred_boxes=pred_boxes,
        domain_map=DOMAIN_MAP,
        model=SIAMESE_MODEL,
        ocr_model=OCR_MODEL,
        logo_feat_list=LOGO_FEATS,
        file_name_list=LOGO_FILES,
        domain=domain,
        shot_path=screenshot_path,
        ts=SIAMESE_THRE,
    )

    if pred_target is None:
        logging.info("Did not match to any brand, report as benign")
        return pred_category, pred_target, has_crp

    ######################## Step3: CRP checker (if a target is reported) #################################
    logging.info("A target is reported by siamese, enter CRP classifier")

    if pred_target is not None:
        # CRP HTML heuristic
        cre_pred = html_heuristic(html_code)

        if cre_pred == 1:  # if HTML heuristic report as nonCRP
            # CRP classifier
            logging.info("Trying mixed credential classifier")
            cre_pred, _, _ = credential_classifier_mixed_al(
                img=screenshot_path,
                coords=pred_boxes,
                types=pred_classes,
                model=CRP_CLASSIFIER,
            )

        ######################## Step4: Dynamic analysis #################################
        if cre_pred == 1:
            logging.info("It is a Non-CRP page, enter dynamic analysis")

            with sync_playwright() as p:
                browser: Browser = p.chromium.connect_over_cdp(
                    f"ws://{BROWSER_HOST}?stealth&timeout=300000"
                )

                context: BrowserContext = browser.new_context(
                    java_script_enabled=True, viewport={"width": 1920, "height": 1080}
                )

                page: Page = context.new_page()

                url, screenshot_path, successful, _ = dynamic_analysis(
                    url=url,
                    screenshot_path=screenshot_path,
                    cls_model=CRP_CLASSIFIER,
                    ele_model=AWL_MODEL,
                    login_model=CRP_LOCATOR,
                    page=page,
                )

                if successful == False:
                    logging.info(
                        "Dynamic analysis cannot find any link redirected to a CRP page, report as benign"
                    )
                else:
                    cre_pred = 0

    ######################## Step4: Return #################################
    pred_category = True if pred_target is not None else False
    has_crp = True if cre_pred == 0 else False

    return pred_category, pred_target, has_crp
