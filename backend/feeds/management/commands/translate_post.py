from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from feeds.models import Post
from feeds.translation_service import (
    SUPPORTED_TRANSLATION_LANGUAGES,
    PostTranslationError,
    translate_post_to_language,
)


class Command(BaseCommand):
    help = "Translate a post into one or more supported languages."

    def add_arguments(self, parser):
        parser.add_argument("post_id", type=int)
        parser.add_argument(
            "--language",
            action="append",
            choices=tuple(SUPPORTED_TRANSLATION_LANGUAGES),
            dest="languages",
            help="Target language code. Can be passed multiple times.",
        )

    def handle(self, *args, **options):
        post_id = options["post_id"]
        languages = options.get("languages") or list(SUPPORTED_TRANSLATION_LANGUAGES)
        try:
            post = Post.objects.get(pk=post_id)
        except Post.DoesNotExist as exc:
            raise CommandError(f"Post {post_id} does not exist") from exc

        for language in languages:
            if language == post.original_language:
                continue
            try:
                translation = translate_post_to_language(post, language)
            except PostTranslationError as exc:
                self.stderr.write(f"{language}: {exc}")
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"{language}: translation {translation.pk} is {translation.status}"
                )
            )
