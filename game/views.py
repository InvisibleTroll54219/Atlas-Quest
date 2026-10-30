import json
import random

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import PlayerProgress
from .question_bank import (
    create_question_variant,
    get_levels,
    get_questions_by_level,
)


QUESTIONS_PER_ROUND = 5
ROUND_GOAL = 4
POINTS_PER_CORRECT_ANSWER = 100


def _get_progress(request):
    if not request.session.session_key:
        request.session.create()
    progress, _ = PlayerProgress.objects.get_or_create(
        session_key=request.session.session_key
    )
    if progress.campaign_version < 2:
        progress.campaign_version = 2
        progress.unlocked_level = 0
        progress.cleared_levels = []
        progress.save(
            update_fields=[
                "campaign_version",
                "unlocked_level",
                "cleared_levels",
                "updated_at",
            ]
        )
    return progress


def _progress_payload(progress):
    return {
        "unlocked_level": progress.unlocked_level,
        "cleared_levels": progress.cleared_levels,
        "level_best_scores": progress.level_best_scores,
        "score": progress.score,
        "correct_answers": progress.correct_answers,
        "best_streak": progress.best_streak,
        "current_streak": progress.current_streak,
        "levels": get_levels(),
    }


def _json_body(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


@ensure_csrf_cookie
def index(request):
    return render(request, "index.html")


@require_GET
def progress_view(request):
    return JsonResponse(_progress_payload(_get_progress(request)))


@require_GET
def start_round(request):
    try:
        level_index = int(request.GET.get("level", "0"))
    except ValueError:
        return JsonResponse({"error": "Level must be a number."}, status=400)
    progress = _get_progress(request)
    levels = get_levels()
    if level_index < 0 or level_index >= len(levels):
        return JsonResponse({"error": "That level does not exist."}, status=404)
    if level_index > progress.unlocked_level:
        return JsonResponse({"error": "Clear the previous level to unlock this one."}, status=403)
    fact_groups = get_questions_by_level().get(level_index, {})
    curated_groups = [
        group for group in fact_groups.values()
        if group and group[0].get("source") != "GeoNames"
    ]
    if len(curated_groups) < QUESTIONS_PER_ROUND:
        return JsonResponse({"error": "This level does not have enough curated questions."}, status=500)

    selected_groups = random.sample(curated_groups, QUESTIONS_PER_ROUND)
    selected_questions = [
        create_question_variant(random.choice(group)) for group in selected_groups
    ]
    request.session["active_round"] = {
        "level": level_index,
        "question_ids": [question["id"] for question in selected_questions],
        "question_answers": {
            question["id"]: {
                "answer_indices": question["answer_indices"],
                "explanation": question["explanation"],
                "option_count": len(question["options"]),
            }
            for question in selected_questions
        },
        "answered_ids": [],
        "correct": 0,
        "complete": False,
    }
    request.session.modified = True
    return JsonResponse(
        {
            "level": level_index,
            "level_info": levels[level_index],
            "question_count": QUESTIONS_PER_ROUND,
            "goal": ROUND_GOAL,
            "questions": [
                {
                    "id": question["id"],
                    "prompt": question["prompt"],
                    "options": question["options"],
                }
                for question in selected_questions
            ],
        }
    )


@require_POST
def submit_answer(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)
    question_id = body.get("question_id")
    selected_index = body.get("selected_index")
    if not isinstance(question_id, str) or not isinstance(selected_index, int) or isinstance(selected_index, bool):
        return JsonResponse({"error": "A question ID and answer choice are required."}, status=400)

    active_round = request.session.get("active_round")
    if not active_round or active_round.get("complete"):
        return JsonResponse({"error": "Start a round before submitting an answer."}, status=409)
    if question_id not in active_round["question_ids"]:
        return JsonResponse({"error": "That question is not part of the active round."}, status=400)
    if question_id in active_round["answered_ids"]:
        return JsonResponse({"error": "That question has already been answered."}, status=409)

    question_answers = active_round.get("question_answers")
    if not isinstance(question_answers, dict):
        return JsonResponse({"error": "Start a new round before submitting an answer."}, status=409)
    question = question_answers.get(question_id)
    if question is None or selected_index < 0 or selected_index >= question["option_count"]:
        return JsonResponse({"error": "That answer choice is not valid."}, status=400)

    correct_indices = question["answer_indices"]
    is_correct = selected_index in correct_indices
    with transaction.atomic():
        progress = _get_progress(request)
        if is_correct:
            progress.score += POINTS_PER_CORRECT_ANSWER
            progress.correct_answers += 1
            progress.current_streak += 1
            progress.best_streak = max(progress.best_streak, progress.current_streak)
            active_round["correct"] += 1
        else:
            progress.current_streak = 0

        active_round["answered_ids"].append(question_id)
        round_complete = len(active_round["answered_ids"]) == QUESTIONS_PER_ROUND
        cleared = False
        newly_cleared = False
        new_best_score = False
        if round_complete:
            active_round["complete"] = True
            cleared = active_round["correct"] >= ROUND_GOAL
            level_best_scores = dict(progress.level_best_scores)
            level_key = str(active_round["level"])
            previous_best_score = level_best_scores.get(level_key, 0)
            new_best_score = active_round["correct"] > previous_best_score
            level_best_scores[level_key] = max(
                previous_best_score, active_round["correct"]
            )
            progress.level_best_scores = level_best_scores
            if cleared:
                cleared_levels = list(progress.cleared_levels)
                newly_cleared = active_round["level"] not in cleared_levels
                if newly_cleared:
                    cleared_levels.append(active_round["level"])
                    progress.cleared_levels = sorted(cleared_levels)
                progress.unlocked_level = max(
                    progress.unlocked_level,
                    min(active_round["level"] + 1, len(get_levels()) - 1),
                )

        progress.save()
        request.session["active_round"] = active_round
        request.session.modified = True

    response = {
        "correct": is_correct,
        "correct_indices": correct_indices,
        "explanation": question["explanation"],
        "score": progress.score,
        "current_streak": progress.current_streak,
        "best_streak": progress.best_streak,
        "round_complete": round_complete,
    }
    if round_complete:
        response.update(
            {
                "cleared": cleared,
                "newly_cleared": newly_cleared,
                "correct_in_round": active_round["correct"],
                "best_score": progress.level_best_scores[str(active_round["level"])],
                "new_best_score": new_best_score,
                "goal": ROUND_GOAL,
                "unlocked_level": progress.unlocked_level,
                "cleared_levels": progress.cleared_levels,
                "level_best_scores": progress.level_best_scores,
                "all_cleared": len(progress.cleared_levels) == len(get_levels()),
            }
        )
    return JsonResponse(response)


@require_POST
def reset_progress(request):
    if not request.session.session_key:
        return JsonResponse({"error": "There is no saved progress to reset."}, status=404)
    PlayerProgress.objects.filter(session_key=request.session.session_key).delete()
    request.session.flush()
    progress = _get_progress(request)
    request.session.pop("active_round", None)
    return JsonResponse(_progress_payload(progress))
