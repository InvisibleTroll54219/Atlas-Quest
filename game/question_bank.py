import json
import random
from functools import lru_cache
from pathlib import Path

from django.conf import settings


@lru_cache(maxsize=1)
def get_question_bank():
    path = Path(settings.BASE_DIR) / "data" / "questions.json"
    with path.open(encoding="utf-8") as question_file:
        questions = json.load(question_file)
    return questions


@lru_cache(maxsize=1)
def get_questions_by_id():
    return {question["id"]: question for question in get_question_bank()}


@lru_cache(maxsize=1)
def get_questions_by_level():
    questions_by_level = {}
    for question in get_question_bank():
        questions_by_level.setdefault(question["level"], {}).setdefault(
            question["fact_id"], []
        ).append(question)
    return questions_by_level


def get_levels():
    levels = {}
    for question in get_question_bank():
        level_index = question["level"]
        levels[level_index] = {
            "name": question["name"],
            "region": question["region"],
            "icon": question["icon"],
            "continent": question["continent"],
        }
    return [levels[index] for index in sorted(levels)]


def create_question_variant(fact):
    option_order = list(range(len(fact["options"])))
    random.shuffle(option_order)
    return {
        **fact,
        "options": [fact["options"][index] for index in option_order],
        "answer_indices": [
            option_order.index(index) for index in fact["answer_indices"]
        ],
    }
