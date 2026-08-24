from __future__ import annotations

import re

CORE_INTENTS = (
    "GREETING",
    "THANKS",
    "ACKNOWLEDGMENT",
    "CONVERSATION_CLOSE",
    "DECLINE",
    "CONSIDERING",
    "SIMPLE_CONTINUATION",
    "PRESALES_INTEREST",
    "PRICING_INQUIRY",
    "PACKAGE_SELECTION",
    "HOW_TO",
    "TECHNICAL_SUPPORT",
    "FACTUAL_INFORMATION",
    "REQUEST_OWNER",
    "COMPLAINT",
    "REFUND_INFORMATION",
    "REFUND_AUTHORIZATION",
    "DISCOUNT_INFORMATION",
    "DISCOUNT_REQUEST",
    "PRIVATE_DATA_REQUEST",
    "BINDING_COMMITMENT",
    "SENSITIVE_ACTION",
    "UNCLEAR",
    "SPAM",
)

SOCIAL_INTENTS = frozenset(
    {
        "GREETING",
        "THANKS",
        "ACKNOWLEDGMENT",
        "CONVERSATION_CLOSE",
        "DECLINE",
        "CONSIDERING",
        "SIMPLE_CONTINUATION",
    }
)
SENSITIVE_INTENTS = frozenset(
    {
        "REFUND_AUTHORIZATION",
        "DISCOUNT_REQUEST",
        "PRIVATE_DATA_REQUEST",
        "BINDING_COMMITMENT",
        "SENSITIVE_ACTION",
    }
)
SAFE_CLARIFICATION_INTENTS = frozenset(
    {
        "UNCLEAR",
        "PRESALES_INTEREST",
        "PACKAGE_SELECTION",
        "HOW_TO",
        "TECHNICAL_SUPPORT",
        "FACTUAL_INFORMATION",
    }
)
BUSINESS_FACT_INTENTS = frozenset(
    {
        "PRESALES_INTEREST",
        "PRICING_INQUIRY",
        "PACKAGE_SELECTION",
        "HOW_TO",
        "TECHNICAL_SUPPORT",
        "FACTUAL_INFORMATION",
        "COMPLAINT",
        "REFUND_INFORMATION",
        "DISCOUNT_INFORMATION",
    }
)

_ALIASES = {
    "THANK_YOU": "THANKS",
    "GRATITUDE": "THANKS",
    "ACK": "ACKNOWLEDGMENT",
    "ACKNOWLEDGEMENT": "ACKNOWLEDGMENT",
    "CLOSE": "CONVERSATION_CLOSE",
    "CLOSING": "CONVERSATION_CLOSE",
    "NOT_INTERESTED": "DECLINE",
    "THINKING": "CONSIDERING",
    "FOLLOW_UP": "SIMPLE_CONTINUATION",
    "PRE_SALES": "PRESALES_INTEREST",
    "PRE_SALES_INTEREST": "PRESALES_INTEREST",
    "SUBSCRIPTION_INTEREST": "PRESALES_INTEREST",
    "PRICE_INQUIRY": "PRICING_INQUIRY",
    "PACKAGE_INQUIRY": "PACKAGE_SELECTION",
    "ONBOARDING": "HOW_TO",
    "TROUBLESHOOTING": "TECHNICAL_SUPPORT",
    "QUESTION": "FACTUAL_INFORMATION",
    "REQUEST_HUMAN": "REQUEST_OWNER",
    "HUMAN_REQUEST": "REQUEST_OWNER",
    "REFUND_INQUIRY": "REFUND_INFORMATION",
    "REFUND_REQUEST": "REFUND_AUTHORIZATION",
    "DISCOUNT_INQUIRY": "DISCOUNT_INFORMATION",
    "DISCOUNT_GRANT": "DISCOUNT_REQUEST",
    "PRIVATE_INFORMATION_REQUEST": "PRIVATE_DATA_REQUEST",
    "LEGAL_COMMITMENT": "BINDING_COMMITMENT",
    "UNKNOWN": "UNCLEAR",
}
_LABEL_SANITIZER = re.compile(r"[^A-Z0-9_]+")


def canonicalize_intent(value: str) -> str:
    normalized = _LABEL_SANITIZER.sub("_", str(value or "").strip().upper()).strip("_")
    normalized = _ALIASES.get(normalized, normalized)
    return normalized if normalized in CORE_INTENTS else "UNCLEAR"


def classifier_taxonomy_prompt() -> str:
    labels = ", ".join(CORE_INTENTS)
    return (
        f"Choose exactly one intent from: {labels}. "
        "Use THANKS/ACKNOWLEDGMENT/CONVERSATION_CLOSE/DECLINE/CONSIDERING for social "
        "turns and natural conversation endings. PRESALES_INTEREST is interest before buying or "
        "joining; HOW_TO is setup or usage after selection. PRICING_INQUIRY, "
        "REFUND_INFORMATION, and DISCOUNT_INFORMATION ask only for published information and are "
        "normally LOW risk when grounded. REFUND_AUTHORIZATION requests an actual refund decision; "
        "DISCOUNT_REQUEST asks to grant an unapproved discount; BINDING_COMMITMENT asks for a "
        "contract, guaranteed promise, compensation, deadline, or decision on the owner's behalf; "
        "those are HIGH. Topic words such as price, payment, subscription, refund, or discount do "
        "not by themselves make a message HIGH. Risk follows the requested action, authority, and "
        "context. If the contact explicitly asks for the owner, choose REQUEST_OWNER."
    )
