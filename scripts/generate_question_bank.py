#!/usr/bin/env python3
"""Build the compact runtime question bank from the geography fact source."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "data" / "facts.json"
OUTPUT_PATH = ROOT / "data" / "questions.json"


def build_question_bank():
    facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    questions = []
    seen_ids = set()
    for fact in facts:
        if fact["id"] in seen_ids:
            raise ValueError("Duplicate fact ID: {}".format(fact["id"]))
        seen_ids.add(fact["id"])
        correct_indices = (
            fact["answer_indices"]
            if "answer_indices" in fact
            else [fact["answer_index"]]
        )
        question = {
            key: value
            for key, value in fact.items()
            if key not in {"answer_index", "answer_indices"}
        }
        question.update(
            {
                "fact_id": fact["id"],
                "answer_indices": correct_indices,
            }
        )
        questions.append(question)
    return questions


if __name__ == "__main__":
    bank = build_question_bank()
    OUTPUT_PATH.write_text(
        "[\n  "
        + ",\n  ".join(
            json.dumps(question, ensure_ascii=False, separators=(",", ":"))
            for question in bank
        )
        + "\n]\n",
        encoding="utf-8",
    )
    print("Wrote {:,} distinct questions to {}".format(len(bank), OUTPUT_PATH))
