from django.test import SimpleTestCase
from rabotaem_backend.read_context import read_context, memoize_read


class ReadContextTests(SimpleTestCase):
    def test_values_are_reused_only_within_scope_and_reset_after_error(self):
        calls = []

        @memoize_read
        def load(key):
            calls.append(key)
            return len(calls)

        self.assertEqual(load("a"), 1)
        self.assertEqual(load("a"), 2)
        with self.assertRaises(ValueError):
            with read_context():
                self.assertEqual(load("a"), 3)
                self.assertEqual(load("a"), 3)
                with read_context():
                    self.assertEqual(load("a"), 4)
                self.assertEqual(load("a"), 3)
                raise ValueError("failed read")
        with read_context():
            self.assertEqual(load("a"), 5)
