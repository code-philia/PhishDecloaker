import os
import pickle
from collections import OrderedDict

import numpy as np
import tldextract
import torch
from phishintention.src.OCR_siamese_utils.demo import ocr_model_config
from phishintention.src.OCR_siamese_utils.inference import (
    pred_siamese_OCR, siamese_inference_OCR)
from phishintention.src.phishpedia_siamese.inference import (pred_siamese,
                                                             siamese_inference)
from phishintention.src.phishpedia_siamese.siamese_retrain.bit_pytorch.models import \
    KNOWN_MODELS
from phishintention.src.phishpedia_siamese.utils import brand_converter
from tqdm import tqdm


def phishpedia_config(
    num_classes: int, weights_path: str, targetlist_path: str, grayscale=False
):
    """
    Load phishpedia configurations
    :param num_classes: number of protected brands
    :param weights_path: siamese weights
    :param targetlist_path: targetlist folder
    :param grayscale: convert logo to grayscale or not, default is RGB
    :return model: siamese model
    :return logo_feat_list: targetlist embeddings
    :return file_name_list: targetlist paths
    """

    # Initialize model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = KNOWN_MODELS["BiT-M-R50x1"](head_size=num_classes, zero_head=True)

    # Load weights
    weights = torch.load(weights_path, map_location="cpu")
    weights = weights["model"] if "model" in weights.keys() else weights
    new_state_dict = OrderedDict()
    for k, v in weights.items():
        name = k.split("module.")[1]
        new_state_dict[name] = v

    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    #     Prediction for targetlists
    logo_feat_list = []
    file_name_list = []

    for target in tqdm(os.listdir(targetlist_path)):
        if target.startswith("."):  # skip hidden files
            continue
        for logo_path in os.listdir(os.path.join(targetlist_path, target)):
            if (
                logo_path.endswith(".png")
                or logo_path.endswith(".jpeg")
                or logo_path.endswith(".jpg")
                or logo_path.endswith(".PNG")
                or logo_path.endswith(".JPG")
                or logo_path.endswith(".JPEG")
            ):
                if logo_path.startswith("loginpage") or logo_path.startswith(
                    "homepage"
                ):  # skip homepage/loginpage
                    continue
                logo_feat_list.append(
                    pred_siamese(
                        img=os.path.join(targetlist_path, target, logo_path),
                        model=model,
                        grayscale=grayscale,
                    )
                )
                file_name_list.append(
                    str(os.path.join(targetlist_path, target, logo_path))
                )

    return model, np.asarray(logo_feat_list), np.asarray(file_name_list)


def phishpedia_config_OCR(
    num_classes: int,
    weights_path: str,
    ocr_weights_path: str,
    targetlist_path: str,
    grayscale=False,
):
    """
    Load phishpedia configurations
    :param num_classes: number of protected brands
    :param weights_path: siamese weights
    :param targetlist_path: targetlist folder
    :param grayscale: convert logo to grayscale or not, default is RGB
    :return model: siamese model
    :return logo_feat_list: targetlist embeddings
    :return file_name_list: targetlist paths
    """

    # load OCR model
    ocr_model = ocr_model_config(checkpoint=ocr_weights_path)

    # Initialize model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    from .OCR_siamese_utils.siamese_unified.bit_pytorch.models import \
        KNOWN_MODELS

    model = KNOWN_MODELS["BiT-M-R50x1"](head_size=num_classes, zero_head=True)

    # Load weights
    weights = torch.load(weights_path, map_location="cpu")
    weights = weights["model"] if "model" in weights.keys() else weights
    new_state_dict = OrderedDict()
    for k, v in weights.items():
        if k.startswith("module"):
            name = k.split("module.")[1]
        else:
            name = k
        new_state_dict[name] = v

    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    #     Prediction for targetlists
    logo_feat_list = []
    file_name_list = []

    for target in tqdm(os.listdir(targetlist_path)):
        if target.startswith("."):  # skip hidden files
            continue
        for logo_path in os.listdir(os.path.join(targetlist_path, target)):
            if (
                logo_path.endswith(".png")
                or logo_path.endswith(".jpeg")
                or logo_path.endswith(".jpg")
                or logo_path.endswith(".PNG")
                or logo_path.endswith(".JPG")
                or logo_path.endswith(".JPEG")
            ):
                if logo_path.startswith("loginpage") or logo_path.startswith(
                    "homepage"
                ):  # skip homepage/loginpage
                    continue
                logo_feat_list.append(
                    pred_siamese_OCR(
                        img=os.path.join(targetlist_path, target, logo_path),
                        model=model,
                        ocr_model=ocr_model,
                        grayscale=grayscale,
                    )
                )
                file_name_list.append(
                    str(os.path.join(targetlist_path, target, logo_path))
                )

    return model, ocr_model, np.asarray(logo_feat_list), np.asarray(file_name_list)


