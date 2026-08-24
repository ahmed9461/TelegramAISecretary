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


def test_customer_copy_removes_only_repeated_opening_greeting() -> None:
    assert polish_candidate_reply(
        "هلا والله! الباقة الأنسب لأربع مجموعات هي الباقة المرنة.",
        allow_greeting=False,
    ) == "الباقة الأنسب لأربع مجموعات هي الباقة المرنة."
    assert polish_candidate_reply(
        "أهلا بك، يسعدني توضيح خطوات الاشتراك.",
        allow_greeting=False,
    ) == "يسعدني توضيح خطوات الاشتراك."
    assert polish_candidate_reply(
        "أهلًا بكم، هذه هي الباقات المتاحة.",
        allow_greeting=False,
    ) == "هذه هي الباقات المتاحة."
    assert polish_candidate_reply(
        "أهلاوية الخدمة مذكورة في المصدر.",
        allow_greeting=False,
    ) == "أهلاوية الخدمة مذكورة في المصدر."
    assert polish_candidate_reply("أهلًا بك! كيف أقدر أساعدك؟") == "أهلًا بك! كيف أقدر أساعدك؟"


def test_customer_copy_removes_raw_markdown_markers() -> None:
    assert polish_candidate_reply(
        "# الباقات\n\n- **الخيار المرن**\n- `الخيار الاحترافي`"
    ) == "الباقات\n\n• الخيار المرن\n• الخيار الاحترافي"
