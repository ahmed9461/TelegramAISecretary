from app.conversations.service import ConversationContext, effective_state
from app.db.enums import ConversationState, GlobalMode


def test_global_approval_applies_to_normal_ai_conversation() -> None:
    ctx = ConversationContext(ConversationState.AI_AUTO, GlobalMode.APPROVAL)
    assert effective_state(ctx) == ConversationState.AI_APPROVAL


def test_human_takeover_wins_over_global_auto() -> None:
    ctx = ConversationContext(ConversationState.HUMAN_TAKEOVER, GlobalMode.AUTO)
    assert effective_state(ctx) == ConversationState.HUMAN_TAKEOVER
