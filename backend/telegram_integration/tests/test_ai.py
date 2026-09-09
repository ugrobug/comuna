from unittest.mock import patch

from django.test import SimpleTestCase

from telegram_integration.ai import summarize_telegram_messages


class TelegramSummaryPromptTests(SimpleTestCase):
    def test_custom_prompt_is_added_without_replacing_summary_contract(self):
        with (
            patch(
                "telegram_integration.ai._request_openrouter_json_translation",
                return_value={"response": "payload"},
            ) as request_mock,
            patch(
                "telegram_integration.ai._parse_translated_json_payload",
                return_value={"title": "Итоги", "summary": "Решение принято."},
            ),
        ):
            result = summarize_telegram_messages(
                "Обсуждение команды",
                custom_prompt="Сначала перечисли решения и ответственных.",
            )

        self.assertEqual(result, ("Итоги", "Решение принято."))
        request_payload = request_mock.call_args.args[0]
        system_prompt = request_mock.call_args.kwargs["system_prompt"]
        self.assertEqual(request_payload, {"messages": "Обсуждение команды"})
        self.assertIn("Сначала перечисли решения и ответственных.", system_prompt)
        self.assertIn("valid JSON with title and summary keys", system_prompt)

    def test_custom_prompt_is_limited_to_3000_characters(self):
        with (
            patch(
                "telegram_integration.ai._request_openrouter_json_translation",
                return_value={"response": "payload"},
            ) as request_mock,
            patch(
                "telegram_integration.ai._parse_translated_json_payload",
                return_value={"title": "Итоги", "summary": "Решение принято."},
            ),
        ):
            summarize_telegram_messages("Обсуждение", custom_prompt="x" * 3100)

        system_prompt = request_mock.call_args.kwargs["system_prompt"]
        prompt_block = system_prompt.split("<community_summary_prompt>\n", 1)[1].split(
            "\n</community_summary_prompt>", 1
        )[0]
        self.assertEqual(len(prompt_block), 3000)
