from app.db.enums import ConversationState


_ALLOWED: dict[ConversationState, set[ConversationState]] = {
    ConversationState.AI_AUTO: {
        ConversationState.AI_APPROVAL,
        ConversationState.OBSERVE_ONLY,
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.ESCALATED,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
    },
    ConversationState.AI_APPROVAL: {
        ConversationState.AI_AUTO,
        ConversationState.OBSERVE_ONLY,
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.ESCALATED,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
    },
    ConversationState.OBSERVE_ONLY: {
        ConversationState.AI_AUTO,
        ConversationState.AI_APPROVAL,
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
    },
    ConversationState.HUMAN_TAKEOVER: {
        ConversationState.AI_AUTO,
        ConversationState.AI_APPROVAL,
        ConversationState.OBSERVE_ONLY,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
    },
    ConversationState.ESCALATED: {
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.AI_AUTO,
        ConversationState.AI_APPROVAL,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
    },
    ConversationState.PAUSED: {
        ConversationState.AI_AUTO,
        ConversationState.AI_APPROVAL,
        ConversationState.OBSERVE_ONLY,
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.EXCLUDED,
    },
    ConversationState.EXCLUDED: set(),
}


def can_transition(current: ConversationState, target: ConversationState, *, explicit_unexclude: bool = False) -> bool:
    if current == target:
        return True
    if current == ConversationState.EXCLUDED:
        return explicit_unexclude and target != ConversationState.EXCLUDED
    return target in _ALLOWED[current]


def transition(current: ConversationState, target: ConversationState, *, explicit_unexclude: bool = False) -> ConversationState:
    if not can_transition(current, target, explicit_unexclude=explicit_unexclude):
        raise ValueError(f"invalid conversation transition: {current} -> {target}")
    return target
