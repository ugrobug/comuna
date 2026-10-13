from django.urls import path
from . import views

app_name = "unitgame_app"

urlpatterns = [
    path("", views.menu_view, name="menu"),
    path("play/", views.play_view, name="play"),
    path("onboarding/", views.onboarding_view, name="onboarding"),
]
