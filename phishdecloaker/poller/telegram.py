import base64
import io

import telebot


def create_poll(bot: telebot.TeleBot, group_id: str, crawl_mode: str, sample: dict):
    domain = sample.get("domain", None)
    sample_id = str(sample.get("_id", None))
    phish_pred = sample.get("phish_pred", False)
    phish_target = sample.get("phish_target", None)
    has_captcha = sample.get("has_captcha", False)
    captcha_type = sample.get("captcha_type", None)
    captcha_solved = sample.get("captcha_solved", False)
    captcha_solved = "🟩" if captcha_solved else "🟥"

    if crawl_mode == "BASELINE":
        verdicts = ["🟩" if sample.get(f"group_{i+1}", False) else "🟥" for i in range(5)]
        screenshot = None
        for i in range(4, -1, -1):
            screenshot = (
                str(sample.get(f"screenshot_{i+1}"))
                .replace("data:image/png;base64,", "", 1)
                .replace("None", "", 1)
            )
            if screenshot:
                break

    elif crawl_mode == "CAPTCHA":
        verdicts = ["🟩" if phish_pred else "🟥"]
        screenshot = str(sample.get("screenshot", "")).replace(
            "data:image/png;base64,", "", 1
        )

    caption = [f"https://{domain}"]
    if has_captcha:
        caption.append(f"<b>CAPTCHA:</b> {captcha_type}, solved: {captcha_solved}")
    if phish_pred:
        caption.append(f"<b>Target:</b> {phish_target}, verdicts: {''.join(verdicts)}")

    captcha_poll = True if has_captcha else False
    question = (
        f"[{crawl_mode[0]}:{sample_id}]\nCAPTCHA? Phishing?"
        if captcha_poll
        else f"[{crawl_mode[0]}:{sample_id}]\nPhishing?"
    )
    options = (
        ["No, No", "No, Yes", "Yes, No", "Yes, Yes"] if captcha_poll else ["Yes", "No"]
    )

    if screenshot:
        screenshot = io.BytesIO(base64.b64decode(screenshot))
        screenshot = telebot.types.InputFile(screenshot)
        bot.send_photo(
            chat_id=group_id,
            photo=screenshot,
            caption="\n".join(caption),
            parse_mode="HTML",
            disable_notification=True,
        )
    else:
        bot.send_message(
            chat_id=group_id,
            text="\n".join(caption),
            parse_mode="HTML",
            disable_notification=True,
        )

    poll_id = bot.send_poll(
        chat_id=group_id, question=question, options=options, disable_notification=True
    ).message_id

    return poll_id


def report_hourly_stats(bot: telebot.TeleBot, group_id: str, stats: dict):
    monitoring = int(stats.get("monitoring", 0))
    active = int(stats.get("active", 0))
    blacklisted_by_gsb = int(stats.get("blacklisted_by_gsb", 0))
    blacklisted_by_ms = int(stats.get("blacklisted_by_ms", 0))
    text = [
        "<b>Stats</b>",
        f"<b>Active:</b> {active}/{monitoring}",
        f"<b>GSB Blacklist:</b> {blacklisted_by_gsb}/{monitoring}",
        f"<b>MS Blacklist:</b> {blacklisted_by_ms}/{monitoring}",
    ]
    bot.send_message(
        chat_id=group_id,
        text="\n".join(text),
        parse_mode="HTML",
        disable_notification=True,
    )


def report_daily_stats(bot: telebot.TeleBot, group_id: str, stats: dict):
    monitoring = int(stats.get("monitoring", 0))
    active = int(stats.get("active", 0))
    zero_days = int(stats.get("zero_days", 0))
    blacklisted_by_vt = int(stats.get("blacklisted_by_vt", 0))
    text = [
        "<b>Stats</b>",
        f"<b>Active:</b> {active}/{monitoring}",
        f"<b>0-days:</b> {zero_days}/{monitoring}",
        f"<b>VT Blacklist:</b> {blacklisted_by_vt}/{monitoring}",
    ]
    bot.send_message(
        chat_id=group_id,
        text="\n".join(text),
        parse_mode="HTML",
        disable_notification=True,
    )


def report_captcha(bot: telebot.TeleBot, group_id: str, domain: str):
    bot.send_message(
        chat_id=group_id,
        text=f"⚠️ May have CAPTCHA: https://{domain}",
        parse_mode="HTML",
        disable_notification=True,
    )
