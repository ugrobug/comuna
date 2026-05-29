from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from communities.models import Comun, ComunCategory, ComunGlossaryTerm, ComunPostCategoryAssignment, ComunVote
from feeds.models import (
    Author,
    Post,
    PostComment,
    PostFavorite,
    PostLike,
    PostRead,
    Tag,
)
from ratings.models import AuthorRatingEvent
from users.models import AuthorAdmin, SiteUserProfile

User = get_user_model()

DEMO_PASSWORD = "demo12345"
DEMO_USERNAMES = [f"demo_user_{index:02d}" for index in range(1, 11)]
DEMO_AUTHOR_USERNAMES = [f"demo_channel_{index:02d}" for index in range(1, 11)]
DEMO_COMUN_SLUG_PREFIX = "demo-"
DEMO_TAG_NAMES = (
    "AI Lab",
    "Game Design",
    "Product Sense",
    "Frontend Craft",
    "Backend Ops",
    "Data Stories",
    "Cinema Club",
    "Music Lab",
    "Travel Notes",
    "Startup Weekly",
    "Дискуссия",
    "Лонгрид",
)


@dataclass(frozen=True)
class DemoUserSpec:
    username: str
    display_name: str
    first_name: str
    last_name: str
    email: str


@dataclass(frozen=True)
class DemoTopicSpec:
    community_name: str
    community_slug: str
    tag_name: str
    category_name: str
    glossary_term: str
    glossary_definition: str
    post_title: str
    post_html: str


DEMO_USERS: tuple[DemoUserSpec, ...] = (
    DemoUserSpec("demo_user_01", "Алина Миронова", "Алина", "Миронова", "alina@example.test"),
    DemoUserSpec("demo_user_02", "Илья Серов", "Илья", "Серов", "ilya@example.test"),
    DemoUserSpec("demo_user_03", "Надя Белова", "Надя", "Белова", "nadya@example.test"),
    DemoUserSpec("demo_user_04", "Егор Киселев", "Егор", "Киселев", "egor@example.test"),
    DemoUserSpec("demo_user_05", "Вика Романова", "Вика", "Романова", "vika@example.test"),
    DemoUserSpec("demo_user_06", "Марк Журавлев", "Марк", "Журавлев", "mark@example.test"),
    DemoUserSpec("demo_user_07", "Оля Соколова", "Оля", "Соколова", "olya@example.test"),
    DemoUserSpec("demo_user_08", "Денис Орлов", "Денис", "Орлов", "denis@example.test"),
    DemoUserSpec("demo_user_09", "Катя Веденеева", "Катя", "Веденеева", "katya@example.test"),
    DemoUserSpec("demo_user_10", "Павел Титов", "Павел", "Титов", "pavel@example.test"),
)

