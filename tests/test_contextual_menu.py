from types import SimpleNamespace

import pytest

from app.interface.service import menu_item_matches_context
from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.resilient_bot import is_owner_bound_method


def test_empty_visibility_rules_are_always_visible() -> None:
    assert menu_item_matches_context({}, {"text": "أي شيء"}) is True


def test_contextual_button_matches_customer_or_reply_text() -> None:
    rules = {
        "mode": "CONTEXTUAL",
        "keywords": ["دفع", "سداد", "كريبتو"],
    }
    assert menu_item_matches_context(rules, {"user_text": "ما هي طرق الدفع؟"}) is True
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


@pytest.mark.asyncio
async def test_adapter_forwards_approval_intent_to_default_menu(monkeypatch) -> None:
    captured: dict = {}

    class FakeBot:
        async def send_message(self, **kwargs):
            captured["send"] = kwargs
            return SimpleNamespace(message_id=321)

    def capture_menu(*, chat_id: int, reply_text: str, intent: str = ""):
        captured["menu"] = {
            "chat_id": chat_id,
            "reply_text": reply_text,
            "intent": intent,
        }
        return "menu"

    monkeypatch.setattr(
        AiogramTelegramAdapter,
        "_default_reply_markup",
        staticmethod(capture_menu),
    )
    adapter = AiogramTelegramAdapter(FakeBot())

    message_id = await adapter.send_text(
        business_connection_id="bc-1",
        chat_id=456,
        text="طرق الدفع المتاحة",
        native_rich=False,
        intent="PAYMENT_METHODS",
    )

    assert message_id == 321
    assert captured["menu"]["intent"] == "PAYMENT_METHODS"
    assert captured["send"]["reply_markup"] == "menu"
