import os
from random import choice

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
    SCORE_BUTTON,
    SURRENDER_BUTTON,
    WRONG_ANSWER_MESSAGE,
    get_current_question,
    get_short_answer,
    is_correct_answer,
    save_current_question,
)


def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button(NEW_QUESTION_BUTTON, color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(SURRENDER_BUTTON, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(SCORE_BUTTON, color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def send_message(vk, peer_id, text):
    vk.messages.send(
        peer_id=peer_id,
        random_id=get_random_id(),
        keyboard=get_keyboard(),
        message=text,
    )


def handle_new_question_request(vk, peer_id, user_id, redis_database, question_texts):
    question = choice(question_texts)
    save_current_question(redis_database, "vk", user_id, question)
    send_message(vk, peer_id, question)


def handle_solution_attempt(vk, peer_id, user_id, user_answer, redis_database, quiz_questions):
    question = get_current_question(redis_database, "vk", user_id)

    if not question:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    correct_answer = quiz_questions[question]

    if is_correct_answer(user_answer, correct_answer):
        send_message(vk, peer_id, CORRECT_ANSWER_MESSAGE)
        return

    send_message(vk, peer_id, WRONG_ANSWER_MESSAGE)


def handle_surrender(vk, peer_id, user_id, redis_database, quiz_questions, question_texts):
    question = get_current_question(redis_database, "vk", user_id)

    if not question:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    correct_answer = quiz_questions[question]
    short_answer = get_short_answer(correct_answer)
    send_message(vk, peer_id, f"Правильный ответ: {short_answer}")
    handle_new_question_request(vk, peer_id, user_id, redis_database, question_texts)


def handle_message(vk, message, redis_database, quiz_questions, question_texts):
    peer_id = message["peer_id"]
    user_id = message["from_id"]
    user_text = message["text"]

    if user_text == NEW_QUESTION_BUTTON:
        handle_new_question_request(vk, peer_id, user_id, redis_database, question_texts)
        return

    if user_text == SURRENDER_BUTTON:
        handle_surrender(vk, peer_id, user_id, redis_database, quiz_questions, question_texts)
        return

    handle_solution_attempt(vk, peer_id, user_id, user_text, redis_database, quiz_questions)


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

    quiz_questions = load_quiz_questions()
    if not quiz_questions:
        raise RuntimeError("Вопросы не найдены")

    redis_database = connect_to_database()

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id)
    question_texts = list(quiz_questions.keys())

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        message = event.object.message
        if message["out"]:
            continue

        handle_message(vk, message, redis_database, quiz_questions, question_texts)


if __name__ == "__main__":
    run_bot()
