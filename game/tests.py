import json
from collections import Counter

from django.test import TestCase

from .models import PlayerProgress
from .question_bank import get_question_bank, get_questions_by_id, get_questions_by_level


class QuestionBankTests(TestCase):
    def _correct_index(self, question_data):
        question = get_questions_by_id()[question_data["id"]]
        correct_options = {
            question["options"][index] for index in question["answer_indices"]
        }
        return next(
            index
            for index, option in enumerate(question_data["options"])
            if option in correct_options
        )

    def test_bank_has_one_hundred_times_more_distinct_facts(self):
        bank = get_question_bank()
        self.assertEqual(len(bank), 6400)
        self.assertEqual(len({question["id"] for question in bank}), len(bank))
        self.assertEqual(len({question["fact_id"] for question in bank}), len(bank))
        self.assertEqual({question["level"] for question in bank}, set(range(8)))
        self.assertEqual(
            {question["continent"] for question in bank},
            {"Africa", "Asia", "Europe", "North America", "South America", "Oceania", "Antarctica", "World"},
        )
        continent_order = [
            "Africa",
            "Asia",
            "Europe",
            "North America",
            "South America",
            "Oceania",
            "Antarctica",
            "World",
        ]
        self.assertEqual(
            Counter(question["level"] for question in bank),
            {0: 800, 1: 800, 2: 800, 3: 800, 4: 800, 5: 800, 6: 8, 7: 1592},
        )
        geonames_facts = [question for question in bank if question.get("source") == "GeoNames"]
        self.assertEqual(len(geonames_facts), 6336)
        self.assertEqual(
            len({question["geoname_id"] for question in geonames_facts}),
            len(geonames_facts),
        )
        for level, fact_groups in get_questions_by_level().items():
            self.assertEqual(
                len(fact_groups),
                {0: 800, 1: 800, 2: 800, 3: 800, 4: 800, 5: 800, 6: 8, 7: 1592}[level],
            )
            self.assertEqual(
                {question["continent"] for group in fact_groups.values() for question in group},
                {continent_order[level]},
            )

    def test_world_challenge_stays_locked_until_continent_campaign_is_cleared(self):
        self.assertEqual(self.client.get("/api/round/?level=7").status_code, 403)

    def test_old_theme_progress_starts_new_campaign_without_losing_stats(self):
        self.client.get("/api/progress/")
        progress = PlayerProgress.objects.get()
        progress.campaign_version = 1
        progress.unlocked_level = 5
        progress.cleared_levels = [0, 1, 2, 3, 4]
        progress.score = 900
        progress.correct_answers = 9
        progress.save()

        result = self.client.get("/api/progress/").json()

        self.assertEqual(result["unlocked_level"], 0)
        self.assertEqual(result["cleared_levels"], [])
        self.assertEqual(result["score"], 900)
        self.assertEqual(result["correct_answers"], 9)

    def test_round_uses_five_distinct_facts_and_hides_answers(self):
        response = self.client.get("/api/round/?level=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["questions"]), 5)
        fact_ids = [question["id"] for question in data["questions"]]
        self.assertEqual(len(set(fact_ids)), 5)
        for question in data["questions"]:
            self.assertNotIn("answer_index", question)
            self.assertNotIn("answer_indices", question)
            self.assertNotIn("explanation", question)
            self.assertEqual(len(question["options"]), 4)

    def test_locked_level_cannot_be_started(self):
        self.assertEqual(self.client.get("/api/round/?level=1").status_code, 403)

    def test_vercel_deployment_host_is_allowed(self):
        response = self.client.get(
            "/api/progress/", HTTP_HOST="atlas-quest-preview.vercel.app"
        )
        self.assertEqual(response.status_code, 200)

    def test_answers_are_scored_and_four_correct_answers_unlock_next_level(self):
        round_data = self.client.get("/api/round/?level=0").json()
        for question_data in round_data["questions"]:
            response = self.client.post(
                "/api/answer/",
                data=json.dumps(
                    {
                        "question_id": question_data["id"],
                        "selected_index": self._correct_index(question_data),
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
        self.assertEqual(final_answer["level_best_scores"], {"0": 5})
        self.assertEqual(PlayerProgress.objects.get().score, 500)

    def test_level_best_score_tracks_bare_pass_and_upgrades_to_perfect(self):
        for expected_best in (4, 5):
            round_data = self.client.get("/api/round/?level=0").json()
            for index, question_data in enumerate(round_data["questions"]):
                correct_index = self._correct_index(question_data)
                selected_index = (
                    correct_index
                    if index < expected_best
                    else (correct_index + 1) % len(question_data["options"])
                )
                response = self.client.post(
                    "/api/answer/",
                    data=json.dumps(
                        {
                            "question_id": question_data["id"],
                            "selected_index": selected_index,
                        }
                    ),
                    content_type="application/json",
                )
            result = response.json()
            self.assertEqual(result["best_score"], expected_best)
            self.assertEqual(result["new_best_score"], True)

        self.assertTrue(result["cleared"])
        self.assertEqual(result["level_best_scores"], {"0": 5})
        progress = self.client.get("/api/progress/").json()
        self.assertEqual(progress["level_best_scores"], {"0": 5})

    def test_clearing_seventh_continent_unlocks_world_explorer_finale(self):
        self.client.get("/api/progress/")
        progress = PlayerProgress.objects.get()
        progress.unlocked_level = 6
        progress.cleared_levels = [0, 1, 2, 3, 4, 5]
        progress.save()
        round_data = self.client.get("/api/round/?level=6").json()
        for question_data in round_data["questions"]:
            response = self.client.post(
                "/api/answer/",
                data=json.dumps(
                    {
                        "question_id": question_data["id"],
                        "selected_index": self._correct_index(question_data),
                    }
                ),
                content_type="application/json",
            )

        result = response.json()
        self.assertTrue(result["cleared"])
        self.assertEqual(result["unlocked_level"], 7)
        self.assertEqual(result["cleared_levels"], [0, 1, 2, 3, 4, 5, 6])
        self.assertFalse(result["all_cleared"])
        world_round = self.client.get("/api/round/?level=7").json()
        for question_data in world_round["questions"]:
            response = self.client.post(
                "/api/answer/",
                data=json.dumps(
                    {
                        "question_id": question_data["id"],
                        "selected_index": self._correct_index(question_data),
                    }
                ),
                content_type="application/json",
            )
        self.assertTrue(response.json()["all_cleared"])

    def test_answer_cannot_be_submitted_twice(self):
        question = self.client.get("/api/round/?level=0").json()["questions"][0]
        answer = {
            "question_id": question["id"],
            "selected_index": self._correct_index(question),
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
