import re
import time

from playwright.sync_api import Page


def visit_url(page: Page, orig_url, popup=False, sleep=False):
    """
    Visit a URL
    :param page: playwright Page
    :param orig_url: URL to visit
    :param popup: click popup window or not
    :param sleep: need sleep time or not
    :return: load url successful or not
    """
    try:
        page.goto(orig_url, wait_until="domcontentloaded")
        if sleep:
            time.sleep(2)
        if popup:
            click_popup(page)
        return True, page
    except Exception as e:
        print(f"visit_url error: {e}")
        return True, page


def get_page_text(page: Page):
    """
    get body text from html
    :param driver: chromdriver
    :return: text
    """
    text = ""
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception as e:
        print(f"get_page_text error: {e}")

    if not text:
        try:
            text = page.content()
        except:
            pass

    return text


def click_popup(page: Page):
    """
    Click unexpected popup (accpet terms condditions, close alerts etc.)
    :return:
    """
    keyword_list = [
        "Allow all cookies",
        "Accept Cookies",
        "Accept",
        "Accept all cookies",
        "Accept and continue",
        "Continue",
        "I accept",
        "OK",
        "AGREE",
        "close",
        "Close",
        "accept",
        "Accept all",
        "I agree",
        "I AGREE",
        "Allow everyone",
        "Enter Now",
        "Confirm selection",
        "I understand",
    ]

    for button_text in keyword_list:
        try:
            page.get_by_text(re.compile(button_text, re.IGNORECASE)).click(force=True)
        except:
            continue


def click_text(page: Page, text: str):
    """
    click the text's region
    :param text:
    :return:
    """
    try:
        time.sleep(1)
        page.get_by_text(re.compile(text, re.IGNORECASE)).click(force=True)
        time.sleep(2)  # wait until website is completely loaded
        click_popup(page)
    except Exception as e:
        print(e)


def click_point(page: Page, x, y):
    """
    click on coordinate (x,y)
    :param x:
    :param y:
    :return:
    """
    try:
        page.mouse.click(x, y)
    except Exception as e:
        print(e)


def writetxt(txtpath, contents):
    """
    write into txt file with encoding utf-8
    :param txtpath:
    :param contents: text to write
    :return:
    """
    with open(txtpath, "w", encoding="utf-8") as fw:
        fw.write(contents)
