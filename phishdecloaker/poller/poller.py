import os
import time
import traceback

import telebot
from flask import Flask, Response, request, abort, jsonify

import telegram
from database import Database


DATABASE_URL = os.getenv("DATABASE_URL", None)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", None)
TELEGRAM_VOTERS = int(os.getenv("TELEGRAM_VOTERS", 0))
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", None)

database = Database(DATABASE_URL)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)
app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return Response(status=200)


@app.route(f"/{TELEGRAM_BOT_TOKEN}/", methods=["POST"])
def telegram_webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ""
    else:
        abort(403)


# Notifies users of newly detected phishing websites or solved/unsolved CAPTCHAs.
@app.route(f"/poll", methods=["POST"])
def poll():
    content: dict = request.json
    crawl_mode = content.get("crawl_mode", None)
    sample_id = content.get("sample_id", None)
    sample = database.get_sample(crawl_mode, sample_id)
    if not sample:
        raise Exception("Sample not found")
    message_id = telegram.create_poll(bot, TELEGRAM_GROUP_ID, crawl_mode, sample)
    database.update_poll_id(crawl_mode, sample_id, message_id)
    return Response(status=200)


# Notifies users of suspected captcha page.
@app.route(f"/captcha", methods=["POST"])
def captcha():
    content: dict = request.json
    domain = content.get("domain", None)
    telegram.report_captcha(bot, TELEGRAM_GROUP_ID, domain)
    return Response(status=200)


# Notifies users of hourly statistics
@app.route(f"/hourly_stats", methods=["POST"])
def hourly_stats():
    content: dict = request.json
    telegram.report_hourly_stats(bot, TELEGRAM_GROUP_ID, content)
    return Response(status=200)


# Notifies users of daily statistics
@app.route(f"/daily_stats", methods=["POST"])
def daily_stats():
    content: dict = request.json
    telegram.report_daily_stats(bot, TELEGRAM_GROUP_ID, content)
    return Response(status=200)


# Check bot connectivity
@bot.message_handler(commands=["ping"])
def start(message: telebot.types.Message):
    chat_id = str(message.chat.id)
    bot.send_message(chat_id, f"Listening. Group ID: {chat_id}")

    return Response(status=200)


# When a user votes on a poll.
@bot.poll_handler(func=lambda x: True)
def poll_answer(answer: telebot.types.Poll):
    sample_info: str = answer.question[
        answer.question.find("[") + 1 : answer.question.find("]")
    ]
    sample_info = sample_info.split(":")
    sample_id = sample_info[1]
    crawl_mode = "BASELINE" if sample_info[0] == "B" else "CAPTCHA"

    sample = database.get_sample(crawl_mode, sample_id)
    if not sample:
        return
    poll_id = int(sample.get("poll_id", None))
    try:
        bot.stop_poll(TELEGRAM_GROUP_ID, poll_id)
        options = answer.options

        for option in options:
            if option.voter_count:
                bot.send_message(
                    TELEGRAM_GROUP_ID,
                    f"🟩 Poll {sample_id} closed. Verdict: {option.text}",
                )
                database.update_ground_truth(crawl_mode, sample_id, option.text)
                return
    except:
        pass


def init_webhook():
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=TELEGRAM_WEBHOOK_URL, allowed_updates=[])


def handle_exception(e: Exception):
    print(traceback.print_exc())
    return jsonify(message=str(e)), 400


app.register_error_handler(Exception, handle_exception)


if __name__ == "__main__":
    init_webhook()
    app.run(host="0.0.0.0", port=8000, debug=True)
