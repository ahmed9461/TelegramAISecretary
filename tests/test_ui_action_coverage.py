from pathlib import Path

from app.telegram.automation_ui import intent_action_keyboard
from app.telegram.owner_ui import main_admin_keyboard


def test_custom_intent_has_meaningful_choices_without_published_flows() -> None:
    keyboard = intent_action_keyboard([])
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert len(labels) == 3
    assert any("فهم" in label for label in labels)
    assert any("رد ثابت" in label for label in labels)
    assert any("تحويل" in label for label in labels)
    assert callbacks == [
        "automation:intent:link:0",
        "automation:intent:link:r",
        "automation:intent:link:h",
    ]


def test_every_main_admin_button_has_a_registered_handler_literal() -> None:
    telegram_dir = Path(__file__).parents[1] / "app" / "telegram"
    handler_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in telegram_dir.glob("*.py")
        if path.name != "owner_ui.py"
    )
    callbacks = [
        button.callback_data
        for row in main_admin_keyboard().inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert callbacks
    assert all(callback in handler_source for callback in callbacks)
