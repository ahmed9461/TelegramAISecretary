from __future__ import annotations

import re

from aiogram.types import (
    InputRichBlockList,
    InputRichBlockListItem,
    InputRichBlockParagraph,
    InputRichBlockSectionHeading,
    InputRichMessage,
)

_BULLET = re.compile(r"^\s*[•\-*]\s+(.+?)\s*$")
_ARABIC = re.compile(r"[\u0600-\u06ff]")


def render_input_rich_message(text: str) -> InputRichMessage | None:
    """Build Telegram Rich Message blocks only when the reply is genuinely structured."""

    clean = (text or "").strip()
    if not clean or len(clean) > 4000:
        return None
    lines = clean.splitlines()
    has_heading = len(lines) > 2 and bool(lines[0].strip()) and not lines[1].strip()
    bullet_count = sum(1 for line in lines if _BULLET.match(line))
    if not has_heading and bullet_count < 2:
        return None

    blocks: list = []
    index = 0
    if has_heading:
        blocks.append(InputRichBlockSectionHeading(text=lines[0].strip(), size=2))
        index = 2

    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(InputRichBlockParagraph(text="\n".join(paragraph).strip()))
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            blocks.append(
                InputRichBlockList(
                    items=[
                        InputRichBlockListItem(
                            blocks=[InputRichBlockParagraph(text=item)],
                        )
                        for item in bullets
                    ]
                )
            )
            bullets.clear()

    for line in lines[index:]:
        match = _BULLET.match(line)
        if match:
            flush_paragraph()
            bullets.append(match.group(1))
        elif not line.strip():
            flush_paragraph()
            flush_bullets()
        else:
            flush_bullets()
            paragraph.append(line.strip())
    flush_paragraph()
    flush_bullets()
    if not blocks:
        return None
    return InputRichMessage(
        blocks=blocks,
        is_rtl=len(_ARABIC.findall(clean)) >= max(1, len(clean) // 12),
        skip_entity_detection=False,
    )
