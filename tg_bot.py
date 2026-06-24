import os
import re
from enum import IntEnum

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
    REPORT_BUTTON,
    SCORE_BUTTON,
    SURRENDER_BUTTON,
    TG_PLATFORM,
    WRONG_ANSWER_MESSAGE,
    add_answer_attempt,
    clear_current_question,
    format_score_message,
    get_current_question_id,
    get_quiz_question,
    get_random_question_id,
    get_short_answer,
    get_user_score,
    has_quiz_questions,
    is_correct_answer,
    report_last_surrendered_question,
    save_current_question,
    save_quiz_questions,
    save_surrendered_question,
)


QUIZ_KEYBOARD = [
    [NEW_QUESTION_BUTTON, SURRENDER_BUTTON],
    [SCORE_BUTTON],
]
NEW_QUESTION_PATTERN = f"^{re.escape(NEW_QUESTION_BUTTON)}$"
SURRENDER_PATTERN = f"^{re.escape(SURRENDER_BUTTON)}$"
SCORE_PATTERN = f"^{re.escape(SCORE_BUTTON)}$"
REPORT_PATTERN = f"^{re.escape(REPORT_BUTTON)}$"


class BotState(IntEnum):
    ANSWERING = 1


def get_keyboard(show_report_button=False):
    keyboard = QUIZ_KEYBOARD.copy()
    if show_report_button:
        keyboard = [*keyboard, [REPORT_BUTTON]]

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def start(update, context):
    update.message.reply_text(
        "Привет! Я бот для викторины.",
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_new_question_request(update, context, show_report_button=False):
    question_id = get_random_question_id(context.bot_data["redis_database"])
    if not question_id:
        raise RuntimeError("Вопросы не найдены")

    question = get_quiz_question(context.bot_data["redis_database"], question_id)
    if not question:
        raise RuntimeError("Вопрос не найден в Redis")

    chat_id = update.message.chat_id
    save_current_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
        question_id,
    )

    update.message.reply_text(
        question["question"],
        reply_markup=get_keyboard(show_report_button),
    )
    return BotState.ANSWERING


def handle_solution_attempt(update, context):
    chat_id = update.message.chat_id
    question_id = get_current_question_id(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
    )

    if not question_id:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    question = get_quiz_question(context.bot_data["redis_database"], question_id)
    if not question:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    correct_answer = question["answer"]

    if is_correct_answer(update.message.text, correct_answer):
        add_answer_attempt(
            context.bot_data["redis_database"],
            TG_PLATFORM,
            chat_id,
            is_correct=True,
        )
        clear_current_question(context.bot_data["redis_database"], TG_PLATFORM, chat_id)
        update.message.reply_text(
            CORRECT_ANSWER_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    add_answer_attempt(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
        is_correct=False,
    )
    update.message.reply_text(
        WRONG_ANSWER_MESSAGE,
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_surrender(update, context):
    chat_id = update.message.chat_id
    question_id = get_current_question_id(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
    )

    if not question_id:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    question = get_quiz_question(context.bot_data["redis_database"], question_id)
    if not question:
        update.message.reply_text(
            NO_CURRENT_QUESTION_MESSAGE,
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    correct_answer = question["answer"]
    short_answer = get_short_answer(correct_answer)
    save_surrendered_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
        question_id,
    )
    update.message.reply_text(
        f"Правильный ответ: {short_answer}",
        reply_markup=get_keyboard(show_report_button=True),
    )
    return handle_new_question_request(update, context, show_report_button=True)


def handle_score_request(update, context):
    chat_id = update.message.chat_id
    score = get_user_score(context.bot_data["redis_database"], TG_PLATFORM, chat_id)
    update.message.reply_text(
        format_score_message(score),
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


def handle_question_report(update, context):
    chat_id = update.message.chat_id
    question_id = report_last_surrendered_question(
        context.bot_data["redis_database"],
        TG_PLATFORM,
        chat_id,
    )

    if not question_id:
        update.message.reply_text(
            "Сначала нажмите «Сдаться», чтобы выбрать вопрос для жалобы.",
            reply_markup=get_keyboard(),
        )
        return BotState.ANSWERING

    update.message.reply_text(
        "Спасибо! Я запомнил, что этот вопрос нужно проверить.",
        reply_markup=get_keyboard(),
    )
    return BotState.ANSWERING


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

    redis_database = connect_to_database(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=redis_port,
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=redis_db,
    )

    if not has_quiz_questions(redis_database):
        quiz_questions = load_quiz_questions()
        if not quiz_questions:
            raise RuntimeError("Вопросы не найдены")

        save_quiz_questions(redis_database, quiz_questions)

    updater = Updater(telegram_token)
    dispatcher = updater.dispatcher
    dispatcher.bot_data["redis_database"] = redis_database

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
                Filters.regex(SCORE_PATTERN),
                handle_score_request,
            ),
            MessageHandler(
                Filters.regex(REPORT_PATTERN),
                handle_question_report,
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
                    Filters.regex(SCORE_PATTERN),
                    handle_score_request,
                ),
                MessageHandler(
                    Filters.regex(REPORT_PATTERN),
                    handle_question_report,
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
