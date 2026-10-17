#!/usr/bin/env python3
"""Build a reproducible question-instance pool from the authored geography facts."""

import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "data" / "facts.json"
OUTPUT_PATH = ROOT / "data" / "questions.json"
PROMPT_FRAMES = (
    "{}",
    "Atlas check: {}",
    "Quick globe challenge: {}",
    "Expedition question: {}",
    "Map room: {}",
    "Navigator's quiz: {}",
    "On this leg of the journey: {}",
    "Test your world knowledge: {}",
)


def build_question_bank():
    facts = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    questions = []
    for fact in facts:
        for frame_index, frame in enumerate(PROMPT_FRAMES):
            for permutation_index, permutation in enumerate(
                itertools.permutations(range(len(fact["options"])))
            ):
                choices = [fact["options"][index] for index in permutation]
                questions.append(
                    {
                        "id": "{}-{:02d}-{:02d}".format(
                            fact["id"], frame_index, permutation_index
                        ),
                        "fact_id": fact["id"],
                        "level": fact["level"],
                        "name": fact["name"],
                        "region": fact["region"],
                        "icon": fact["icon"],
                        "prompt": frame.format(fact["prompt"]),
                        "options": choices,
                        "answer_index": permutation.index(fact["answer_index"]),
                        "explanation": fact["explanation"],
                    }
                )
    return questions


if __name__ == "__main__":
    bank = build_question_bank()
    OUTPUT_PATH.write_text(
        json.dumps(bank, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("Wrote {:,} question variants to {}".format(len(bank), OUTPUT_PATH))
