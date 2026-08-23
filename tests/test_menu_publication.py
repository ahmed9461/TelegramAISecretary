from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import InterfaceMode
from app.db.models import MenuItem, Owner
from app.interface.menus import MenuAction
from app.interface.service import (
    get_or_create_default_menu_profile,
    get_owned_menu_item,
    list_menu_items,
    load_menu_definition,
    publish_menu_draft,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_draft_changes_are_invisible_until_explicit_publication() -> None:
    with _session() as session:
        owner = Owner(telegram_user_id=77, display_name="مالك")
        session.add(owner)
        session.flush()
        published = get_or_create_default_menu_profile(session, owner_id=owner.id)
        published.mode = InterfaceMode.HYBRID.value
        old = MenuItem(
            menu_profile_id=published.id,
            label="السابق",
            action_type=MenuAction.SEND_MESSAGE.value,
            action_config_json={"text": "قديم"},
            visibility_rules_json={"mode": "ALWAYS"},
            enabled=True,
        )
        session.add(old)
        session.commit()

        draft, draft_rows = list_menu_items(session, owner_id=owner.id)
        assert draft.scope == "DRAFT"
        assert draft_rows[0].label == "السابق"
        draft_rows[0].label = "الجديد"
        session.commit()

        before = load_menu_definition(session, owner_id=owner.id)
        assert before is not None and before.buttons[0].label == "السابق"

        promoted = publish_menu_draft(session, owner_id=owner.id)
        session.commit()
        assert promoted.scope == "DEFAULT"
        after = load_menu_definition(session, owner_id=owner.id)
        assert after is not None and after.buttons[0].label == "الجديد"
        assert (
            get_owned_menu_item(
                session,
                owner_id=owner.id,
                item_id=old.id,
                required_scope="DEFAULT",
            )
            is None
        )

        fresh_draft, fresh_rows = list_menu_items(session, owner_id=owner.id)
        assert fresh_draft.scope == "DRAFT"
        assert fresh_rows[0].label == "الجديد"
