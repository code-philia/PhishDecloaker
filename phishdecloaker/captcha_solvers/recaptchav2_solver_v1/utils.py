import random
import time


def saveFile(content, filename):
    with open(filename, "wb") as handle:
        for data in content.iter_content():
            handle.write(data)


def divide_image(img, gw=3, gh=3):
    w, h, _ = img.shape

    tw = w // gw
    th = h // gh

    images = [
        img[x : x + tw, y : y + th] for x in range(0, w, tw) for y in range(0, h, th)
    ]

    return images


def saveInstructions(instructions, image, w, h, folder):
    with open(folder + "/instructions.txt", "a+") as f:
        f.write(
            "{}: {} {} '{}'\n".format(image, w, h, instructions.replace("\n", " # "))
        )


def saveLabelledInstructions(
    instructions, image, w, h, labels, success, file="images/labelled/labelled2.txt"
):
    with open(file, "a+") as f:
        f.write(
            "{}: {} {} '{}' {} {}\n".format(
                image, w, h, instructions.replace("\n", " # "), labels, success
            )
        )


def equal_dicts(d1, d2, ignore_keys):
    d1_filtered = {k: v for k, v in d1.items() if k not in ignore_keys}
    d2_filtered = {k: v for k, v in d2.items() if k not in ignore_keys}
    return d1_filtered == d2_filtered


def get_clicks(detection, gw, gh, img_shape, detector):
    w, h, c = img_shape
    clicks = set()

    cw = w / gw
    ch = h / gh

    l, t, r, b = detection[2]

    l = (l / detector.W) * w
    t = (t / detector.H) * h
    r = (r / detector.W) * w
    b = (b / detector.H) * h

    l, r = (l + 5) / cw, (r - 5) / cw
    t, b = (t + 5) / ch, (b - 5) / ch

    for i in range(gw):
        for j in range(gh):
            if not (i + 1 <= l or i > r or j + 1 <= t or j > b):
                clicks.add(j * gh + i)
    return clicks


def map_objs_to_cells(img, objects, gw, gh):
    w, h, _ = img.shape
    clicks = []

    cw = w / gw
    ch = h / gh

    for obj in objects:
        l, t, r, b, _ = obj
        l, r = l / cw, r / cw
        t, b = t / ch, b / ch

        for i in range(gw):
            for j in range(gh):
                if not (i + 1 <= l or i > r or j + 1 <= t or j > b):
                    clicks.append(j * gh + i)

    clicks = sorted(set(clicks))

    return clicks


def random_sleep(amount):
    time.sleep(amount * (1 + random.uniform(-0.2, 0.2)))
