import os
from random import choice

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

from quiz_parser import load_quiz_questions


QUIZ_KEYBOARD = [
    ["Новый вопрос", "Сдаться"],
    ["Мой счёт"],
]
NEW_QUESTION_BUTTON = "Новый вопрос"


def get_keyboard():
    return ReplyKeyboardMarkup(QUIZ_KEYBOARD, resize_keyboard=True)


def start(update, context):
    update.message.reply_text(
        "Привет! Я бот для викторины.",
        reply_markup=get_keyboard(),
    )


def send_new_question(update, context):
    question = choice(context.bot_data["question_texts"])
    update.message.reply_text(
        question,
        reply_markup=get_keyboard(),
    )


def handle_message(update, context):
    if update.message.text == NEW_QUESTION_BUTTON:
        send_new_question(update, context)
        return

    update.message.reply_text(
        update.message.text,
        reply_markup=get_keyboard(),
    )


def run_bot():
    load_dotenv()

    telegram_token = os.environ.get("TG_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("Set TG_TOKEN in .env")

    quiz_questions = load_quiz_questions()
    if not quiz_questions:
        raise RuntimeError("Questions were not found")

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data["quiz_questions"] = quiz_questions
    dispatcher.bot_data["question_texts"] = list(quiz_questions.keys())

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
