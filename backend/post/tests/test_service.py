from django.core import mail
from django.test import SimpleTestCase, override_settings

from post.service import send_email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.test",
)
class PostEmailServiceTests(SimpleTestCase):
    def setUp(self):
        mail.outbox = []

    def test_send_email_sends_plain_text_message(self):
        delivery = send_email(
            subject="Welcome",
            to=["reader@example.test"],
            text="Hello",
        )

        self.assertEqual(delivery.sent_count, 1)
        self.assertEqual(delivery.recipients, ("reader@example.test",))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Welcome")
        self.assertEqual(mail.outbox[0].body, "Hello")
        self.assertEqual(mail.outbox[0].from_email, "noreply@example.test")

    def test_send_email_sends_html_alternative(self):
        send_email(
            subject="Digest",
            to="reader@example.test",
            text="Digest",
            html="<p>Digest</p>",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].alternatives[0], ("<p>Digest</p>", "text/html"))

    def test_send_email_requires_recipient(self):
        with self.assertRaisesMessage(ValueError, "to must contain at least one email address"):
            send_email(subject="Welcome", to=[], text="Hello")

    def test_send_email_requires_body(self):
        with self.assertRaisesMessage(ValueError, "text or html body is required"):
            send_email(subject="Welcome", to="reader@example.test")
