from app.ai.copy import polish_candidate_reply
from app.telegram.professional_copy import (
    decision_reason_text,
    knowledge_type_text,
    knowledge_visibility_text,
    menu_action_text,
    policy_action_text,
)


def test_generic_today_phrase_is_removed_deterministically() -> None:
    assert polish_candidate_reply("مرحبًا! كيف اقدر اساعدك اليوم؟") == ("مرحبًا! كيف أقدر أساعدك؟")
    assert polish_candidate_reply("How can I help you today?") == "How can I help?"


def test_internal_codes_are_not_owner_facing_copy() -> None:
    assert "HIGH_RISK" not in decision_reason_text("HIGH_RISK")
    assert policy_action_text("REQUIRE_APPROVAL") == "مراجعة المالك قبل الإرسال"
    assert menu_action_text("SEND_MESSAGE") == "رد ثابت"
    assert knowledge_type_text("SERVICE") == "خدمة"
    assert "PUBLIC" not in knowledge_visibility_text("PUBLIC")
    assert polish_candidate_reply("السبب: HIGH_RISK\nسأتولى تحويل طلبك.") == ("سأتولى تحويل طلبك.")
