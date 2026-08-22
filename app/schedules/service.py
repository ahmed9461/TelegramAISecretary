from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Schedule


@dataclass(frozen=True, slots=True)
class ReminderClaim:
    schedule_id: int
    owner_id: int
    text: str
    run_at: datetime


def validate_timezone(value: str) -> str:
    name = value.strip()
    try:
        ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("unknown timezone") from exc
    return name


def local_time_to_utc(*, value: str, timezone: str) -> datetime:
    try:
        local = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("invalid reminder time") from exc
    aware = local.replace(tzinfo=ZoneInfo(validate_timezone(timezone)))
    return aware.astimezone(UTC)


def create_reminder(
    session: Session,
    *,
    owner_id: int,
    timezone: str,
    text: str,
    run_at: datetime,
) -> Schedule:
    body = text.strip()
    if not body:
        raise ValueError("reminder text is required")
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    now = datetime.now(UTC)
    if run_at.astimezone(UTC) <= now:
        raise ValueError("reminder time must be in the future")
    row = Schedule(
        owner_id=owner_id,
        type="REMINDER",
        timezone=validate_timezone(timezone),
        config_json={"text": body[:2000], "run_at": run_at.astimezone(UTC).isoformat()},
        enabled=True,
    )
    session.add(row)
    session.flush()
    return row


def list_reminders(
    session: Session,
    *,
    owner_id: int,
    include_delivered: bool = False,
) -> list[Schedule]:
    query = select(Schedule).where(
        Schedule.owner_id == owner_id,
        Schedule.type == "REMINDER",
    )
    if not include_delivered:
        query = query.where(Schedule.enabled.is_(True))
    return list(session.scalars(query.order_by(Schedule.created_at, Schedule.id)))


def _run_at(row: Schedule) -> datetime | None:
    raw = str((row.config_json or {}).get("run_at") or "")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def claim_due_reminders(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = 20,
    claim_timeout_seconds: int = 300,
) -> list[ReminderClaim]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    lease_expired_before = current - timedelta(seconds=max(30, claim_timeout_seconds))
    rows = list(
        session.scalars(
            select(Schedule)
            .where(
                Schedule.type == "REMINDER",
                Schedule.enabled.is_(True),
                or_(
                    Schedule.last_run_at.is_(None),
                    Schedule.last_run_at < lease_expired_before,
                ),
            )
            .order_by(Schedule.created_at, Schedule.id)
            .with_for_update(skip_locked=True)
        )
    )
    claims: list[ReminderClaim] = []
    for row in rows:
        run_at = _run_at(row)
        if run_at is None or run_at > current:
            continue
        text = str((row.config_json or {}).get("text") or "").strip()
        if not text:
            row.enabled = False
            continue
        row.last_run_at = current
        claims.append(ReminderClaim(row.id, row.owner_id, text, run_at))
        if len(claims) >= max(1, limit):
            break
    session.flush()
    return claims


def mark_reminder_delivered(session: Session, schedule_id: int) -> None:
    row = session.get(Schedule, schedule_id)
    if row is not None:
        row.enabled = False
        session.flush()


def release_reminder_claim(session: Session, schedule_id: int) -> None:
    row = session.get(Schedule, schedule_id)
    if row is not None and row.enabled:
        row.last_run_at = None
        session.flush()
