from pathlib import Path
import re


QUESTIONS_DIR = Path("docs/quiz-questions")


def split_text_to_blocks(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text)
    return [block.strip() for block in blocks if block.strip()]


def remove_title(block):
    parts = block.split(":", 1)
    if len(parts) < 2:
        return ""

    return parts[1].strip()


def clean_question(question):
    question = re.sub(r"^(?:\[[^\]]+\]\s*)+", "", question)
    return question.strip()


def parse_quiz_file(file_path):
    quiz_questions = {}

    text = file_path.read_text(encoding="koi8-r")
    blocks = split_text_to_blocks(text)

    for block_index, block in enumerate(blocks):
        if not block.startswith("Вопрос "):
            continue

        if block_index + 1 >= len(blocks):
            continue

        answer_block = blocks[block_index + 1]
        if not answer_block.startswith("Ответ:"):
            continue

        question = clean_question(remove_title(block))
        answer = remove_title(answer_block)

        if question and answer:
            quiz_questions[question] = answer

    return quiz_questions


def load_quiz_questions(questions_dir=QUESTIONS_DIR):
    quiz_questions = {}

    if not questions_dir.exists():
        raise FileNotFoundError(f"Questions directory not found: {questions_dir}")

    for file_path in questions_dir.glob("*.txt"):
        file_questions = parse_quiz_file(file_path)
        quiz_questions.update(file_questions)

    return quiz_questions


if __name__ == "__main__":
    questions = load_quiz_questions()

    if not questions:
        raise RuntimeError("Questions were not found")
