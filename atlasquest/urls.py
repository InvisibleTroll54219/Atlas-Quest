from django.urls import path

from game import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/progress/", views.progress_view, name="progress"),
    path("api/round/", views.start_round, name="start-round"),
    path("api/answer/", views.submit_answer, name="submit-answer"),
    path("api/reset/", views.reset_progress, name="reset-progress"),
]
