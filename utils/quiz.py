import re


NEW_QUESTION_BUTTON = "Новый вопрос"
SURRENDER_BUTTON = "Сдаться"
SCORE_BUTTON = "Мой счёт"

CORRECT_ANSWER_MESSAGE = (
    "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»"
)
WRONG_ANSWER_MESSAGE = "Неправильно… Попробуешь ещё раз?"
NO_CURRENT_QUESTION_MESSAGE = "Нажми «Новый вопрос», чтобы начать викторину."


def save_current_question(redis_database, platform, user_id, question):
    redis_database.set(f"{platform}:{user_id}:question", question)


def get_current_question(redis_database, platform, user_id):
    return redis_database.get(f"{platform}:{user_id}:question")


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
