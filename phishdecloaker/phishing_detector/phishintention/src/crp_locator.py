import os
import re
import time
import logging

import cv2
import numpy as np
from playwright.sync_api import Page

from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg

from phishintention.src.util.chrome import *
from phishintention.src.crp_classifier import *
from phishintention.src.AWL_detector import *

# global dict
class_dict = {0: 'login'}
inv_class_dict = {v: k for k, v in class_dict.items()}

def cv_imread(filePath):
    '''
    When image path contains nonenglish characters, normal cv2.imread will have error
    :param filePath:
    :return:
    '''
    cv_img = cv2.imdecode(np.fromfile(filePath, dtype=np.uint8), -1)
    return cv_img

def login_config(rcnn_weights_path: str, rcnn_cfg_path: str, threshold=0.05, device='cuda'):
    '''
    Load login button detector configurations
    :param rcnn_weights_path: path to rcnn weights
    :param rcnn_cfg_path: path to configuration file
    :return cfg: rcnn cfg
    :return model: rcnn model
    '''
    # merge configuration
    cfg = get_cfg()
    cfg.merge_from_file(rcnn_cfg_path)
    cfg.MODEL.WEIGHTS = rcnn_weights_path
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = threshold # lower this threshold to report more boxes
    if device == 'cpu':
        cfg.MODEL.DEVICE = 'cpu'
    
    # initialize model
    model = DefaultPredictor(cfg)
    return cfg, model

def login_recognition(img, model):
    '''
    Recognize login button from a screenshot
    :param img: [str|np.ndarray]
    :param model: rcnn model
    :return pred_classes: torch.Tensor of shape Nx1 0 for login
    :return pred_boxes: torch.Tensor of shape Nx4, bounding box coordinates in (x1, y1, x2, y2)
    :return pred_scores: torch.Tensor of shape Nx1, prediction confidence of bounding boxes
    '''
    if isinstance(img, str):
        img_processed = cv2.imread(img)
        if img_processed is None:
            return None, None, None
        else:
            if img_processed.shape[-1] == 4:
                img_processed = cv2.cvtColor(img_processed, cv2.COLOR_BGRA2BGR)
    else:
        img_processed = img
        
    pred = model(img_processed)
    pred_i = pred["instances"].to("cpu")
    pred_classes = pred_i.pred_classes # Boxes types
    pred_boxes = pred_i.pred_boxes.tensor # Boxes coords
    pred_scores = pred_i.scores # Boxes prediction scores

    return pred_classes, pred_boxes, pred_scores

