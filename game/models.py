from django.db import models


class PlayerProgress(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    campaign_version = models.PositiveSmallIntegerField(default=2)
    unlocked_level = models.PositiveSmallIntegerField(default=0)
    cleared_levels = models.JSONField(default=list)
    level_best_scores = models.JSONField(default=dict)
    score = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Player progress ({})".format(self.session_key[:8])
