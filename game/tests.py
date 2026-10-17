import json

from django.test import TestCase

from .models import PlayerProgress
from .question_bank import get_question_bank, get_questions_by_id


class QuestionBankTests(TestCase):
    def test_bank_has_more_than_ten_thousand_unique_questions(self):
        bank = get_question_bank()
        self.assertGreaterEqual(len(bank), 10000)
        self.assertEqual(len({question["id"] for question in bank}), len(bank))
        self.assertEqual({question["level"] for question in bank}, set(range(8)))

    def test_round_uses_five_distinct_facts_and_hides_answers(self):
        response = self.client.get("/api/round/?level=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["questions"]), 5)
        fact_ids = [question["id"].split("-")[0] + "-" + question["id"].split("-")[1] for question in data["questions"]]
        self.assertEqual(len(set(fact_ids)), 5)
        for question in data["questions"]:
            self.assertNotIn("answer_index", question)
            self.assertNotIn("explanation", question)

    def test_locked_level_cannot_be_started(self):
        self.assertEqual(self.client.get("/api/round/?level=1").status_code, 403)

    def test_answers_are_scored_and_four_correct_answers_unlock_next_level(self):
        round_data = self.client.get("/api/round/?level=0").json()
        bank = get_questions_by_id()
        for question_data in round_data["questions"]:
            question = bank[question_data["id"]]
            response = self.client.post(
                "/api/answer/",
                data=json.dumps(
                    {
                        "question_id": question["id"],
                        "selected_index": question["answer_index"],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        final_answer = response.json()
        self.assertTrue(final_answer["round_complete"])
        self.assertTrue(final_answer["cleared"])
        self.assertEqual(final_answer["correct_in_round"], 5)
        self.assertEqual(final_answer["unlocked_level"], 1)
        self.assertEqual(final_answer["score"], 500)
        self.assertEqual(final_answer["cleared_levels"], [0])
        self.assertEqual(PlayerProgress.objects.get().score, 500)

    def test_answer_cannot_be_submitted_twice(self):
        question = self.client.get("/api/round/?level=0").json()["questions"][0]
        answer = {
            "question_id": question["id"],
            "selected_index": get_questions_by_id()[question["id"]]["answer_index"],
        }
        first = self.client.post("/api/answer/", json.dumps(answer), content_type="application/json")
        second = self.client.post("/api/answer/", json.dumps(answer), content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_reset_clears_database_progress(self):
        self.client.get("/api/progress/")
        progress = PlayerProgress.objects.get()
        progress.score = 700
        progress.save()
        response = self.client.post("/api/reset/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"], 0)
        self.assertEqual(PlayerProgress.objects.count(), 1)