DEMO_TOPICS: tuple[DemoTopicSpec, ...] = (
    DemoTopicSpec(
        community_name="Демо: AI Lab",
        community_slug="demo-ai-lab",
        tag_name="AI Lab",
        category_name="Разборы",
        glossary_term="RAG",
        glossary_definition="Подход, где модель опирается на внешнюю базу знаний перед ответом.",
        post_title="Что реально работает в маленькой AI-команде без лишнего шума",
        post_html=(
            "<p>Мы за месяц проверили три сценария: FAQ-бот, тематический поиск и разбор входящих заявок.</p>"
            "<p>Лучший результат дал узкий кейс с понятными источниками данных и прозрачной валидацией ответа.</p>"
            "<p>Главный вывод: сначала ограничьте домен, затем добавляйте магию.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Game Design Circle",
        community_slug="demo-game-design",
        tag_name="Game Design",
        category_name="Механики",
        glossary_term="Core Loop",
        glossary_definition="Короткий повторяемый цикл действия, который удерживает игрока в продукте.",
        post_title="Почему маленькая игровая петля важнее большой дорожной карты",
        post_html=(
            "<p>Игрок быстро считывает ценность проекта не по роадмапу, а по первым двум минутам взаимодействия.</p>"
            "<p>Если базовая петля не цепляет, никакая мета-прогрессия потом не спасает retention.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Product Sense",
        community_slug="demo-product-sense",
        tag_name="Product Sense",
        category_name="Гипотезы",
        glossary_term="North Star",
        glossary_definition="Метрика, которая лучше всего отражает долгосрочную пользу продукта для пользователя.",
        post_title="Одна метрика недели, которая помогла нам перестать спорить о фичах",
        post_html=(
            "<p>Команда тонет в обсуждениях, когда каждая функция защищается своей локальной выгодой.</p>"
            "<p>Мы свели спор к одной метрике активации и внезапно упростили половину приоритетов.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Frontend Craft",
        community_slug="demo-frontend-craft",
        tag_name="Frontend Craft",
        category_name="Интерфейсы",
        glossary_term="Hydration",
        glossary_definition="Связывание серверно отрендеренного HTML с клиентским приложением в браузере.",
        post_title="Три фронтенд-решения, которые дают ощущение скорости без обмана",
        post_html=(
            "<p>Скелетоны не спасают, если структура страницы меняется после загрузки.</p>"
            "<p>Лучше работают стабильная раскладка, честные плейсхолдеры и приоритетная загрузка ключевого контента.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Backend Ops",
        community_slug="demo-backend-ops",
        tag_name="Backend Ops",
        category_name="Инциденты",
        glossary_term="Idempotency",
        glossary_definition="Свойство операции давать один и тот же результат при повторном выполнении.",
        post_title="Как мы перестали бояться повторных запросов и дублей задач",
        post_html=(
            "<p>Половина хаоса в бекенде пришла не из нагрузки, а из повторного исполнения одних и тех же действий.</p>"
            "<p>Идемпотентные ключи и явные статусы джобов сняли больше боли, чем очередной кеш.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Data Stories",
        community_slug="demo-data-stories",
        tag_name="Data Stories",
        category_name="Метрики",
        glossary_term="Cohort",
        glossary_definition="Группа пользователей, объединенная общим моментом или сценарием входа в продукт.",
        post_title="Когортный анализ без самообмана: на какие срезы мы смотрим теперь",
        post_html=(
            "<p>Средние значения красиво выглядят в презентации, но плохо объясняют реальную динамику.</p>"
            "<p>Когорты по каналу входа и первой полезной активности дали заметно больше управляемых инсайтов.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Cinema Club",
        community_slug="demo-cinema-club",
        tag_name="Cinema Club",
        category_name="Обсуждение",
        glossary_term="Cold Open",
        glossary_definition="Сцена до титров, которая быстро задает тон и интригу истории.",
        post_title="Фильм недели: почему сильное открытие удерживает даже спорный сюжет",
        post_html=(
            "<p>Первые пять минут фильма часто важнее третьего акта, потому что именно там зритель решает доверять ли истории.</p>"
            "<p>Мы собрали примеры, где мощное открытие держит интерес даже при неровном сценарии.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Music Lab",
        community_slug="demo-music-lab",
        tag_name="Music Lab",
        category_name="Релизы",
        glossary_term="Hook",
        glossary_definition="Самый запоминающийся музыкальный фрагмент, который удерживает внимание слушателя.",
        post_title="Новый релиз и один вопрос: что в треке реально цепляет после второго прослушивания",
        post_html=(
            "<p>Первое впечатление обычно создает продакшен, а второе проверяет силу мелодии и аранжировки.</p>"
            "<p>Разобрали трек по слоям и поняли, где именно работает хук, а где только эффект новизны.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Travel Notes",
        community_slug="demo-travel-notes",
        tag_name="Travel Notes",
        category_name="Маршруты",
        glossary_term="Slow Travel",
        glossary_definition="Подход к поездкам, где ставка делается на глубину опыта, а не на максимальное число точек.",
        post_title="Маршрут на три дня без гонки: как собрать поездку, после которой не нужен отпуск",
        post_html=(
            "<p>Мы отказались от схемы «успеть все» и оставили один район, два музея и длинную прогулку.</p>"
            "<p>Оказалось, что именно такой ритм делает поездку запоминающейся, а не утомительной.</p>"
        ),
    ),
    DemoTopicSpec(
        community_name="Демо: Startup Weekly",
        community_slug="demo-startup-weekly",
        tag_name="Startup Weekly",
        category_name="Разбор недели",
        glossary_term="PMF",
        glossary_definition="Состояние, когда продукт устойчиво решает понятную проблему для заметной группы людей.",
        post_title="Неделя стартапа в одном посте: где мы слили время и где, наконец, попали в цель",
        post_html=(
            "<p>Слишком долго проверяли вкусовые идеи и слишком поздно спросили пользователей, что именно им мешает сегодня.</p>"
            "<p>Когда перешли к конкретной проблеме и понятной аудитории, гипотезы стали измеримыми.</p>"
        ),
    ),
)


class Command(BaseCommand):
    help = "Seeds the local database with reusable demo users, posts, communities, comments, and ratings."

    def handle(self, *args, **options):
        now = timezone.now()
        rng = Random(20260406)

        with transaction.atomic():
            self._clear_previous_demo_data()
            tags = self._create_tags()
            users = self._create_users()
            authors = self._create_authors(users, now)
            posts = self._create_posts(authors, tags, now, rng)
            self._create_comments(posts, users, now)
            self._create_post_feedback(posts, users, now)
            self._create_comuns(posts, users, tags, now)

        self.stdout.write(self.style.SUCCESS("Demo content created successfully."))
        self.stdout.write(f"Users: {User.objects.filter(username__in=DEMO_USERNAMES).count()}")
        self.stdout.write(f"Authors: {Author.objects.filter(username__in=DEMO_AUTHOR_USERNAMES).count()}")
        self.stdout.write(
            f"Posts: {Post.objects.filter(author__username__in=DEMO_AUTHOR_USERNAMES).count()}"
        )
        self.stdout.write(
            f"Communities: {Comun.objects.filter(slug__startswith=DEMO_COMUN_SLUG_PREFIX).count()}"
        )
        self.stdout.write(f"Demo password for all seeded users: {DEMO_PASSWORD}")

    def _clear_previous_demo_data(self) -> None:
        Comun.objects.filter(slug__startswith=DEMO_COMUN_SLUG_PREFIX).delete()
        Tag.objects.filter(name__in=DEMO_TAG_NAMES).delete()
        Author.objects.filter(username__in=DEMO_AUTHOR_USERNAMES).delete()
        User.objects.filter(username__in=DEMO_USERNAMES).delete()

    def _create_tags(self) -> dict[str, Tag]:
        mood_cycle = [
            Tag.MOOD_NEUTRAL,
            Tag.MOOD_SERIOUS,
            Tag.MOOD_FUNNY,
            Tag.MOOD_NEUTRAL,
        ]
        tags: dict[str, Tag] = {}
        for index, name in enumerate(DEMO_TAG_NAMES):
            tags[name], _created = Tag.objects.get_or_create(
                name=name,
                defaults={"mood": mood_cycle[index % len(mood_cycle)], "is_active": True},
            )
        return tags

    def _create_users(self) -> dict[str, User]:
        users: dict[str, User] = {}
        for spec in DEMO_USERS:
            user = User.objects.create_user(
                username=spec.username,
                email=spec.email,
                password=DEMO_PASSWORD,
                first_name=spec.first_name,
                last_name=spec.last_name,
            )
            SiteUserProfile.objects.create(
                user=user,
                display_name=spec.display_name,
                avatar_url=f"https://api.dicebear.com/8.x/initials/svg?seed={spec.username}",
            )
            users[spec.username] = user
        return users

    def _create_authors(
        self,
        users: dict[str, User],
        now,
    ) -> dict[str, Author]:
        authors: dict[str, Author] = {}
        for index, spec in enumerate(DEMO_USERS):
            user = users[spec.username]
            author = Author.objects.create(
                username=DEMO_AUTHOR_USERNAMES[index],
                title=f"{spec.display_name} пишет о теме недели",
                channel_url=f"https://t.me/{DEMO_AUTHOR_USERNAMES[index]}",
                invite_url=f"https://t.me/{DEMO_AUTHOR_USERNAMES[index]}",
                avatar_url=f"https://api.dicebear.com/8.x/shapes/svg?seed={DEMO_AUTHOR_USERNAMES[index]}",
                description=(
                    f"Авторская лента {spec.display_name}. Короткие наблюдения, разборы и ссылки без лишнего шума."
                ),
                subscribers_count=850 + index * 137,
                auto_publish=True,
                notify_comments=False,
                rating_total=0,
                is_blocked=False,
                shadow_banned=False,
                force_home=index % 3 == 0,
            )
            AuthorAdmin.objects.create(author=author, user=user, verified_at=now)
            authors[spec.username] = author
        return authors

    def _create_posts(
        self,
        authors: dict[str, Author],
        tags: dict[str, Tag],
        now,
        rng: Random,
    ) -> dict[str, Post]:
        posts: dict[str, Post] = {}
        shared_tags = [tags["Дискуссия"], tags["Лонгрид"]]

        for index, topic in enumerate(DEMO_TOPICS):
            user_key = DEMO_USERS[index].username
            author = authors[user_key]
            created_at = now - timedelta(days=10 - index, hours=index)
            post = Post.objects.create(
                author=author,
                message_id=1000 + index,
                title=topic.post_title,
                content=topic.post_html,
                rating=0,
                comments_count=0,
                fake_views_target=120 + index * 35,
                real_views_count=15 + index * 3,
                source_url=f"https://example.com/{topic.community_slug}/post-{index + 1}",
                channel_url=author.invite_url or author.channel_url,
                is_pending=False,
                is_blocked=False,
                publish_at=created_at,
                raw_data={
                    "source": "seed_local_demo_content",
                    "comun_slug": topic.community_slug,
                },
            )
            post.tags.add(tags[topic.tag_name], shared_tags[index % 2])
            Post.objects.filter(id=post.id).update(
                created_at=created_at,
                updated_at=created_at + timedelta(minutes=20),
            )
            post.refresh_from_db()
            posts[topic.community_slug] = post

            for _offset in range(2):
                reader_user = User.objects.get(username=DEMO_USERS[(index + _offset + 2) % len(DEMO_USERS)].username)
                PostRead.objects.get_or_create(post=post, user=reader_user)
            if index % 2 == 0:
                favorite_user = User.objects.get(username=DEMO_USERS[(index + 4) % len(DEMO_USERS)].username)
                PostFavorite.objects.get_or_create(post=post, user=favorite_user)
            post.real_views_count = 20 + rng.randint(5, 80)
            post.save(update_fields=["real_views_count", "updated_at"])

        return posts

    def _create_comments(self, posts: dict[str, Post], users: dict[str, User], now) -> None:
        for index, topic in enumerate(DEMO_TOPICS):
            post = posts[topic.community_slug]
            commenter_a = users[DEMO_USERS[(index + 1) % len(DEMO_USERS)].username]
            commenter_b = users[DEMO_USERS[(index + 2) % len(DEMO_USERS)].username]
            base_time = now - timedelta(days=9 - index, hours=2)

            first_comment = PostComment.objects.create(
                post=post,
                user=commenter_a,
                body=(
                    "Хороший разбор. Больше всего понравилось, что здесь есть конкретный вывод, "
                    "а не просто пересказ проблемы."
                ),
            )
            reply_comment = PostComment.objects.create(
                post=post,
                user=commenter_b,
                parent=first_comment,
                body=(
                    "Согласен. И еще полезно, что видно, какие решения уже проверили, "
                    "а какие пока только выглядят красиво на бумаге."
                ),
            )
            PostComment.objects.filter(id=first_comment.id).update(
                created_at=base_time,
                updated_at=base_time,
            )
            PostComment.objects.filter(id=reply_comment.id).update(
                created_at=base_time + timedelta(minutes=35),
                updated_at=base_time + timedelta(minutes=35),
            )

            comments_count = PostComment.objects.filter(post=post, is_deleted=False).count()
            Post.objects.filter(id=post.id).update(comments_count=comments_count)

    def _create_post_feedback(self, posts: dict[str, Post], users: dict[str, User], now) -> None:
        for index, topic in enumerate(DEMO_TOPICS):
            post = posts[topic.community_slug]
            voters = [
                users[DEMO_USERS[(index + 3) % len(DEMO_USERS)].username],
                users[DEMO_USERS[(index + 4) % len(DEMO_USERS)].username],
                users[DEMO_USERS[(index + 5) % len(DEMO_USERS)].username],
            ]
            values = [1, 1, -1 if index % 4 == 0 else 1]
            for vote_index, (user, value) in enumerate(zip(voters, values, strict=True)):
                like = PostLike.objects.create(post=post, user=user, value=value)
                PostLike.objects.filter(id=like.id).update(
                    created_at=now - timedelta(days=8 - index, minutes=vote_index * 11)
                )
                AuthorRatingEvent.objects.create(
                    author=post.author,
                    actor=user,
                    post=post,
                    event_type=AuthorRatingEvent.EVENT_TYPE_POST_LIKE,
                    delta=value,
                )

        for author in Author.objects.filter(username__in=DEMO_AUTHOR_USERNAMES):
            rating_total = (
                AuthorRatingEvent.objects.filter(author=author).aggregate(total=Sum("delta")).get("total")
                or 0
            )
            Author.objects.filter(id=author.id).update(rating_total=int(rating_total))

        for post in Post.objects.filter(author__username__in=DEMO_AUTHOR_USERNAMES):
            rating_total = (
                PostLike.objects.filter(post=post).aggregate(total=Sum("value")).get("total") or 0
            )
            Post.objects.filter(id=post.id).update(rating=int(rating_total))

    def _create_comuns(
        self,
        posts: dict[str, Post],
        users: dict[str, User],
        tags: dict[str, Tag],
        now,
    ) -> None:
        for index, topic in enumerate(DEMO_TOPICS):
            creator = users[DEMO_USERS[index].username]
            moderator = users[DEMO_USERS[(index + 1) % len(DEMO_USERS)].username]
            comun = Comun.objects.create(
                name=topic.community_name,
                slug=topic.community_slug,
                creator=creator,
                website_url=f"https://example.com/{topic.community_slug}",
                logo_url=f"https://api.dicebear.com/8.x/shapes/svg?seed={topic.community_slug}",
                product_description=(
                    f"{topic.community_name} для обсуждения практики, заметок и конкретных разборов без пустых анонсов."
                ),
                rules_text="Пишите по теме, спорьте по существу, не захламляйте ленту рекламой.",
                target_audience="Люди, которым нужны внятные наблюдения, примеры и аргументы.",
                glossary_enabled=index < 5,
                roadmap_enabled=True,
                minimum_author_rating_to_post=0,
                only_moderators_can_post=False,
                forbid_external_links=False,
                rating_score=0,
                votes_up=0,
                votes_down=0,
                hide_from_home=False,
                allowed_post_templates=["basic"],
                is_active=True,
                sort_order=index + 1,
            )
            comun.tags.add(tags[topic.tag_name], tags["Дискуссия"])
            comun.moderators.add(creator, moderator)
            Comun.objects.filter(id=comun.id).update(
                created_at=now - timedelta(days=10 - index),
                updated_at=now - timedelta(days=10 - index) + timedelta(minutes=15),
            )

            category_main = ComunCategory.objects.create(
                comun=comun,
                name=topic.category_name,
                slug="main",
                description=f"Основная категория для темы {topic.community_name}.",
                sort_order=1,
                allowed_post_templates=[],
                only_moderators_can_post=False,
                is_active=True,
            )
            category_notes = ComunCategory.objects.create(
                comun=comun,
                name="Заметки",
                slug="notes",
                description="Короткие наблюдения и полезные ссылки.",
                sort_order=2,
                allowed_post_templates=[],
                only_moderators_can_post=False,
                is_active=True,
            )
            comun.categories.add(category_main, category_notes)

            if index < 5:
                ComunGlossaryTerm.objects.create(
                    comun=comun,
                    term=topic.glossary_term,
                    slug=f"term-{index + 1}",
                    definition=topic.glossary_definition,
                    sort_order=1,
                    is_active=True,
                )

            ComunPostCategoryAssignment.objects.create(
                comun=comun,
                post=posts[topic.community_slug],
                category=category_main,
                assigned_by=creator,
            )

            vote_values = [1, 1, 1, -1 if index % 3 == 0 else 1]
            vote_users = [
                users[DEMO_USERS[(index + 2) % len(DEMO_USERS)].username],
                users[DEMO_USERS[(index + 3) % len(DEMO_USERS)].username],
                users[DEMO_USERS[(index + 4) % len(DEMO_USERS)].username],
                users[DEMO_USERS[(index + 5) % len(DEMO_USERS)].username],
            ]
            for vote_user, vote_value in zip(vote_users, vote_values, strict=True):
                ComunVote.objects.create(comun=comun, user=vote_user, value=vote_value)

            votes_up = ComunVote.objects.filter(comun=comun, value=1).count()
            votes_down = ComunVote.objects.filter(comun=comun, value=-1).count()
            Comun.objects.filter(id=comun.id).update(
                votes_up=votes_up,
                votes_down=votes_down,
                rating_score=votes_up - votes_down,
            )
