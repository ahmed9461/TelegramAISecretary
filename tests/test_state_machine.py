import pytest

from app.conversations.state_machine import transition
from app.db.enums import ConversationState


def test_human_takeover_blocks_until_explicit_return() -> None:
    assert transition(ConversationState.AI_AUTO, ConversationState.HUMAN_TAKEOVER) == ConversationState.HUMAN_TAKEOVER
    assert transition(ConversationState.HUMAN_TAKEOVER, ConversationState.AI_APPROVAL) == ConversationState.AI_APPROVAL


def test_excluded_requires_explicit_unexclude() -> None:
    with pytest.raises(ValueError):
        transition(ConversationState.EXCLUDED, ConversationState.AI_AUTO)
    assert transition(
        ConversationState.EXCLUDED,
        ConversationState.AI_AUTO,
        explicit_unexclude=True,
    ) == ConversationState.AI_AUTO
