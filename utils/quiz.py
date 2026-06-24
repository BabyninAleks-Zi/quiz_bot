import json
import random
import re


NEW_QUESTION_BUTTON = "Новый вопрос"
SURRENDER_BUTTON = "Сдаться"
SCORE_BUTTON = "Мой счёт"
REPORT_BUTTON = "Вопрос составлен неверно"
TG_PLATFORM = "tg"
VK_PLATFORM = "vk"
QUESTION_IDS_KEY = "question_ids"
QUESTION_REPORTS_KEY = "question_reports"

CORRECT_ANSWER_MESSAGE = (
    "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»"
)
WRONG_ANSWER_MESSAGE = "Неправильно… Попробуешь ещё раз?"
NO_CURRENT_QUESTION_MESSAGE = "Нажми «Новый вопрос», чтобы начать викторину."


def has_quiz_questions(redis_database):
    return redis_database.llen(QUESTION_IDS_KEY) > 0


def save_quiz_questions(redis_database, quiz_questions):
    temporary_question_ids_key = f"{QUESTION_IDS_KEY}_tmp"
    redis_database.delete(temporary_question_ids_key)

    pipeline = redis_database.pipeline()
    for question_number, (question, answer) in enumerate(quiz_questions.items(), 1):
        question_id = f"question_{question_number}"
        question_data = {
            "question": question,
            "answer": answer,
        }
        pipeline.set(question_id, json.dumps(question_data, ensure_ascii=False))
        pipeline.rpush(temporary_question_ids_key, question_id)

        if question_number % 1000 == 0:
            pipeline.execute()

    pipeline.execute()
    redis_database.delete(QUESTION_IDS_KEY)
    redis_database.rename(temporary_question_ids_key, QUESTION_IDS_KEY)


def get_random_question_id(redis_database):
    questions_count = redis_database.llen(QUESTION_IDS_KEY)
    if not questions_count:
        return None

    question_index = random.randrange(questions_count)
    return redis_database.lindex(QUESTION_IDS_KEY, question_index)


def get_quiz_question(redis_database, question_id):
    question_data = redis_database.get(question_id)
    if not question_data:
        return None

    return json.loads(question_data)


def get_user_key(platform, chat_id):
    return f"user_{platform}_{chat_id}"


def get_user_state(redis_database, platform, chat_id):
    user_state = {
        "last_asked_question": None,
        "last_surrendered_question": None,
        "correct_answers": 0,
        "wrong_answers": 0,
    }
    saved_user_state = redis_database.get(get_user_key(platform, chat_id))
    if not saved_user_state:
        return user_state

    user_state.update(json.loads(saved_user_state))
    return user_state


def save_user_state(redis_database, platform, chat_id, user_state):
    redis_database.set(
        get_user_key(platform, chat_id),
        json.dumps(user_state, ensure_ascii=False),
    )


def save_current_question(redis_database, platform, chat_id, question_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    user_state["last_asked_question"] = question_id
    save_user_state(redis_database, platform, chat_id, user_state)


def get_current_question_id(redis_database, platform, chat_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    return user_state["last_asked_question"]


def clear_current_question(redis_database, platform, chat_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    user_state["last_asked_question"] = None
    save_user_state(redis_database, platform, chat_id, user_state)


def save_surrendered_question(redis_database, platform, chat_id, question_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    user_state["last_surrendered_question"] = question_id
    save_user_state(redis_database, platform, chat_id, user_state)


def report_last_surrendered_question(redis_database, platform, chat_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    question_id = user_state["last_surrendered_question"]
    if not question_id:
        return None

    redis_database.hincrby(QUESTION_REPORTS_KEY, question_id, 1)
    user_state["last_surrendered_question"] = None
    save_user_state(redis_database, platform, chat_id, user_state)
    return question_id


def add_answer_attempt(redis_database, platform, chat_id, is_correct):
    user_state = get_user_state(redis_database, platform, chat_id)

    if is_correct:
        user_state["correct_answers"] += 1
    else:
        user_state["wrong_answers"] += 1

    save_user_state(redis_database, platform, chat_id, user_state)


def get_user_score(redis_database, platform, chat_id):
    user_state = get_user_state(redis_database, platform, chat_id)
    return {
        "correct_answers": user_state["correct_answers"],
        "wrong_answers": user_state["wrong_answers"],
    }


def format_score_message(score):
    return (
        "Ваш счёт:\n"
        f"Правильных ответов: {score['correct_answers']}\n"
        f"Неправильных попыток: {score['wrong_answers']}"
    )


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
