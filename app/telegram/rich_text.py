from __future__ import annotations

from dataclasses import dataclass

from aiogram.enums import MessageEntityType
from aiogram.types import MessageEntity


@dataclass(frozen=True, slots=True)
class NativeRichText:
    text: str
    entities: tuple[MessageEntity, ...] = ()


def _utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def render_native_rich(text: str) -> NativeRichText:
    """Apply lightweight native Telegram entities without HTML/Markdown parse modes.

    AI replies remain normal readable text. If the reply is structured, the first line is
    treated as a heading when followed by a blank line, and short ``label:`` prefixes are
    bolded. Telegram entities use UTF-16 offsets, so Arabic and emoji stay correctly aligned.
    """

    clean = (text or "").strip()
    if not clean:
        return NativeRichText(text="")

    entities: list[MessageEntity] = []
    lines = clean.splitlines(keepends=True)

    first_line = lines[0].rstrip("\r\n") if lines else ""
    if first_line and len(first_line) <= 100 and len(lines) > 1 and lines[1].strip() == "":
        entities.append(
            MessageEntity(
                type=MessageEntityType.BOLD,
                offset=0,
                length=_utf16_len(first_line),
            )
        )

    char_offset = 0
    for line in lines:
        visible = line.rstrip("\r\n")
        colon_index = visible.find(":")
        if 0 < colon_index <= 36:
            prefix = visible[: colon_index + 1]
            # Do not duplicate the heading entity when the whole first line is already bold.
            if not (char_offset == 0 and prefix == first_line):
                entities.append(
                    MessageEntity(
                        type=MessageEntityType.BOLD,
                        offset=_utf16_len(clean[:char_offset]),
                        length=_utf16_len(prefix),
                    )
                )
        char_offset += len(line)

    return NativeRichText(text=clean, entities=tuple(entities))
