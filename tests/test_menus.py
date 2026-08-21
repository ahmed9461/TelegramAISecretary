from app.db.enums import InterfaceMode
from app.interface.menus import MenuAction, MenuButton, MenuDefinition


def test_ai_only_has_no_buttons() -> None:
    menu = MenuDefinition(
        mode=InterfaceMode.AI_ONLY,
        buttons=(MenuButton("x", "شراء", MenuAction.START_FLOW),),
    )
    assert menu.visible_rows() == []


def test_custom_menu_is_data_driven() -> None:
    menu = MenuDefinition(
        mode=InterfaceMode.HYBRID,
        buttons=(
            MenuButton("support", "الدعم", MenuAction.START_FLOW, row=0, order=1),
            MenuButton("renew", "تجديد", MenuAction.START_FLOW, row=0, order=0),
            MenuButton("hidden", "مخفي", MenuAction.SEND_MESSAGE, enabled=False, row=1),
        ),
    )
    rows = menu.visible_rows()
    assert [b.id for b in rows[0]] == ["renew", "support"]
    assert len(rows) == 1