def keyword_heuristic(page: Page, orig_url, page_text,
                      new_screenshot_path, new_html_path, new_info_path,
                      ele_model, cls_model):
    '''
    Keyword based login finder
   :param page: playwright Page
   :param orig_url: original URL
   :param page_text: html text
   :param new_screenshot_path: new screenshot path
   :param new_html_path: new html path
   :param new_info_path: new info path
   :param ele_model: element detector model
   :param cls_model: CRP classifier
   :return reach_crp: reach CRP or not
   :return time_deduct: URL loading and clicking time
    '''
    ct = 0 # count number of sign-up/login links
    reach_crp = False # reach a CRP page or not
    time_deduct = 0
    logging.info(page_text)

    # URL after loading might be different from orig_url
    start_time = time.time()
    orig_url = page.url
    time_deduct += time.time() - start_time

    for i in page_text: # iterate over html text
        # looking for keyword
        start_time = time.time()
        keyword_finder = re.findall('(login)|(log in)|(log on)|(signup)|(sign up)|(sign in)|(sign on)|(submit)|(register)|(create.*account)|(open an account)|(get free.*now)|(join now)|(new user)|(my account)|(come in)|(check in)|(personal area)|(logg inn)|(Log-in)|(become a member)|(customer centre)|(登入)|(登录)|(登錄)|(登録)|(注册)|(Anmeldung)|(iniciar sesión)|(identifier)|(ログインする)|(サインアップ)|(ログイン)|(로그인)|(가입하기)|(시작하기)|(регистрация)|(войти)|(вход)|(accedered)|(gabung)|(daftar)|(masuk)|(girişi)|(Giriş)|(สมัครสม)|(üye ol)|(وارد)|(عضویت)|(regístrate)|(acceso)|(acessar)|(entrar )|(giriş)|(เข้าสู่ระบบ)|(สมัครสมาชิก)|(Přihlásit)|(mein konto)|(registrati)|(anmelden)|(me connecter)|(ingresa)|(mon allociné)|(accedi)|(мой профиль)|(حسابي)|(administrer)|(next)|(entre )|(cadastre-se)|(είσοδος)|(entrance)|(start now)|(accessibilité)|(accéder)|(zaloguj)|(otwórz konto osobiste)|(đăng nhập)|(devam)|(your account)',
                                        i, re.IGNORECASE)
        time_deduct += time.time() - start_time
        if len(keyword_finder) > 0:
            ct += 1
            found_kw = [y for x in keyword_finder for y in x if len(y) > 0]
            if len(found_kw) == 1: # find only 1 keyword
                 found_kw = found_kw[0]
                 if len(i) <= 2*len(found_kw): # if the text is not long, click on text
                     start_time = time.time()
                     click_text(page, i)
                     try:
                         current_url = page.url
                         if current_url == orig_url:  # if page is not redirected, try clicking the keyword instead
                             logging.info(found_kw)
                             click_text(page, found_kw)
                     except Exception as e:
                         logging.info(e)
                         pass
                     logging.info('Successfully click')
                     time_deduct += time.time() - start_time

                 else: # otherwise click on keyword
                     start_time = time.time()
                     click_text(page, found_kw)
                     logging.info('Successfully click')
                     time_deduct += time.time() - start_time

            else: # find at least 2 keywords in same bulk of text
                 found_kw = found_kw[0] # only click the first keyword
                 start_time = time.time()
                 click_text(page, found_kw)
                 logging.info('Successfully click')
                 time_deduct += time.time() - start_time


            # save redirected url
            try:
                start_time = time.time()
                current_url = page.url
                page.screenshot(path=new_screenshot_path)

                writetxt(new_html_path, page.content())
                writetxt(new_info_path, str(current_url))
                time_deduct += time.time() - start_time

                # Call CRP classifier
                # CRP HTML heuristic
                cre_pred = html_heuristic(new_html_path)
                # Credential classifier module
                if cre_pred == 1:  # if HTML heuristic report as nonCRP
                    pred_classes, pred_boxes, pred_scores = element_recognition(img=new_screenshot_path,
                                                                                model=ele_model)
                    cre_pred, cred_conf, _ = credential_classifier_mixed_al(img=new_screenshot_path, coords=pred_boxes,
                                                                            types=pred_classes, model=cls_model)
                if cre_pred == 0:  # this is an CRP
                    reach_crp = True
                    break  # stop when reach an CRP already

            except Exception as e:
                logging.info(e)
                pass

            # Back to the original site if CRP not found
            start_time = time.time()
            return_success, page = visit_url(page, orig_url)
            if not return_success:
                time_deduct += time.time() - start_time
                break  # TIMEOUT Error
            time_deduct += time.time() - start_time

        # Only check Top 3
        if ct >= 3:
            break

    return reach_crp, time_deduct

def cv_heuristic(page: Page, orig_url, old_screenshot_path,
                 new_screenshot_path, new_html_path, new_info_path,
                 login_model, ele_model, cls_model):
    '''
    CV based login finder
    :param page: playwright Page
    :param orig_url: original URL
    :param old_screenshot_path: old screenshot path
    :param new_screenshot_path: new screenshot path
    :param new_html_path: new html path
    :param new_info_path: new info path
    :param login_model: login button detector
    :param ele_model: element detector
    :param cls_model: CRP classifier
    :return reach_crp: reach CRP or not
    :return time_deduct: URL loading/clicking time
    '''

    # CV-based login finder
    # predict elements
    pred_classes, pred_boxes, _ = login_recognition(img=old_screenshot_path, model=login_model)
    # # visualize elements
    # check = vis(old_screenshot_path, pred_boxes, pred_classes)
    # cv2.imshow(check)
    reach_crp = False
    time_deduct = 0
    # if no prediction at all
    if pred_boxes is None or len(pred_boxes) == 0:
        return reach_crp, time_deduct

    for bbox in pred_boxes.detach().cpu().numpy()[: min(3, len(pred_boxes))]: # only for top3 boxes
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        start_time = time.time()
        click_point(page, center[0], center[1])  # click center point of predicted bbox for safe
        time_deduct += time.time() - start_time

        # save redirected url
        try:
            start_time = time.time()
            current_url = page.url
            page.screenshot(path=new_screenshot_path) # save new screenshot
            writetxt(new_html_path, page.content())
            writetxt(new_info_path, str(current_url))
            time_deduct += time.time() - start_time

            # Call CRP classifier
            # CRP HTML heuristic
            cre_pred = html_heuristic(new_html_path)
            # Credential classifier module
            if cre_pred == 1:  # if HTML heuristic report as nonCRP
                pred_classes_crp, pred_boxes_crp, _ = element_recognition(img=new_screenshot_path, model=ele_model)
                cre_pred, cred_conf, _ = credential_classifier_mixed_al(img=new_screenshot_path, coords=pred_boxes_crp,
                                                                        types=pred_classes_crp, model=cls_model)
            # stop when reach an CRP already
            if cre_pred == 0:  # this is an CRP already
                reach_crp = True
                break

        except Exception as e:
            logging.info(e)

        # Back to the original site if CRP not found
        start_time = time.time()
        return_success, page = visit_url(page, orig_url)
        if not return_success:
            time_deduct += time.time() - start_time
            break  # TIMEOUT Error
        time_deduct += time.time() - start_time

    return reach_crp, time_deduct