def phishpedia_config_OCR_easy(
    num_classes: int, weights_path: str, ocr_weights_path: str
):
    # load OCR model
    ocr_model = ocr_model_config(checkpoint=ocr_weights_path)

    # Initialize model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    from .OCR_siamese_utils.siamese_unified.bit_pytorch.models import \
        KNOWN_MODELS

    model = KNOWN_MODELS["BiT-M-R50x1"](head_size=num_classes, zero_head=True)

    # Load weights
    weights = torch.load(weights_path, map_location="cpu")
    weights = weights["model"] if "model" in weights.keys() else weights
    new_state_dict = OrderedDict()
    for k, v in weights.items():
        if k.startswith("module"):
            name = k.split("module.")[1]
        else:
            name = k
        new_state_dict[name] = v

    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    return model, ocr_model


def phishpedia_classifier(
    pred_classes,
    pred_boxes,
    domain_map_path: str,
    model,
    logo_feat_list,
    file_name_list,
    shot_path: str,
    url: str,
    ts: float,
):
    """
    Run siamese
    :param pred_classes: torch.Tensor/np.ndarray Nx1 predicted box types
    :param pred_boxes: torch.Tensor/np.ndarray Nx4 predicted box coords
    :param domain_map_path: path to domain map dict
    :param model: siamese model
    :param logo_feat_list: targetlist embeddings
    :param file_name_list: targetlist paths
    :param shot_path: path to image
    :param url: url
    :param ts: siamese threshold
    :return pred_target
    :return coord: coordinate for matched logo
    """
    # targetlist domain list
    with open(domain_map_path, "rb") as handle:
        domain_map = pickle.load(handle)

    # look at boxes for logo class only
    logo_boxes = pred_boxes[pred_classes == 0]
    matched_target, matched_domain, matched_coord, this_conf = None, None, None, None

    # run logo matcher
    if len(logo_boxes) > 0:
        # siamese prediction for logo box
        for i, coord in enumerate(logo_boxes):
            min_x, min_y, max_x, max_y = coord
            bbox = [float(min_x), float(min_y), float(max_x), float(max_y)]
            matched_target, matched_domain, this_conf = siamese_inference(
                model,
                domain_map,
                logo_feat_list,
                file_name_list,
                shot_path,
                bbox,
                t_s=ts,
                grayscale=False,
            )

            # domain matcher to avoid FP
            if matched_target is not None:
                matched_coord = coord
                # if tldextract.extract(url).domain + '.' + tldextract.extract(url).suffix not in matched_domain:
                if tldextract.extract(url).domain not in matched_domain:
                    # avoid fp due to godaddy domain parking, ignore webmail provider (ambiguous)
                    if (
                        matched_target == "GoDaddy"
                        or matched_target == "Webmail Provider"
                        or matched_target == "Government of the United Kingdom"
                    ):
                        matched_target = None  # ignore the prediction
                        matched_domain = None  # ignore the prediction
                else:  # benign, real target
                    matched_target = None  # ignore the prediction
                    matched_domain = None  # ignore the prediction
                break
            break  # only look at 1st logo

    return brand_converter(matched_target), matched_coord, this_conf


