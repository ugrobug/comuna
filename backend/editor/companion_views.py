import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from editor.companions import CompanionError, CompanionService
from users.service import _get_user_from_request


@csrf_exempt
def companion_search(request, post_id):
    user = _get_user_from_request(request)
    try:
        if request.method == "GET":
            result = CompanionService.load(post_id, user).serialize(user)
        elif request.method == "POST":
            if not user:
                raise CompanionError("Войдите или зарегистрируйтесь, чтобы откликнуться.", 401)
            try:
                payload = json.loads(request.body or b"{}")
            except (ValueError, UnicodeDecodeError):
                raise CompanionError("Некорректный запрос.")
            if not isinstance(payload, dict):
                raise CompanionError("Некорректный запрос.")
            action = payload.get("action", "respond")
            if action == "approve":
                response_id = payload.get("response_id")
                if not isinstance(response_id, int) or isinstance(response_id, bool) or response_id <= 0:
                    raise CompanionError("Выберите отклик.")
                result = CompanionService.approve(post_id, user, response_id)
            elif action in ("respond", "withdraw"):
                result = CompanionService.respond(post_id, user, payload.get("message"), withdraw=action == "withdraw")
            else:
                raise CompanionError("Неизвестное действие.")
        else:
            raise CompanionError("Метод не поддерживается.", 405)
        response = JsonResponse({"ok": True, "companion": result})
    except CompanionError as error:
        response = JsonResponse({"ok": False, "error": str(error)}, status=error.status)
    response["Cache-Control"] = "private, no-store"
    return response
