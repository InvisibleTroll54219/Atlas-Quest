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
        border_fact = next(
            question for question in bank if question["fact_id"] == "L5-Q7"
        )
        self.assertEqual(
            {border_fact["options"][index] for index in border_fact["answer_indices"]},
            {"China", "Russia"},
        )

    def test_round_uses_five_distinct_facts_and_hides_answers(self):
        response = self.client.get("/api/round/?level=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["questions"]), 5)
        fact_ids = [question["id"].split("-")[0] + "-" + question["id"].split("-")[1] for question in data["questions"]]
        self.assertEqual(len(set(fact_ids)), 5)
        for question in data["questions"]:
            self.assertNotIn("answer_index", question)
            self.assertNotIn("answer_indices", question)
            self.assertNotIn("explanation", question)

    def test_locked_level_cannot_be_started(self):
        self.assertEqual(self.client.get("/api/round/?level=1").status_code, 403)

    def test_vercel_deployment_host_is_allowed(self):
        response = self.client.get(
            "/api/progress/", HTTP_HOST="atlas-quest-preview.vercel.app"
        )
        self.assertEqual(response.status_code, 200)

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
                        "selected_index": question["answer_indices"][0],
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

    def test_both_tied_countries_are_accepted_as_correct_answers(self):
        self.client.get("/api/progress/")
        progress = PlayerProgress.objects.get()
        progress.unlocked_level = 4
        progress.save()
        bank = get_questions_by_id()
        question = next(
            item
            for item in get_question_bank()
            if item["fact_id"] == "L5-Q7"
        )
        correct_options = {
            question["options"][index]
            for index in question["answer_indices"]
        }
        self.assertEqual(correct_options, {"China", "Russia"})

        for option in correct_options:
            progress.refresh_from_db()
            session = self.client.session
            session["active_round"] = {
                "level": 4,
                "question_ids": [question["id"]],
                "answered_ids": [],
                "correct": 0,
                "complete": False,
            }
            session.save()
            response = self.client.post(
                "/api/answer/",
                data=json.dumps(
                    {
                        "question_id": question["id"],
                        "selected_index": question["options"].index(option),
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertTrue(result["correct"], option)
            self.assertEqual(
                {question["options"][index] for index in result["correct_indices"]},
                {"China", "Russia"},
            )
        self.assertEqual(PlayerProgress.objects.get().score, 200)

    def test_answer_cannot_be_submitted_twice(self):
        question = self.client.get("/api/round/?level=0").json()["questions"][0]
        answer = {
            "question_id": question["id"],
            "selected_index": get_questions_by_id()[question["id"]]["answer_indices"][0],
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
