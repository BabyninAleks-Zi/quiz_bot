import os
import re
from enum import IntEnum
from random import choice

import redis
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, Filters, MessageHandler, Updater

from quiz_parser import load_quiz_questions


QUIZ_KEYBOARD = [
    ["Новый вопрос", "Сдаться"],
    ["Мой счёт"],
]
NEW_QUESTION_BUTTON = "Новый вопрос"
NEW_QUESTION_PATTERN = f"^{re.escape(NEW_QUESTION_BUTTON)}$"
SURRENDER_BUTTON = "Сдаться"
SURRENDER_PATTERN = f"^{re.escape(SURRENDER_BUTTON)}$"
CORRECT_ANSWER_MESSAGE = (
    "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»"
)
WRONG_ANSWER_MESSAGE = "Неправильно… Попробуешь ещё раз?"
NO_CURRENT_QUESTION_MESSAGE = "Нажми «Новый вопрос», чтобы начать викторину."


class BotState(IntEnum):
    ANSWERING = 1


def get_database_connection():
    redis_password = os.environ.get("REDIS_PASSWORD") or None

    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=redis_password,
        decode_responses=True,
    )


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
    context.bot_data["redis_database"].set(f"telegram:{chat_id}:question", question)

    update.message.reply_text(
        question,
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def get_short_answer(answer):
    answer = answer.strip(" .\"'«»")
    short_answer = re.split(r"[.(]", answer, maxsplit=1)[0]
    return short_answer.strip()


def normalize_answer(answer):
    answer = " ".join(answer.split())
    answer = answer.strip(" .,!?:;\"'«»")
    return answer.lower().replace("ё", "е")


def is_correct_answer(user_answer, correct_answer):
    short_answer = get_short_answer(correct_answer)
    return normalize_answer(user_answer) == normalize_answer(short_answer)


def handle_solution_attempt(update, context):
    chat_id = update.message.chat_id
    question = context.bot_data["redis_database"].get(f"telegram:{chat_id}:question")

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
    question = context.bot_data["redis_database"].get(f"telegram:{chat_id}:question")

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

    telegram_token = os.environ.get("TG_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError("Set TG_TOKEN in .env")

    quiz_questions = load_quiz_questions()
    if not quiz_questions:
        raise RuntimeError("Questions were not found")

    redis_database = get_database_connection()
    redis_database.ping()

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

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
