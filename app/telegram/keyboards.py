from __future__ import annotations

from app.interface.menus import MenuAction, MenuDefinition


def to_aiogram_inline_keyboard(menu: MenuDefinition):
    # aiogram remains isolated inside Telegram adapter code.
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard: list[list[InlineKeyboardButton]] = []
    for row in menu.visible_rows():
        rendered_row: list[InlineKeyboardButton] = []
        for button in row:
            text = f"{button.emoji + ' ' if button.emoji else ''}{button.label}"
            if button.action == MenuAction.OPEN_URL:
                url = str(button.config.get("url") or "").strip()
                if url.startswith(("https://", "http://")):
                    rendered_row.append(InlineKeyboardButton(text=text, url=url))
                continue
            rendered_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"m:{button.id}",
                )
            )
        if rendered_row:
            keyboard.append(rendered_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