def dynamic_analysis(url: str, screenshot_path: str, login_model, ele_model, cls_model, page: Page):
    '''
    Dynamic analysis to find CRP
    :param url: URL
    :param screenshot_path: old screenshot path
    :param login_model: login button detector
    :param ele_model: element detector
    :param cls_model: CRP classifier
    :param page: playwright Page
    :return current_url: final URL
    :return current_ss: final screenshot path
    :return reach_crp: reach CRP or not
    :return total_time: total processing time
    '''

    # get url
    orig_url = url
    successful = False # reach CRP or not?
    # path to save redirected URL
    data_path = os.path.dirname(os.path.abspath(screenshot_path))
    new_screenshot_path = os.path.join(data_path, 'new_shot.png')
    new_html_path = os.path.join(data_path, 'new_html.txt')
    new_info_path = os.path.join(data_path, 'new_info.txt')

    visit_success, page = visit_url(page, orig_url, popup=False)

    if not visit_success:
        return url, screenshot_path, successful, 0

    start_time = time.time()
    logging.info("Getting url")
    page_text = get_page_text(page)

    # HTML heuristic based login finder
    reach_crp, time_deduct_html = keyword_heuristic(page=page, orig_url=orig_url, page_text=page_text,
                                  new_screenshot_path=new_screenshot_path, new_html_path=new_html_path,
                                  new_info_path=new_info_path, ele_model=ele_model, cls_model=cls_model)

    logging.info(f'After HTML keyword finder: {reach_crp}')
    total_time = time.time() - start_time - time_deduct_html

    # If HTML login finder did not find CRP, call CV-based login finder
    if not reach_crp:
        # Ensure that it goes back to the original URL
        visit_success, page = visit_url(page, orig_url, sleep=True)
        if not visit_success:
            return url, screenshot_path, successful, total_time  # load URL unsucessful

        # FIXME: update the screenshots
        try:
            
            page.screenshot(path=os.path.join(data_path, 'shot4cv.png'))
        except Exception as e:
            return url, screenshot_path, successful, total_time  # save updated screenshot unsucessful

        start_time = time.time()
        reach_crp, time_deduct_cv = cv_heuristic(page=page,
                                                 orig_url=orig_url, old_screenshot_path=os.path.join(data_path, 'shot4cv.png'),
                                                 new_screenshot_path=new_screenshot_path, new_html_path=new_html_path,
                                                 new_info_path=new_info_path, login_model=login_model, ele_model=ele_model, cls_model=cls_model)
        total_time += time.time() - start_time - time_deduct_cv
        logging.info(f'After CV finder: {reach_crp}')

    # Final URL
    if os.path.exists(new_info_path):
        current_url = open(new_info_path, encoding='ISO-8859-1').read()
        current_ss = new_screenshot_path
        if len(current_url) == 0: # if current URL is empty
            current_url = orig_url # return original url and screenshot_path
            current_ss = screenshot_path
    else: # return original url and screenshot_path
        current_url = orig_url
        current_ss = screenshot_path

    return current_url, current_ss, reach_crp, total_time