def phishpedia_classifier_OCR(
    pred_classes,
    pred_boxes,
    domain_map: dict,
    model,
    ocr_model,
    logo_feat_list,
    file_name_list,
    shot_path: str,
    domain: str,
    ts: float,
):
    """
    Run siamese
    :param pred_classes: torch.Tensor/np.ndarray Nx1 predicted box types
    :param pred_boxes: torch.Tensor/np.ndarray Nx4 predicted box coords
    :param domain_map: domain map dict
    :param model: siamese model
    :param ocr_model: ocr model
    :param logo_feat_list: targetlist embeddings
    :param file_name_list: targetlist paths
    :param shot_path: path to image
    :param domain: domain
    :param ts: siamese threshold
    :return pred_target
    :return coord: coordinate for matched logo
    """

    # look at boxes for logo class only
    logo_boxes = pred_boxes[pred_classes == 0]
    matched_target, matched_domain, matched_coord, this_conf = None, None, None, None

    # run logo matcher
    if len(logo_boxes) > 0:
        # siamese prediction for logo box
        for i, coord in enumerate(logo_boxes):
            min_x, min_y, max_x, max_y = coord
            bbox = [float(min_x), float(min_y), float(max_x), float(max_y)]
            matched_target, matched_domain, this_conf = siamese_inference_OCR(
                model,
                ocr_model,
                domain_map,
                logo_feat_list,
                file_name_list,
                shot_path,
                bbox,
                t_s=ts,
                grayscale=False,
            )

            # domain matcher to avoid FP
            if matched_target is not None:
                matched_coord = coord
                # if tldextract.extract(url).domain+ '.'+tldextract.extract(url).suffix not in matched_domain:
                if domain not in matched_domain:
                    # avoid fp due to godaddy domain parking, ignore webmail provider (ambiguous)
                    if (
                        matched_target == "GoDaddy"
                        or matched_target == "Webmail Provider"
                        or matched_target == "Government of the United Kingdom"
                    ):
                        matched_target = None  # ignore the prediction
                        matched_domain = None  # ignore the prediction
                else:  # benign, real target
                    matched_target = None  # ignore the prediction
                    matched_domain = None  # ignore the prediction
                break  # break if target is matched
            break  # only look at 1st logo

    return brand_converter(matched_target), matched_coord, this_conf


def phishpedia_classifier_logo(
    logo_boxes,
    domain_map_path: str,
    model,
    logo_feat_list,
    file_name_list,
    shot_path: str,
    url: str,
    ts: float,
):
    """
    Run siamese
    :param logo_boxes: torch.Tensor/np.ndarray Nx4 logo box coords
    :param domain_map_path: path to domain map dict
    :param model: siamese model
    :param logo_feat_list: targetlist embeddings
    :param file_name_list: targetlist paths
    :param shot_path: path to image
    :param url: url
    :param ts: siamese threshold
    :return pred_target
    :return coord: coordinate for matched logo
    """
    # targetlist domain list
    with open(domain_map_path, "rb") as handle:
        domain_map = pickle.load(handle)

    print("number of logo boxes:", len(logo_boxes))
    matched_target, matched_domain, matched_coord, this_conf = None, None, None, None

    if len(logo_boxes) > 0:
        # siamese prediction for logo box
        for i, coord in enumerate(logo_boxes):
            min_x, min_y, max_x, max_y = coord
            bbox = [float(min_x), float(min_y), float(max_x), float(max_y)]
            matched_target, matched_domain, this_conf = siamese_inference(
                model,
                domain_map,
                logo_feat_list,
                file_name_list,
                shot_path,
                bbox,
                t_s=ts,
                grayscale=False,
            )

            # domain matcher to avoid FP
            if matched_target is not None:
                matched_coord = coord
                # if tldextract.extract(url).domain + '.' + tldextract.extract(url).suffix not in matched_domain:
                if tldextract.extract(url).domain not in matched_domain:
                    # avoid fp due to godaddy domain parking, ignore webmail provider (ambiguous)
                    if (
                        matched_target == "GoDaddy"
                        or matched_target == "Webmail Provider"
                        or matched_target == "Government of the United Kingdom"
                    ):
                        matched_target = None  # ignore the prediction
                        matched_domain = None  # ignore the prediction
                else:  # benign, real target
                    matched_target = None  # ignore the prediction
                    matched_domain = None  # ignore the prediction
                break  # break if target is matched
            break

    return brand_converter(matched_target), matched_coord, this_conf
