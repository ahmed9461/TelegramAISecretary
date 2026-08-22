from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AiRun, Approval, Feedback, Message

logger = logging.getLogger(__name__)


def _numeric_usage(usage: dict[str, Any], key: str) -> int:
    value = usage.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def record_ai_run(
    db: Session,
    *,
    owner_id: int,
    trace_id: str,
    operation: str,
    provider: str,
    model: str,
    status: str,
    conversation_id: int | None = None,
    trigger_message_id: int | None = None,
    intent: str = "",
    risk: str = "",
    action: str = "",
    confidence: dict[str, Any] | None = None,
    knowledge_refs: list[int] | None = None,
    latency_ms: int = 0,
    token_usage: dict[str, Any] | None = None,
    error_code: str = "",
) -> AiRun | None:
    run = AiRun(
        owner_id=owner_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
        trace_id=trace_id[:64],
        operation=operation[:64],
        provider=provider[:64],
        model=model[:128],
        intent=intent[:64],
        risk=risk[:32],
        action=action[:64],
        confidence_json=confidence or {},
        knowledge_refs_json=knowledge_refs or [],
        latency_ms=max(0, latency_ms),
        token_usage_json=token_usage or {},
        status=status[:32],
        error_code=error_code[:128],
    )
    try:
        with db.begin_nested():
            db.add(run)
            db.flush()
        return run
    except Exception:
        logger.exception("Could not persist AI run telemetry")
        return None


@dataclass(frozen=True)
class MetricsSnapshot:
    window_days: int
    messages_total: int
    approvals_total: int
    approvals_pending: int
    approvals_sent: int
    approvals_rejected: int
    approvals_uncertain: int
    approvals_failed: int
    ai_runs_total: int
    ai_runs_error: int
    ai_runs_discarded: int
    ai_latency_ms_average: float
    ai_tokens_total: int
    retrieval_runs_total: int
    retrieval_hit_runs: int
    feedback_total: int
    feedback_rating_average: float


def collect_metrics(db: Session, *, window_days: int) -> MetricsSnapshot:
    window_days = max(1, min(window_days, 3650))
    since = datetime.now(UTC) - timedelta(days=window_days)
    messages_total = int(
        db.scalar(select(func.count(Message.id)).where(Message.created_at >= since)) or 0
    )
    approval_rows = db.execute(
        select(Approval.status, func.count(Approval.id))
        .where(Approval.created_at >= since)
        .group_by(Approval.status)
    ).all()
    approvals = {str(status): int(count) for status, count in approval_rows}
    runs = list(db.scalars(select(AiRun).where(AiRun.created_at >= since)))
    feedback_total, feedback_average = db.execute(
        select(func.count(Feedback.id), func.avg(Feedback.rating)).where(
            Feedback.created_at >= since
        )
    ).one()

    successful_latencies = [run.latency_ms for run in runs if run.status == "SUCCESS"]
    return MetricsSnapshot(
        window_days=window_days,
        messages_total=messages_total,
        approvals_total=sum(approvals.values()),
        approvals_pending=approvals.get("PENDING", 0),
        approvals_sent=approvals.get("SENT", 0),
        approvals_rejected=approvals.get("REJECTED", 0),
        approvals_uncertain=approvals.get("UNCERTAIN", 0),
        approvals_failed=approvals.get("FAILED", 0),
        ai_runs_total=len(runs),
        ai_runs_error=sum(run.status == "ERROR" for run in runs),
        ai_runs_discarded=sum(run.status == "DISCARDED" for run in runs),
        ai_latency_ms_average=(
            sum(successful_latencies) / len(successful_latencies) if successful_latencies else 0.0
        ),
        ai_tokens_total=sum(_numeric_usage(run.token_usage_json, "total_tokens") for run in runs),
        retrieval_runs_total=sum(run.operation == "TEXT_RESPONSE" for run in runs),
        retrieval_hit_runs=sum(
            run.operation == "TEXT_RESPONSE" and bool(run.knowledge_refs_json) for run in runs
        ),
        feedback_total=int(feedback_total or 0),
        feedback_rating_average=float(feedback_average or 0.0),
    )


def render_prometheus(snapshot: MetricsSnapshot) -> str:
    values: list[tuple[str, str, int | float]] = [
        (
            "secretary_messages_total",
            "Messages received in the metrics window",
            snapshot.messages_total,
        ),
        (
            "secretary_approvals_total",
            "Approval records in the metrics window",
            snapshot.approvals_total,
        ),
        ("secretary_approvals_pending", "Pending approvals", snapshot.approvals_pending),
        ("secretary_approvals_sent", "Responses sent after approval", snapshot.approvals_sent),
        ("secretary_approvals_rejected", "Rejected responses", snapshot.approvals_rejected),
        (
            "secretary_approvals_uncertain",
            "Approvals with uncertain delivery",
            snapshot.approvals_uncertain,
        ),
        (
            "secretary_approvals_failed",
            "Failed approval sends",
            snapshot.approvals_failed,
        ),
        ("secretary_ai_runs_total", "AI operations", snapshot.ai_runs_total),
        ("secretary_ai_runs_error", "Failed AI operations", snapshot.ai_runs_error),
        (
            "secretary_ai_runs_discarded",
            "AI results discarded after context changed",
            snapshot.ai_runs_discarded,
        ),
        (
            "secretary_ai_latency_ms_average",
            "Average successful AI latency",
            round(snapshot.ai_latency_ms_average, 3),
        ),
        ("secretary_ai_tokens_total", "Reported AI tokens", snapshot.ai_tokens_total),
        (
            "secretary_retrieval_runs_total",
            "Text retrieval operations",
            snapshot.retrieval_runs_total,
        ),
        (
            "secretary_retrieval_hit_runs",
            "Runs with knowledge references",
            snapshot.retrieval_hit_runs,
        ),
        ("secretary_feedback_total", "Feedback ratings", snapshot.feedback_total),
        (
            "secretary_feedback_rating_average",
            "Average feedback rating",
            round(snapshot.feedback_rating_average, 3),
        ),
    ]
    lines = [f"# metrics_window_days {snapshot.window_days}"]
    for name, help_text, value in values:
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge", f"{name} {value}"))
    return "\n".join(lines) + "\n"
