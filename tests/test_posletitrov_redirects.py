"""Offline migration contract tests; integration checks also run against nginx."""
import copy
import unittest

from deploy.import_posletitrov_redirects import NginxRedirectRenderer, WordPressRedirectImporter


class RedirectImportTests(unittest.TestCase):
    def setUp(self):
        self.importer = WordPressRedirectImporter()

    def row(self, path="/articles/film", target="https://tambur.pub/b/post/1-film", source_id="1"):
        return {"redirect": {"id": source_id, "from": "https://posletitrov.ru" + path,
                "match": path, "to": target, "type": "redirection", "status": "1"},
                "metas": {"ignore_case": "1", "ignore_parameters": "1",
                "ignore_trailing_slashes": "1", "redirect_code": "301",
                "pass_on_parameters": "", "inclusion_exclusion_rules": "",
                "redirection_http_headers": ""}}

    def test_equivalent_slash_case_and_encoded_source_are_collapsed(self):
        for path in ("/articles/Film", "/articles/film/", "/articles/%66ilm"):
            self.importer.add_exact(self.row(path))
        self.assertEqual(list(self.importer.redirects), ["/articles/film"])
        self.assertEqual(self.importer.duplicates, 2)

    def test_existing_tag_destination_wins_independently_of_order(self):
        tag = self.row("/tag/film", "https://tambur.pub/tags/фильм", "2")
        article = self.row("/tag/film")
        for rows in ((tag, article), (article, tag)):
            importer = WordPressRedirectImporter()
            for row in rows:
                importer.add_exact(row)
            self.assertEqual(importer.redirects["/tag/film"].target,
                             "https://tambur.pub/tags/%D1%84%D0%B8%D0%BB%D1%8C%D0%BC")
            self.assertEqual(len(importer.conflicts), 1)

    def test_unexpected_conflict_is_not_silently_overwritten(self):
        self.importer.add_exact(self.row())
        with self.assertRaisesRegex(ValueError, "Unresolved"):
            self.importer.add_exact(self.row(target="https://tambur.pub/b/post/2-other"))

    def test_html_entities_spaces_cyrillic_and_variables_are_encoded(self):
        self.assertEqual(self.importer.target_url("https://tambur.pub/tags/О&#039;Брайен $host"),
                         "https://tambur.pub/tags/%D0%9E%27%D0%91%D1%80%D0%B0%D0%B9%D0%B5%D0%BD%20%24host")
        self.assertEqual(self.importer.target_url("https://tambur.pub/tags/rock%20music"),
                         "https://tambur.pub/tags/rock%20music")

    def test_external_targets_and_header_injection_are_rejected(self):
        for target in ("https://evil.example/a", "https://tambur.pub@evil.example/b/post/1",
                       "https://tambur.pub/b/post/1%0d%0aHeader:bad", "http://tambur.pub/b/post/1",
                       "https://tambur.pub/b/post/1#fragment"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.importer.add_exact(self.row(target=target))

    def test_conditional_query_or_non_301_rules_fail_closed(self):
        for key, value in (("ignore_parameters", "0"), ("redirect_code", "302"),
                           ("rules_group1", {"enabled": "1"})):
            row = self.row()
            row["metas"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.importer.add_exact(row)
        with self.assertRaises(ValueError):
            self.importer.add_exact(self.row("/articles/film?p=123"))

    def rule(self, expression, condition="regex-match"):
        row = self.row()
        row["redirect"]["type"] = "redirection_rule"
        row["metas"].update(criterias=[{"criteria": condition, "value": expression}],
                            action={"name": "a-specific-url", "value": row["redirect"]["to"]})
        return row

    def test_pagination_is_anchored_and_drops_source_query(self):
        self.importer.add_pagination(self.rule("https://posletitrov.ru/articles/page/[0-9]+/"))
        self.importer.add_pagination(self.rule("/page/[0-9]+/"))
        rendered = NginxRedirectRenderer().render(self.importer)
        self.assertIn('"~*^/articles/page/[0-9]+/?$"', rendered)
        self.assertIn('"~*^/page/[0-9]+/?$"', rendered)
        self.assertNotIn("$args", rendered)

    def test_only_known_literal_regex_mistake_is_repaired(self):
        self.importer.add_pagination(self.rule("https://posletitrov.ru/articles/tv-series/page/[0-9]+/", "end-with"))
        self.assertEqual(self.importer.repaired_rules, ["1"])
        with self.assertRaises(ValueError):
            self.importer.add_pagination(self.rule("/articles/page/[0-9]+/", "end-with"))
        with self.assertRaises(ValueError):
            self.importer.add_pagination(self.rule("/.*"))

    def test_unicode_paths_have_case_insensitive_fallback(self):
        self.importer.add_exact(self.row("/tag/кино"))
        rendered = NginxRedirectRenderer().render(self.importer)
        self.assertIn('"/tag/кино/"', rendered)
        self.assertIn('"~*(*UTF)(*UCP)^/tag/кино/?$"', rendered)


if __name__ == "__main__":
    unittest.main()
