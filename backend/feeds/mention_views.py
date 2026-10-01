from django.http import JsonResponse
from django.views.decorators.http import require_GET
from feeds.mentions import MentionSearch
from users.service import _get_user_from_request


@require_GET
def mention_suggestions(request):
    if not _get_user_from_request(request):
        return JsonResponse({'error': 'unauthorized'}, status=401)
    query = request.GET.get('q', '')
    if len(query) > 80:
        return JsonResponse({'error': 'query too long'}, status=400)
    response = JsonResponse({'items': MentionSearch().search(query)})
    response['Cache-Control'] = 'private, no-store'
    return response
