"""Bounded mention discovery, explicit link parsing and idempotent notification writes."""
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from communities.models import Comun
from feeds.preview import parse_editor_payload


class MentionSearch:
    limit = 5

    def search(self, text):
        text = str(text or '').strip().lstrip('@')
        if not text or len(text) > 80:
            return []
        terms = re.findall(r'\w+', text, flags=re.UNICODE)[:5]
        if not terms:
            return []
        query = SearchQuery(' & '.join(f'{term}:*' for term in terms), config='simple', search_type='raw')
        users = (get_user_model().objects.filter(is_active=True)
                 .alias(mention_search=SearchVector('username', 'first_name', 'last_name', config='simple'))
                 .filter(mention_search=query).order_by(Lower('username'), 'id')
                 .values('id', 'username', 'first_name', 'last_name')[:self.limit])
        communities = (Comun.objects.filter(is_active=True)
                       .alias(mention_search=SearchVector('name', 'slug', config='simple'))
                       .filter(mention_search=query).order_by(Lower('name'), 'id')
                       .values('id', 'name', 'slug')[:self.limit])
        return [dict(kind='user', id=u['id'], handle=u['username'],
                     label=(' '.join([u['first_name'], u['last_name']]).strip() or u['username']),
                     url=f"/id{u['id']}?mention=user.{u['id']}") for u in users] + [
            dict(kind='comun', id=c['id'], handle=c['slug'], label=c['name'],
                 url=f"/comuns/{quote(c['slug'])}?mention=comun.{c['id']}") for c in communities]


class MentionParser(HTMLParser):
    """Only links selected as mentions count; plain @text and ordinary links do not."""
    limit = 20
    max_content_length = 1_000_000
    markdown_link = re.compile(r'(?<![!\\])\[(@(?:\\.|[^\]\\])+)\]\(([^\s)]+)\)')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.targets = set()
        self.ignored = 0
        self.anchor = None
        self.label = ''

    def add(self, href, label):
        if len(self.targets) >= self.limit or not label.strip().startswith('@'):
            return
        try:
            url = urlsplit(href)
            own = urlsplit(settings.SITE_BASE_URL)
            if url.netloc and (url.scheme not in ('http', 'https') or url.netloc != own.netloc):
                return
            if url.scheme and not url.netloc:
                return
            match = re.fullmatch(r'(user|comun)\.([1-9][0-9]{0,9})', parse_qs(url.query).get('mention', [''])[0])
            if not match:
                return
            kind, identifier = match.groups()
            if kind == 'user' and url.path != f'/id{identifier}':
                return
            if kind == 'comun' and not re.fullmatch(r'/comuns/[^/]+', url.path):
                return
            self.targets.add((kind, int(identifier)))
        except ValueError:
            return

    def handle_starttag(self, tag, attrs):
        if tag in ('code', 'pre', 'script', 'style'):
            self.ignored += 1
        if tag == 'a' and not self.ignored:
            self.anchor = dict(attrs).get('href', '')
            self.label = ''

    def handle_data(self, data):
        if self.anchor is not None and not self.ignored:
            self.label += data

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.anchor is not None and not self.ignored:
                self.add(self.anchor, self.label)
            self.anchor = None
        if tag in ('code', 'pre', 'script', 'style'):
            self.ignored = max(0, self.ignored - 1)

    def text(self, text, *, markdown=False):
        if markdown:
            text = re.sub(r'<(code|pre)\b[^>]*>[\s\S]*?</\1>', '', text, flags=re.I)
            text = re.sub(r'```[\s\S]*?(?:```|$)|~~~[\s\S]*?(?:~~~|$)|`[^`\n]*`', '', text)
            for match in self.markdown_link.finditer(text):
                self.add(match[2], match[1])
        self.feed(text)
        self.reset()
        self.ignored = 0
        self.anchor = None

    def extract(self, content, *, comment=False):
        if not content or len(content) > self.max_content_length:
            return set()
        if comment:
            self.text(content, markdown=True)
        else:
            payload = parse_editor_payload(content)
            if payload:
                # Read only visible text; never infer mentions from code, URLs, preview or metadata.
                for block in payload['blocks'][:2000]:
                    if not isinstance(block, dict) or block.get('type') not in (
                        'paragraph', 'header', 'list', 'quote', 'table', 'callout', 'warning'):
                        continue
                    self.walk(block.get('data', {}))
            else:
                self.text(content, markdown=True)
        return self.targets

    def walk(self, value, depth=0):
        if depth > 12 or len(self.targets) >= self.limit:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('text', 'content', 'items', 'caption', 'title', 'message'):
                    self.walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value[:2000]:
                self.walk(item, depth + 1)
        elif isinstance(value, str):
            self.text(value)


