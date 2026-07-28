from __future__ import annotations

from feeds.translation_service import (
    PostTranslationError,
    _parse_translated_json_payload,
    _request_openrouter_json_translation,
)


def summarize_telegram_messages(source_text: str) -> tuple[str, str]:
    text = str(source_text or "").strip()
    if not text:
        raise PostTranslationError("Нет текста для саммари")

    response_payload = _request_openrouter_json_translation(
        {"messages": text[:20000]},
        system_prompt=(
            "You summarize a Telegram discussion for a community knowledge base. "
            "Write in the main language of the supplied messages. Return only valid JSON "
            "with keys title and summary. Keep facts, decisions, useful arguments, names, "
            "numbers, and links. Remove repetition and conversational filler. Do not invent "
            "facts or add commentary outside JSON."
        ),
        timeout_seconds=45,
    )
    payload = _parse_translated_json_payload(response_payload)
    title = str(payload.get("title") or "").strip()[:255]
    summary = str(payload.get("summary") or "").strip()[:20000]
    if not title or not summary:
        raise PostTranslationError("ИИ вернул пустой заголовок или текст саммари")
    return title, summary


__all__ = ["summarize_telegram_messages"]
