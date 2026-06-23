import os
import re
from enum import IntEnum
from random import choice

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.error import NetworkError
from telegram.ext import CommandHandler, ConversationHandler, Filters, MessageHandler, Updater

from quiz_parser import load_quiz_questions
from utils.database import connect_to_database
from utils.quiz import (
    CORRECT_ANSWER_MESSAGE,
    NEW_QUESTION_BUTTON,
    NO_CURRENT_QUESTION_MESSAGE,
    SCORE_BUTTON,
    SURRENDER_BUTTON,
    TG_PLATFORM,
    WRONG_ANSWER_MESSAGE,
    get_current_question,
    get_short_answer,
    is_correct_answer,
    save_current_question,
)


QUIZ_KEYBOARD = [
    [NEW_QUESTION_BUTTON, SURRENDER_BUTTON],
    [SCORE_BUTTON],
]
NEW_QUESTION_PATTERN = f"^{re.escape(NEW_QUESTION_BUTTON)}$"
SURRENDER_PATTERN = f"^{re.escape(SURRENDER_BUTTON)}$"


class BotState(IntEnum):
    ANSWERING = 1


def get_keyboard():
    return ReplyKeyboardMarkup(QUIZ_KEYBOARD, resize_keyboard=True)


def start(update, context):
    update.message.reply_text(
        "Привет! Я бот для викторины.",
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_new_question_request(update, context):
    question = choice(context.bot_data["question_texts"])
    chat_id = update.message.chat_id
    save_current_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
        question,
    )

    update.message.reply_text(
        question,
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_solution_attempt(update, context):
    chat_id = update.message.chat_id
    question = get_current_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
    )

    if not question:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    correct_answer = context.bot_data["quiz_questions"][question]

    if is_correct_answer(update.message.text, correct_answer):
        update.message.reply_text(
            CORRECT_ANSWER_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    update.message.reply_text(
        WRONG_ANSWER_MESSAGE,
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_surrender(update, context):
    chat_id = update.message.chat_id
    question = get_current_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
    )

    if not question:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    correct_answer = context.bot_data["quiz_questions"][question]
    short_answer = get_short_answer(correct_answer)
    update.message.reply_text(
        f"Правильный ответ: {short_answer}",
        reply_markup=get_keyboard(),
    )
    return handle_new_question_request(update, context)


def run_bot():
    load_dotenv()

    telegram_token = os.environ.get("TG_TOKEN")
    if not telegram_token:
        raise RuntimeError("Добавьте TG_TOKEN в .env")

    try:
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_db = int(os.environ.get("REDIS_DB", 0))
    except ValueError:
        raise RuntimeError("REDIS_PORT и REDIS_DB в .env должны быть числами")

    quiz_questions = load_quiz_questions()
    if not quiz_questions:
        raise RuntimeError("Вопросы не найдены")

    redis_database = connect_to_database(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=redis_port,
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=redis_db,
    )

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data["redis_database"] = redis_database
    dispatcher.bot_data["quiz_questions"] = quiz_questions
    dispatcher.bot_data["question_texts"] = list(quiz_questions.keys())

    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(
                Filters.regex(NEW_QUESTION_PATTERN),
                handle_new_question_request,
            ),
            MessageHandler(
                Filters.regex(SURRENDER_PATTERN),
                handle_surrender,
            ),
            MessageHandler(
                Filters.text & ~Filters.command,
                handle_solution_attempt,
            ),
        ],
        states={
            BotState.ANSWERING: [
                MessageHandler(
                    Filters.regex(NEW_QUESTION_PATTERN),
                    handle_new_question_request,
                ),
                MessageHandler(
                    Filters.regex(SURRENDER_PATTERN),
                    handle_surrender,
                ),
                MessageHandler(
                    Filters.text & ~Filters.command,
                    handle_solution_attempt,
                ),
            ],
        },
        fallbacks=[],
    )
    dispatcher.add_handler(conversation_handler)

    try:
        updater.start_polling()
        updater.idle()
    except NetworkError:
        raise SystemExit("Не удалось подключиться к Telegram API") from None


if __name__ == "__main__":
    run_bot()
