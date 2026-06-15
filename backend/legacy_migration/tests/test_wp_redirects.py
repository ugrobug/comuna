from django.test import SimpleTestCase, TestCase

from feeds.models import Tag
from legacy_migration.wp_redirects import (
    RedirectRow,
    format_redirection_plugin_json,
    merge_redirect_rows,
    normalize_legacy_path,
    path_variants,
    tag_public_path,
)


class WpRedirectsPathTests(SimpleTestCase):
    def test_normalize_full_url(self) -> None:
        self.assertEqual(
            normalize_legacy_path(
                "https://posletitrov.ru/articles/movies/reviews/slug/?utm=1"
            ),
            "/articles/movies/reviews/slug",
        )

    def test_path_variants(self) -> None:
        self.assertEqual(
            path_variants("/articles/foo/"),
            ["/articles/foo", "/articles/foo/"],
        )


class RedirectionExportFormatTests(SimpleTestCase):
    def test_redirection_json_matches_plugin_export_shape(self) -> None:
        rows = [
            RedirectRow(
                from_path="/articles/acolyte",
                to_path="/b/post/16972-2024",
                wp_post_id=19938,
                post_id=16972,
                source="legacy_url",
            ),
            RedirectRow(
                from_path="/articles/acolyte/",
                to_path="/b/post/16972-2024",
                wp_post_id=19938,
                post_id=16972,
                source="legacy_url",
            ),
        ]
        import json

        payload = json.loads(format_redirection_plugin_json(rows))
        self.assertEqual(len(payload), 1)
        entry = payload[0]
        self.assertIn("redirect", entry)
        self.assertIn("metas", entry)
        redir = entry["redirect"]
        self.assertEqual(redir["from"], "https://posletitrov.ru/articles/acolyte")
        self.assertEqual(redir["match"], "/articles/acolyte")
        self.assertEqual(redir["to"], "https://tambur.pub/b/post/16972-2024")
        self.assertEqual(redir["type"], "redirection")
        self.assertEqual(entry["metas"]["ignore_trailing_slashes"], "1")
        self.assertEqual(entry["metas"]["redirect_code"], "301")


class WpTagRedirectTests(TestCase):
    def test_tag_public_path_uses_tag_lemma_when_exists(self) -> None:
        Tag.objects.create(name="Marvel", lemma="marvel")
        self.assertEqual(tag_public_path("Marvel"), "/tags/marvel")

    def test_merge_post_wins_on_same_from(self) -> None:
        from legacy_migration.wp_redirects import RedirectRow

        post = RedirectRow(
            from_path="/tag/foo",
            to_path="/b/post/1",
            wp_post_id=1,
            post_id=1,
            source="legacy_url",
        )
        tag = RedirectRow(
            from_path="/tag/foo",
            to_path="/tags/foo",
            wp_term_id=2,
            source="post_tag",
        )
        merged, conflicts = merge_redirect_rows([post], [tag])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].to_path, "/b/post/1")
        self.assertTrue(conflicts)
