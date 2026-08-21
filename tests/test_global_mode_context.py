from app.conversations.context import effective_state_for_global_mode
from app.db.enums import ConversationState, GlobalMode


def test_global_approval_restricts_auto_conversation() -> None:
    assert (
        effective_state_for_global_mode(
            conversation_state=ConversationState.AI_AUTO.value,
            global_mode=GlobalMode.APPROVAL.value,
        )
        == ConversationState.AI_APPROVAL.value
    )


def test_global_auto_does_not_loosen_human_takeover() -> None:
    assert (
        effective_state_for_global_mode(
            conversation_state=ConversationState.HUMAN_TAKEOVER.value,
            global_mode=GlobalMode.AUTO.value,
        )
        == ConversationState.HUMAN_TAKEOVER.value
    )


def test_observe_and_off_suppress_replies() -> None:
    assert (
        effective_state_for_global_mode(
            conversation_state=ConversationState.AI_AUTO.value,
            global_mode=GlobalMode.OBSERVE.value,
        )
        == ConversationState.OBSERVE_ONLY.value
    )
    assert (
        effective_state_for_global_mode(
            conversation_state=ConversationState.AI_AUTO.value,
            global_mode=GlobalMode.OFF.value,
        )
        == ConversationState.PAUSED.value
    )