class MentionService:
    """Lock a source, batch recipients/preferences, and write each recipient once for its lifetime."""
    @staticmethod
    def notification_is_visible(notification):
        from django.db.models import Q
        from feeds.models import Post
        payload = notification.payload or {}
        posts = Post.objects.filter(
            pk=payload.get('post_id'), is_pending=False, is_blocked=False,
            author__is_blocked=False, companion_matched_at__isnull=True,
        ).filter(Q(publish_at__isnull=True) | Q(publish_at__lte=timezone.now()))
        if notification.event_key == 'comment_mention':
            posts = posts.filter(comments__id=payload.get('comment_id'), comments__is_deleted=False)
        return posts.exists()

    def save_source(self, source, save, *, comment=False, process=True):
        content = source.body if comment else source.content
        targets = MentionParser().extract(content, comment=comment) if process else set()
        if not targets:
            return save()
        with transaction.atomic():
            result = save()
            self.publish(source, comment=comment, targets=targets)
            return result

    def publish(self, source, *, comment=False, targets=None):
        from feeds.models import Post, PostComment, MentionDelivery
        from notifications.models import SiteNotification, SiteNotificationPreference

        content = source.body if comment else source.content
        if targets is None:
            targets = MentionParser().extract(content, comment=comment)
        if not targets:
            return
        with transaction.atomic():
            # The source lock serializes concurrent edits, including scheduled publication.
            model = PostComment if comment else Post
            current = model.objects.select_for_update().get(pk=source.pk)
            post = Post.objects.select_related('author').get(pk=current.post_id) if comment else current
            if (post.is_pending or post.is_blocked or post.author.is_blocked or post.companion_matched_at
                    or (post.publish_at and post.publish_at > timezone.now())
                    or (comment and current.is_deleted)):
                return
            targets = MentionParser().extract(current.body if comment else current.content, comment=comment)
            source_filter = {'comment_id' if comment else 'post_id': current.pk}
            recipients = {pk: [] for kind, pk in targets if kind == 'user'}
            # A community's creator is its administrator; moderators are not owners.
            for comun in Comun.objects.filter(pk__in=[pk for kind, pk in targets if kind == 'comun'],
                                               is_active=True, creator__isnull=False).values('id', 'name', 'creator_id'):
                recipients.setdefault(comun['creator_id'], []).append(comun['name'])
            already = set(MentionDelivery.objects.filter(**source_filter, user_id__in=recipients).values_list('user_id', flat=True))
            users = list(get_user_model().objects.filter(pk__in=set(recipients) - already, is_active=True)
                         .exclude(**({'pk': current.user_id} if comment else {'username__iexact': post.author.username}))
                         .only('id', 'username'))
            if not users:
                return
            event = 'comment_mention' if comment else 'post_mention'
            preferences = {p.user_id: p for p in SiteNotificationPreference.objects.filter(
                user_id__in=[u.pk for u in users], event_key=event)}
            now = timezone.now()
            rows = []
            for user in users:
                pref = preferences.get(user.pk)
                channels = dict(is_site=pref.site_enabled if pref else True,
                                is_telegram=pref.telegram_enabled if pref else False,
                                is_push=pref.push_enabled if pref else False)
                if not any(channels.values()):
                    continue
                communities = recipients[user.pk]
                location = 'комментарии' if comment else 'посте'
                subject = ('Ваше сообщество «' + '», «'.join(communities) + '»') if communities else 'Вас'
                rows.append(SiteNotification(
                    user=user, event_key=event, title=f'Упоминание в {location}',
                    message=f'{subject} упомянули в {location}.',
                    link_url=f'/b/post/{post.pk}' + (f'#site-comment-{current.pk}' if comment else ''),
                    payload={'post_id': post.pk, **({'comment_id': current.pk} if comment else {})},
                    group_key=f'mention:{"comment" if comment else "post"}:{current.pk}:{user.pk}',
                    delivery_at=now, delivered_at=None if channels['is_telegram'] or channels['is_push'] else now,
                    **channels))
            MentionDelivery.objects.bulk_create([MentionDelivery(user=u, **source_filter) for u in users])
            SiteNotification.objects.bulk_create(rows)
