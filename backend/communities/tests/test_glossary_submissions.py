import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Comun, ComunTelegramSubmission
from notifications.models import SiteNotification
from users import service as user_service


User = get_user_model()


class ComunGlossarySubmissionNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.moderator = User.objects.create_user(username="moderator")
        self.proposer = User.objects.create_user(username="proposer")
        self.comun = Comun.objects.create(
            name="Glossary Community",
            slug="glossary-community",
            creator=self.owner,
            glossary_enabled=True,
        )
        self.comun.moderators.add(self.moderator)

    def _token_headers(self, user):
        token = user_service._issue_token(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_glossary_submission_notifies_comun_team(self):
        with patch("notifications.service.send_site_notification_to_push"):
            response = self.client.post(
                reverse("comun-glossary-submission-create", kwargs={"slug": self.comun.slug}),
                data=json.dumps(
                    {
                        "glossary_term": "Новый термин",
                        "glossary_term_en": "New term",
                        "glossary_definition": "Расшифровка термина",
                    }
                ),
                content_type="application/json",
                **self._token_headers(self.proposer),
            )

        self.assertEqual(response.status_code, 201, response.content.decode())
        submission = ComunTelegramSubmission.objects.get()
        notifications = SiteNotification.objects.filter(
            event_key="comun_telegram_submission",
            payload__submission_id=submission.id,
        )
        self.assertEqual(notifications.count(), 2)
        self.assertTrue(notifications.filter(user=self.owner).exists())
        self.assertTrue(notifications.filter(user=self.moderator).exists())
        self.assertFalse(notifications.filter(user=self.proposer).exists())

    def test_approve_glossary_submission_notifies_proposer(self):
        submission = ComunTelegramSubmission.objects.create(
            comun=self.comun,
            request_type=ComunTelegramSubmission.TYPE_GLOSSARY,
            requested_by=self.proposer,
            telegram_chat_id=-100,
            telegram_source_message_id=-1,
            source_text="Расшифровка",
            glossary_term="Термин",
            glossary_definition="Расшифровка",
        )

        with patch("notifications.service.send_site_notification_to_push"):
            response = self.client.patch(
                reverse(
                    "comun-telegram-submission-detail",
                    kwargs={"slug": self.comun.slug, "submission_id": submission.id},
                ),
                data=json.dumps({"action": "approve"}),
                content_type="application/json",
                **self._token_headers(self.owner),
            )

        self.assertEqual(response.status_code, 200, response.content.decode())
        notification = SiteNotification.objects.get(
            user=self.proposer,
            event_key="glossary_term_submission_reviewed",
            payload__submission_id=submission.id,
        )
        self.assertEqual(notification.title, "Термин принят")
        self.assertEqual(notification.payload["status"], ComunTelegramSubmission.STATUS_APPROVED)

    def test_reject_glossary_submission_notifies_proposer(self):
        submission = ComunTelegramSubmission.objects.create(
            comun=self.comun,
            request_type=ComunTelegramSubmission.TYPE_GLOSSARY,
            requested_by=self.proposer,
            telegram_chat_id=-100,
            telegram_source_message_id=-2,
            source_text="Расшифровка",
            glossary_term="Термин",
            glossary_definition="Расшифровка",
        )

        with patch("notifications.service.send_site_notification_to_push"):
            response = self.client.patch(
                reverse(
                    "comun-telegram-submission-detail",
                    kwargs={"slug": self.comun.slug, "submission_id": submission.id},
                ),
                data=json.dumps({"action": "reject"}),
                content_type="application/json",
                **self._token_headers(self.owner),
            )

        self.assertEqual(response.status_code, 200, response.content.decode())
        notification = SiteNotification.objects.get(
            user=self.proposer,
            event_key="glossary_term_submission_reviewed",
            payload__submission_id=submission.id,
        )
        self.assertEqual(notification.title, "Термин не принят")
        self.assertEqual(notification.payload["status"], ComunTelegramSubmission.STATUS_REJECTED)
