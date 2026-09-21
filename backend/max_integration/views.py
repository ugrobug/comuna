import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from communities.models import Comun
from communities.service import _comun_is_moderator
from rabotaem_backend.rate_limit import is_rate_limited
from users.service import _get_user_from_request
from .client import MaxAPIError
from .models import MaxAccount, MaxChat, MaxUpdate, MaxVerificationCode, MaxSubmission
from .service import MaxAccountService, MaxChannelService
from .submissions import MaxSubmissionService


def serialize_chat(chat):
    return {'id': chat.pk, 'chat_id': str(chat.chat_id), 'type': chat.chat_type, 'title': chat.title,
            'link': chat.link, 'comun_slug': chat.comun.slug if chat.comun_id else None,
            'auto_publish': chat.auto_publish, 'publish_delay_days': chat.publish_delay_days}


@csrf_exempt
def webhook(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    expected = getattr(settings, 'MAX_WEBHOOK_SECRET', '')
    if not expected or not hmac.compare_digest(request.headers.get('X-Max-Bot-Api-Secret', ''), expected):
        return JsonResponse({'ok': False}, status=403)
    if len(request.body) > 1024 * 1024:
        return JsonResponse({'ok': False}, status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get('update_type'), str):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False}, status=400)
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    MaxUpdate.objects.get_or_create(digest=digest, defaults={'payload': data, 'available_at': timezone.now()})
    return JsonResponse({'ok': True})


@csrf_exempt
def account(request):
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    linked = MaxAccount.objects.filter(user=user).first()
    if request.method == 'POST':
        if is_rate_limited(request, scope='max_link_code', limit=10, window_seconds=300):
            return JsonResponse({'ok': False, 'error': 'Попробуйте позже.'}, status=429)
        return JsonResponse({'ok': True, 'code': MaxAccountService.issue_code(user)})
    if request.method == 'DELETE':
        MaxVerificationCode.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        if linked:
            MaxChat.verified_users.through.objects.filter(user_id=user.pk).delete()
            linked.delete()
        return JsonResponse({'ok': True})
    if request.method != 'GET':
        return JsonResponse({'ok': False}, status=405)
    return JsonResponse({'ok': True, 'configured': bool(settings.MAX_BOT_TOKEN),
        'bot_url': f'https://max.ru/{settings.MAX_BOT_USERNAME}',
        'account': {'name': linked.name, 'active': linked.is_active} if linked else None,
        'chats': [serialize_chat(c) for c in MaxChat.objects.filter(verified_users=user, is_active=True).select_related('comun')]})


@csrf_exempt
def community(request, slug):
    user = _get_user_from_request(request)
    comun = Comun.objects.filter(slug=slug).first()
    if not user:
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    if not comun or not _comun_is_moderator(user, comun):
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    if request.method == 'GET':
        return JsonResponse({'ok': True, 'chats': [serialize_chat(c) for c in comun.max_chats.select_related('comun')], 'submissions': list(comun.max_submissions.filter(status='pending').values('id', 'request_type', 'source_text')[:100])})
    if request.method not in ['POST', 'DELETE']:
        return JsonResponse({'ok': False}, status=405)
    try:
        data = json.loads(request.body)
        if data.get('action') in ['approve', 'reject'] and request.method == 'POST':
            item = MaxSubmission.objects.get(pk=int(data['id']), comun=comun)
            MaxSubmissionService.review(user, item.pk, data['action'] == 'approve')
            return JsonResponse({'ok': True})
        chat = MaxChat.objects.get(pk=int(data['id']))
        if request.method == 'DELETE':
            if chat.comun_id != comun.pk:
                raise ValueError('Канал не привязан к этому сообществу.')
            chat.comun = None
            chat.save(update_fields=['comun', 'updated_at'])
        else:
            linked = MaxAccount.objects.filter(user=user, is_active=True).first()
            if not linked:
                raise ValueError('Сначала привяжите аккаунт MAX в настройках профиля.')
            chat = MaxChannelService().link(linked, chat, comun)
        return JsonResponse({'ok': True, 'chat': serialize_chat(chat)})
    except (ValueError, KeyError, TypeError, AttributeError, MaxChat.DoesNotExist, MaxSubmission.DoesNotExist) as exc:
        return JsonResponse({'ok': False, 'error': str(exc) or 'Некорректные данные'}, status=400)
    except MaxAPIError:
        return JsonResponse({'ok': False, 'error': 'MAX временно недоступен. Попробуйте ещё раз.'}, status=502)
