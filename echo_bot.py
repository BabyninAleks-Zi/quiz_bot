import os

from dotenv import load_dotenv
from telegram.ext import Filters, MessageHandler, Updater


def echo(update, context):
    update.message.reply_text(update.message.text)


def run_bot():
    load_dotenv()

    telegram_token = os.environ.get("TG_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("Set TG_TOKEN in .env")

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(MessageHandler(Filters.text, echo))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
