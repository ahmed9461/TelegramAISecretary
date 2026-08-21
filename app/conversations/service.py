from dataclasses import dataclass

from app.db.enums import ConversationState, GlobalMode


@dataclass(slots=True)
class ConversationContext:
    state: ConversationState
    global_mode: GlobalMode
    contact_excluded: bool = False
    ai_allowed: bool = True


def effective_state(ctx: ConversationContext) -> ConversationState:
    if ctx.contact_excluded:
        return ConversationState.EXCLUDED
    if not ctx.ai_allowed:
        return ConversationState.OBSERVE_ONLY
    if ctx.state in {
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.EXCLUDED,
        ConversationState.PAUSED,
        ConversationState.ESCALATED,
    }:
        return ctx.state
    if ctx.global_mode == GlobalMode.OFF:
        return ConversationState.PAUSED
    if ctx.global_mode == GlobalMode.OBSERVE:
        return ConversationState.OBSERVE_ONLY
    if ctx.global_mode == GlobalMode.APPROVAL:
        return ConversationState.AI_APPROVAL
    return ConversationState.AI_AUTO
