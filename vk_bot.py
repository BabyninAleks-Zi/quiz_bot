import os
import re
from random import choice

import redis
import vk_api
from dotenv import load_dotenv
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from quiz_parser import load_quiz_questions


NEW_QUESTION_BUTTON = "Новый вопрос"
SURRENDER_BUTTON = "Сдаться"
CORRECT_ANSWER_MESSAGE = (
    "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»"
)
WRONG_ANSWER_MESSAGE = "Неправильно… Попробуешь ещё раз?"
NO_CURRENT_QUESTION_MESSAGE = "Нажми «Новый вопрос», чтобы начать викторину."


def get_database_connection():
    redis_password = os.environ.get("REDIS_PASSWORD") or None

    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        password=redis_password,
        decode_responses=True,
    )


def get_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button(NEW_QUESTION_BUTTON, color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(SURRENDER_BUTTON, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("Мой счёт", color=VkKeyboardColor.SECONDARY)
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
    redis_database.set(f"vk:{user_id}:question", question)
    send_message(vk, peer_id, question)


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


def handle_solution_attempt(vk, peer_id, user_id, user_answer, redis_database, quiz_questions):
    question = redis_database.get(f"vk:{user_id}:question")

    if not question:
        send_message(vk, peer_id, NO_CURRENT_QUESTION_MESSAGE)
        return

    correct_answer = quiz_questions[question]

    if is_correct_answer(user_answer, correct_answer):
        send_message(vk, peer_id, CORRECT_ANSWER_MESSAGE)
        return

    send_message(vk, peer_id, WRONG_ANSWER_MESSAGE)


def handle_surrender(vk, peer_id, user_id, redis_database, quiz_questions, question_texts):
    question = redis_database.get(f"vk:{user_id}:question")

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
        raise RuntimeError("Set VK_TOKEN in .env")
    if not group_id:
        raise RuntimeError("Set VK_GROUP_ID in .env")

    quiz_questions = load_quiz_questions()
    if not quiz_questions:
        raise RuntimeError("Questions were not found")

    redis_database = get_database_connection()
    redis_database.ping()

    vk_session = vk_api.VkApi(token=token)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, int(group_id))
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
