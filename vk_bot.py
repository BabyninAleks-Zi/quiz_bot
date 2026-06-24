import os

import vk_api
from dotenv import load_dotenv
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from quiz_parser import load_quiz_questions
from utils.database import connect_to_database
from utils.quiz import (
    CORRECT_ANSWER_MESSAGE,
    NEW_QUESTION_BUTTON,
    NO_CURRENT_QUESTION_MESSAGE,
    REPORT_BUTTON,
    SCORE_BUTTON,
    SURRENDER_BUTTON,
    VK_PLATFORM,
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


def get_keyboard(show_report_button=False):
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button(NEW_QUESTION_BUTTON, color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(SURRENDER_BUTTON, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(SCORE_BUTTON, color=VkKeyboardColor.SECONDARY)
    if show_report_button:
        keyboard.add_line()
        keyboard.add_button(REPORT_BUTTON, color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def send_message(vk, peer_id, text, show_report_button=False):
    vk.messages.send(
        peer_id=peer_id,
        random_id=get_random_id(),
        keyboard=get_keyboard(show_report_button),
        message=text,
    )


def handle_new_question_request(vk, peer_id, redis_database, show_report_button=False):
    question_id = get_random_question_id(redis_database)
    if not question_id:
        raise RuntimeError("Вопросы не найдены")

    question = get_quiz_question(redis_database, question_id)
    if not question:
        raise RuntimeError("Вопрос не найден в Redis")

    save_current_question(redis_database, VK_PLATFORM, peer_id, question_id)
    send_message(vk, peer_id, question["question"], show_report_button)


def handle_solution_attempt(vk, peer_id, user_answer, redis_database):
    question_id = get_current_question_id(redis_database, VK_PLATFORM, peer_id)

    if not question_id:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    question = get_quiz_question(redis_database, question_id)
    if not question:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    correct_answer = question["answer"]

    if is_correct_answer(user_answer, correct_answer):
        add_answer_attempt(redis_database, VK_PLATFORM, peer_id, is_correct=True)
        clear_current_question(redis_database, VK_PLATFORM, peer_id)
        send_message(vk, peer_id, CORRECT_ANSWER_MESSAGE)
        return

    add_answer_attempt(redis_database, VK_PLATFORM, peer_id, is_correct=False)
    send_message(vk, peer_id, WRONG_ANSWER_MESSAGE)


def handle_surrender(vk, peer_id, redis_database):
    question_id = get_current_question_id(redis_database, VK_PLATFORM, peer_id)

    if not question_id:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    question = get_quiz_question(redis_database, question_id)
    if not question:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    correct_answer = question["answer"]
    short_answer = get_short_answer(correct_answer)
    save_surrendered_question(redis_database, VK_PLATFORM, peer_id, question_id)
    send_message(
        vk,
        peer_id,
        f"Правильный ответ: {short_answer}",
        show_report_button=True,
    )
    handle_new_question_request(vk, peer_id, redis_database, show_report_button=True)


def handle_score_request(vk, peer_id, redis_database):
    score = get_user_score(redis_database, VK_PLATFORM, peer_id)
    send_message(vk, peer_id, format_score_message(score))


def handle_question_report(vk, peer_id, redis_database):
    question_id = report_last_surrendered_question(redis_database, VK_PLATFORM, peer_id)

    if not question_id:
        send_message(vk, peer_id, "Сначала нажмите «Сдаться», чтобы выбрать вопрос для жалобы.")
        return

    send_message(vk, peer_id, "Спасибо! Я запомнил, что этот вопрос нужно проверить.")


def handle_message(vk, message, redis_database):
    peer_id = message["peer_id"]
    user_text = message["text"]

    if user_text == NEW_QUESTION_BUTTON:
        handle_new_question_request(vk, peer_id, redis_database)
        return

    if user_text == SURRENDER_BUTTON:
        handle_surrender(vk, peer_id, redis_database)
        return

    if user_text == SCORE_BUTTON:
        handle_score_request(vk, peer_id, redis_database)
        return

    if user_text == REPORT_BUTTON:
        handle_question_report(vk, peer_id, redis_database)
        return

    handle_solution_attempt(vk, peer_id, user_text, redis_database)


def run_bot():
    load_dotenv()

    token = os.environ.get("VK_TOKEN")
    group_id = os.environ.get("VK_GROUP_ID")
    if not token:
        raise RuntimeError("Добавьте VK_TOKEN в .env")
    if not group_id:
        raise RuntimeError("Добавьте VK_GROUP_ID в .env")

    try:
        group_id = int(group_id)
    except ValueError:
        raise RuntimeError("VK_GROUP_ID в .env должен быть числом")

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

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        message = event.object.message
        if message["out"]:
            continue

        handle_message(vk, message, redis_database)


if __name__ == "__main__":
    run_bot()
