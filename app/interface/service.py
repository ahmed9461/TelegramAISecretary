from __future__ import annotations

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


def load_menu_definition(
    session: Session,
    *,
    owner_id: int,
    parent_item_id: int | None = None,
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
    rows = list(session.scalars(query.order_by(MenuItem.row_index, MenuItem.sort_order, MenuItem.id)))

    buttons: list[MenuButton] = []
    for row in rows:
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
) -> tuple[MenuProfile, MenuItem] | None:
    row = session.get(MenuItem, item_id)
    if row is None:
        return None
    profile = session.get(MenuProfile, row.menu_profile_id)
    if profile is None or profile.owner_id != owner_id or not profile.enabled:
        return None
    return profile, row


def list_menu_items(session: Session, *, owner_id: int) -> tuple[MenuProfile, list[MenuItem]]:
    profile = get_or_create_default_menu_profile(session, owner_id=owner_id)
    rows = list(
        session.scalars(
            select(MenuItem)
            .where(MenuItem.menu_profile_id == profile.id, MenuItem.parent_item_id.is_(None))
            .order_by(MenuItem.row_index, MenuItem.sort_order, MenuItem.id)
        )
    )
    return profile, rows
