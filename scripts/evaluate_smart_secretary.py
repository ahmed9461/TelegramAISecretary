from __future__ import annotations

import argparse
import asyncio
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.deepseek import DeepSeekAIProvider
from app.ai.policy import choose_action
from app.ai.schemas import Confidence
from app.config import get_settings
from app.conversations.context import effective_state_for_global_mode
from app.conversations.continuity import resolve_conversation_continuity
from app.db.base import Base
from app.db.enums import ConversationState, RiskLevel, Visibility
from app.db.models import KnowledgeItem, Owner
from app.knowledge.retrieval import retrieve_knowledge
from app.telegram.professional_copy import decision_reason_text

HIGH_CONFIDENCE = Confidence(intent=0.94, retrieval=0.9, answer=0.92, policy=0.95)


@dataclass(slots=True)
class Score:
    passed: int = 0
    total: int = 0
    failures: list[str] | None = None

    def check(self, ok: bool, case_id: str = "") -> None:
        self.total += 1
        self.passed += int(ok)
        if not ok:
            if self.failures is None:
                self.failures = []
            self.failures.append(case_id or f"case-{self.total}")


def _load_dataset() -> dict:
    path = Path(__file__).parents[1] / "evals" / "smart_secretary_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _supported_call(function, **kwargs):
    parameters = inspect.signature(function).parameters
    return function(**{key: value for key, value in kwargs.items() if key in parameters})


def _offline_scores(dataset: dict) -> dict[str, Score]:
    scores = {
        name: Score() for name in ("policy", "global_state", "continuity", "retrieval", "reason")
    }

    for case in dataset["policy_cases"]:
        decision = _supported_call(
            choose_action,
            state=ConversationState(case["state"]),
            intent=case["intent"],
            risk=RiskLevel(case["risk"]),
            confidence=HIGH_CONFIDENCE,
            has_grounding=case["grounding"],
            has_public_grounding=case["public_grounding"],
            has_conflicting_grounding=case.get("conflict", False),
            needs_more_info=case.get("needs_more_info", False),
        )
        scores["policy"].check(decision.action.value == case["expected_action"], case["id"])

    for case in dataset["global_state_cases"]:
        actual = _supported_call(
            effective_state_for_global_mode,
            conversation_state=case["conversation_state"],
            global_mode=case["global_mode"],
            state_is_explicit=case["state_is_explicit"],
        )
        scores["global_state"].check(actual == case["expected_state"], case["id"])

    for case in dataset["continuity_cases"]:
        messages = [
            SimpleNamespace(direction=direction, text=text) for direction, text in case["messages"]
        ]
        result = resolve_conversation_continuity(case["text"], messages)
        ok = result.contextual_short_reply is case["expected_contextual"]
        if "expected_exact" in case:
            ok = ok and result.resolved_text == case["expected_exact"]
        ok = ok and all(
            value in result.resolved_text for value in case.get("expected_contains", [])
        )
        scores["continuity"].check(ok, case["id"])

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = Owner(telegram_user_id=987654321, display_name="Eval Owner")
        session.add(owner)
        session.flush()
        expected_by_id: dict[int, str] = {}
        for item in dataset["knowledge"]:
            row = KnowledgeItem(
                owner_id=owner.id,
                type=item["type"],
                title=item["title"],
                content=item["content"],
                visibility=Visibility.PUBLIC.value,
                tags_json=item.get("tags", []),
            )
            session.add(row)
            session.flush()
            expected_by_id[row.id] = item["key"]
        session.commit()
        for case in dataset["retrieval_cases"]:
            hits = retrieve_knowledge(session, owner_id=owner.id, query=case["query"], limit=1)
            actual = expected_by_id.get(hits[0].id) if hits else None
            scores["retrieval"].check(actual == case["expected_key"], case["id"])

    reason_outputs: list[str] = []
    for case in dataset["reason_cases"]:
        output = _supported_call(
            decision_reason_text,
            reason_code=case["reason_code"],
            intent=case["intent"],
            risk=case["risk"],
        )
        reason_outputs.append(output)
        scores["reason"].check(
            all(value in output for value in case["expected_contains"]), case["id"]
        )
    # Case-specific explanations must not collapse to one generic sentence.
    scores["reason"].check(
        len(set(reason_outputs)) >= len(reason_outputs) - 1, "reason_distinctness"
    )
    return scores


async def _live_classifier_score(dataset: dict) -> Score:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DeepSeek is not configured; live classifier eval was not run")
    provider = DeepSeekAIProvider(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        thinking_enabled=settings.deepseek_thinking_enabled,
        max_retries=settings.ai_max_retries,
        retry_base_seconds=settings.ai_retry_base_seconds,
    )
    score = Score()
    for case in dataset["classifier_cases"]:
        decision = await provider.classify_and_decide(
            text=case["text"],
            context={
                "state": ConversationState.AI_AUTO.value,
                "has_grounding": case["grounding"],
                "has_public_grounding": case["grounding"],
                "retrieval_confidence": 0.9 if case["grounding"] else 0.0,
                "recent_messages": [],
            },
        )
        expected_intents = case.get("expected_intents") or [case["expected_intent"]]
        ok = (
            decision.intent in expected_intents
            and decision.risk.value == case["expected_risk"]
            and decision.action.value == case["expected_action"]
        )
        actual = f"{decision.intent}/{decision.risk.value}/{decision.action.value}"
        score.check(ok, f"{case['id']}[{actual}]")
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeatable Smart Secretary behavior eval")
    parser.add_argument("--live-provider", action="store_true")
    args = parser.parse_args()
    dataset = _load_dataset()
    scores = _offline_scores(dataset)
    if args.live_provider:
        scores["classifier_live"] = asyncio.run(_live_classifier_score(dataset))
    total_passed = sum(score.passed for score in scores.values())
    total_cases = sum(score.total for score in scores.values())
    for name, score in scores.items():
        suffix = f" failures={','.join(score.failures or [])}" if score.failures else ""
        print(f"{name}: {score.passed}/{score.total}{suffix}")
    print(f"smart-secretary total: {total_passed}/{total_cases}")
    return 0 if total_passed == total_cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
