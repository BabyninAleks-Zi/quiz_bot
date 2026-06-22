import os

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater


QUIZ_KEYBOARD = [
    ["Новый вопрос", "Сдаться"],
    ["Мой счёт"],
]


def get_keyboard():
    return ReplyKeyboardMarkup(QUIZ_KEYBOARD, resize_keyboard=True)


def start(update, context):
    update.message.reply_text(
        "Привет! Я бот для викторины.",
        reply_markup=get_keyboard(),
    )


def echo(update, context):
    update.message.reply_text(
        update.message.text,
        reply_markup=get_keyboard(),
    )


def run_bot():
    load_dotenv()

    telegram_token = os.environ.get("TG_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("Set TG_TOKEN in .env")

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
