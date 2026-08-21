from __future__ import annotations

from app.interface.menus import MenuDefinition


def to_aiogram_inline_keyboard(menu: MenuDefinition):
    # aiogram remains isolated inside Telegram adapter code.
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard: list[list[InlineKeyboardButton]] = []
    for row in menu.visible_rows():
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{button.emoji + ' ' if getattr(button, 'emoji', None) else ''}{button.label}",
                    callback_data=f"m:{button.id}",
                )
                for button in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
