from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.config import get_settings
from app.db.models import Owner
from app.db.session import SessionLocal
from app.schedules.service import (
    claim_due_reminders,
    mark_reminder_delivered,
    release_reminder_claim,
)

logger = logging.getLogger(__name__)


async def deliver_due_reminders(bot: Bot) -> int:
    settings = get_settings()
    with SessionLocal() as session:
        claims = claim_due_reminders(
            session,
            limit=settings.schedule_batch_size,
            claim_timeout_seconds=settings.schedule_claim_timeout_seconds,
        )
        session.commit()

    delivered = 0
    for claim in claims:
        with SessionLocal() as session:
            owner = session.get(Owner, claim.owner_id)
            owner_chat_id = owner.telegram_user_id if owner is not None else None
        if owner_chat_id is None:
            with SessionLocal() as session:
                release_reminder_claim(session, claim.schedule_id)
                session.commit()
            continue
        try:
            await bot.send_message(
                chat_id=owner_chat_id,
                text=f"⏰ تذكيرك\n\n{claim.text}",
            )
        except Exception:
            logger.exception("reminder_delivery_failed schedule=%s", claim.schedule_id)
            with SessionLocal() as session:
                release_reminder_claim(session, claim.schedule_id)
                session.commit()
            continue
        with SessionLocal() as session:
            mark_reminder_delivered(session, claim.schedule_id)
            session.commit()
        delivered += 1
    return delivered


async def run_reminder_loop(bot: Bot, stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(5.0, settings.schedule_poll_seconds)
    while not stop_event.is_set():
        try:
            await deliver_due_reminders(bot)
        except Exception:
            logger.exception("reminder_loop_failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            pass
