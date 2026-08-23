from types import SimpleNamespace

from app.conversations.continuity import resolve_conversation_continuity


def _message(direction: str, text: str):
    return SimpleNamespace(direction=direction, text=text)


def test_numeric_reply_is_resolved_against_latest_secretary_question() -> None:
    result = resolve_conversation_continuity(
        "4",
        [
            _message("IN", "أريد الباقة المناسبة"),
            _message("OUT", "كم عدد المجموعات التي تمتلكها؟"),
            _message("IN", "4"),
        ],
    )

    assert result.contextual_short_reply is True
    assert result.has_prior_outgoing is True
    assert "عدد المجموعات" in result.resolved_text
    assert result.resolved_text.endswith("إجابة العميل: 4")


def test_new_question_is_not_reinterpreted_as_compact_answer() -> None:
    result = resolve_conversation_continuity(
        "كم سعر الاشتراك؟",
        [_message("OUT", "هل تفضّل الخطة الشهرية أم السنوية؟")],
    )

    assert result.contextual_short_reply is False
    assert result.resolved_text == "كم سعر الاشتراك؟"


def test_first_turn_has_no_prior_reply() -> None:
    result = resolve_conversation_continuity("السلام عليكم", [_message("IN", "السلام عليكم")])
    assert result.has_prior_outgoing is False
    assert result.contextual_short_reply is False
