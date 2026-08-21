from types import SimpleNamespace

from app.interface.service import menu_item_matches_context
from app.telegram.resilient_bot import is_owner_bound_method


def test_empty_visibility_rules_are_always_visible() -> None:
    assert menu_item_matches_context({}, {"text": "أي شيء"}) is True


def test_contextual_button_matches_customer_or_reply_text() -> None:
    rules = {
        "mode": "CONTEXTUAL",
        "keywords": ["دفع", "سداد", "كريبتو"],
    }
    assert menu_item_matches_context(rules, {"user_text": "كيف اقدر اسدد؟"}) is True
    assert menu_item_matches_context(rules, {"reply_text": "طرق الدفع المتاحة كالتالي"}) is True
    assert menu_item_matches_context(rules, {"text": "ما هي ساعات العمل؟"}) is False


def test_contextual_button_can_match_explicit_intent() -> None:
    rules = {"mode": "CONTEXTUAL", "intents": ["PAYMENT_METHODS"]}
    assert menu_item_matches_context(rules, {"intent": "payment_methods"}) is True
    assert menu_item_matches_context(rules, {"intent": "SUPPORT"}) is False


def test_telegram_retry_is_scoped_to_owner_chat_only() -> None:
    owner_method = SimpleNamespace(chat_id=123)
    customer_method = SimpleNamespace(chat_id=456)
    no_chat_method = SimpleNamespace()

    assert is_owner_bound_method(owner_method, owner_chat_id=123) is True
    assert is_owner_bound_method(customer_method, owner_chat_id=123) is False
    assert is_owner_bound_method(no_chat_method, owner_chat_id=123) is False
