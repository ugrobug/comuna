from django.shortcuts import render

def menu_view(request):
    return render(request, "unitgame_app/menu.html")

def play_view(request):
    # твой текущий index.html рендерится как есть
    return render(request, "unitgame_app/index.html", {"ONBOARDING": False})

def onboarding_view(request):
    # тот же шаблон, но с подсветками и подсказками
    return render(request, "unitgame_app/index.html", {"ONBOARDING": True})
