import uuid
import random

from playwright.sync_api import Page, Route

PERMISSION_LIST = [
    'geolocation',
    'midi',
    'midi-sysex',
    'notifications',
    'camera',
    'microphone',
    'background-sync',
    'ambient-light-sensor',
    'accelerometer',
    'gyroscope',
    'magnetometer',
    'accessibility-events',
    'clipboard-read',
    'clipboard-write',
    'payment-handler'
]


def ignore_redirects(route: Route):
    try:
        response = route.fetch(max_redirects=0)
        body = response.body()
        headers = response.headers
        route.fulfill(response=response, body=body, headers=headers)
    except Exception as e:
        print(f"\t[>] ignore_redirects error: {e}")
        route.abort("blockedbyclient")


def disable_cookies(route: Route):
    try:
        response = route.fetch()
        body = response.body()
        headers = response.headers
        try: del headers['set-cookie']
        except: pass
        try: del headers['Set-Cookie']
        except: pass
        route.fulfill(response=response, body=body, headers=headers)
    except Exception as e:
        print(f"\t[>] disable_cookies error: {e}")
        route.abort("blockedbyclient")
    

def random_user_agent():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.3",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.1",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.1",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.3",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Agency/93.8.2357.5",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.3",
    ])


def random_referer(domain: str):
    return f"https://{uuid.uuid4().hex}.{domain}" 


def random_mouse_movement(page: Page):
    for _ in range(3):
        x = random.randrange(0, 1920)
        y = random.randrange(0, 1080)
        steps = random.randrange(0, 20)
        page.mouse.move(x=x, y=y, steps=steps)
        page.mouse.click(x=x, y=y, delay=200, click_count=2)