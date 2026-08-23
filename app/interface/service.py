from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import InterfaceMode
from app.db.models import MenuItem, MenuProfile
from app.interface.menus import MenuAction, MenuButton, MenuDefinition


def get_or_create_default_menu_profile(session: Session, *, owner_id: int) -> MenuProfile:
    profile = session.scalar(
        select(MenuProfile)
        .where(
            MenuProfile.owner_id == owner_id,
            MenuProfile.scope == "DEFAULT",
        )
        .order_by(MenuProfile.id.asc())
    )
    if profile is not None:
        return profile
    profile = MenuProfile(
        owner_id=owner_id,
        name="القائمة الافتراضية",
        mode=InterfaceMode.HYBRID.value,
        scope="DEFAULT",
        enabled=True,
        welcome_message="",
    )
    session.add(profile)
    session.flush()
    return profile


def _profile_items(session: Session, profile_id: int) -> list[MenuItem]:
    return list(
        session.scalars(
            select(MenuItem)
            .where(MenuItem.menu_profile_id == profile_id, MenuItem.parent_item_id.is_(None))
            .order_by(MenuItem.row_index, MenuItem.sort_order, MenuItem.id)
        )
    )


def get_or_create_draft_menu_profile(session: Session, *, owner_id: int) -> MenuProfile:
    draft = session.scalar(
        select(MenuProfile)
        .where(MenuProfile.owner_id == owner_id, MenuProfile.scope == "DRAFT")
        .order_by(MenuProfile.id.desc())
    )
    if draft is not None:
        return draft

    published = get_or_create_default_menu_profile(session, owner_id=owner_id)
    draft = MenuProfile(
        owner_id=owner_id,
        name=f"{published.name} — مسودة",
        mode=published.mode,
        scope="DRAFT",
        enabled=True,
        welcome_message=published.welcome_message,
    )
    session.add(draft)
    session.flush()
    for row in _profile_items(session, published.id):
        session.add(
            MenuItem(
                menu_profile_id=draft.id,
                parent_item_id=None,
                label=row.label,
                emoji=row.emoji,
                action_type=row.action_type,
                action_config_json=dict(row.action_config_json or {}),
                row_index=row.row_index,
                sort_order=row.sort_order,
                visibility_rules_json=dict(row.visibility_rules_json or {}),
                enabled=row.enabled,
            )
        )
    session.flush()
    return draft


def publish_menu_draft(session: Session, *, owner_id: int) -> MenuProfile:
    """Atomically promote the reviewed draft and immediately create a fresh editable copy."""

    draft = session.scalar(
        select(MenuProfile)
        .where(MenuProfile.owner_id == owner_id, MenuProfile.scope == "DRAFT")
        .order_by(MenuProfile.id.desc())
    )
    if draft is None:
        raise ValueError("menu_draft_not_found")
    published = session.scalar(
        select(MenuProfile)
        .where(MenuProfile.owner_id == owner_id, MenuProfile.scope == "DEFAULT")
        .order_by(MenuProfile.id.asc())
    )
    if published is not None:
        published.scope = f"ARCHIVED_{published.id}"
        published.enabled = False
    draft.scope = "DEFAULT"
    draft.enabled = True
    draft.name = draft.name.removesuffix(" — مسودة")
    session.flush()
    return draft


def menu_item_matches_context(
    visibility_rules: Mapping | None,
    context: Mapping | None,
) -> bool:
    """Return whether a menu item should be visible for this reply.

    Empty rules are intentionally ALWAYS-visible for backward compatibility. Contextual
    rules are deterministic: they may match configured keywords and/or an explicit intent.
    We do not ask the LLM to randomly choose buttons at render time.
    """
    rules = dict(visibility_rules or {})
    mode = str(rules.get("mode") or "ALWAYS").upper()
    if mode != "CONTEXTUAL":
        return True

    ctx = dict(context or {})
    text_parts = [
        str(ctx.get("text") or ""),
        str(ctx.get("user_text") or ""),
        str(ctx.get("reply_text") or ""),
    ]
    haystack = "\n".join(part for part in text_parts if part).casefold()

    keywords = [
        str(value).strip().casefold()
        for value in (rules.get("keywords") or [])
        if str(value).strip()
    ]
    if keywords and any(keyword in haystack for keyword in keywords):
        return True

    intents = {
        str(value).strip().upper() for value in (rules.get("intents") or []) if str(value).strip()
    }
    current_intent = str(ctx.get("intent") or "").strip().upper()
    if intents and current_intent and current_intent in intents:
        return True

    return False


def load_menu_definition(
    session: Session,
    *,
    owner_id: int,
    parent_item_id: int | None = None,
    context: Mapping | None = None,
) -> MenuDefinition | None:
    profile = session.scalar(
        select(MenuProfile)
        .where(
            MenuProfile.owner_id == owner_id,
            MenuProfile.scope == "DEFAULT",
            MenuProfile.enabled.is_(True),
        )
        .order_by(MenuProfile.id.asc())
    )
    if profile is None:
        return None

    try:
        mode = InterfaceMode(profile.mode)
    except ValueError:
        mode = InterfaceMode.HYBRID

    query = select(MenuItem).where(
        MenuItem.menu_profile_id == profile.id,
        MenuItem.enabled.is_(True),
    )
    if parent_item_id is None:
        query = query.where(MenuItem.parent_item_id.is_(None))
    else:
        query = query.where(MenuItem.parent_item_id == parent_item_id)
    rows = list(
        session.scalars(query.order_by(MenuItem.row_index, MenuItem.sort_order, MenuItem.id))
    )

    buttons: list[MenuButton] = []
    for row in rows:
        if not menu_item_matches_context(row.visibility_rules_json, context):
            continue
        try:
            action = MenuAction(row.action_type)
        except ValueError:
            continue
        buttons.append(
            MenuButton(
                id=str(row.id),
                label=row.label,
                action=action,
                emoji=row.emoji,
                config=dict(row.action_config_json or {}),
                enabled=row.enabled,
                row=row.row_index,
                order=row.sort_order,
            )
        )
    return MenuDefinition(mode=mode, buttons=tuple(buttons))


def get_owned_menu_item(
    session: Session,
    *,
    owner_id: int,
    item_id: int,
    required_scope: str | None = None,
) -> tuple[MenuProfile, MenuItem] | None:
    row = session.get(MenuItem, item_id)
    if row is None:
        return None
    profile = session.get(MenuProfile, row.menu_profile_id)
    if profile is None or profile.owner_id != owner_id or not profile.enabled:
        return None
    if required_scope is not None and profile.scope != required_scope:
        return None
    return profile, row


def list_menu_items(session: Session, *, owner_id: int) -> tuple[MenuProfile, list[MenuItem]]:
    profile = get_or_create_draft_menu_profile(session, owner_id=owner_id)
    return profile, _profile_items(session, profile.id)
