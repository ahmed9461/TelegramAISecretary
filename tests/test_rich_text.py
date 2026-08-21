from aiogram.enums import MessageEntityType

from app.telegram.rich_text import render_native_rich


def test_native_rich_uses_utf16_offsets_for_arabic_and_emoji() -> None:
    rendered = render_native_rich("✨ تفاصيل الباقة\n\nالسعر: 10 دولار\n• المدة 30 يومًا")

    assert rendered.text.startswith("✨ تفاصيل الباقة")
    assert rendered.entities[0].type == MessageEntityType.BOLD
    assert rendered.entities[0].offset == 0
    assert rendered.entities[0].length == len("✨ تفاصيل الباقة".encode("utf-16-le")) // 2
    assert any(entity.type == MessageEntityType.BOLD for entity in rendered.entities[1:])


def test_plain_short_reply_does_not_force_formatting() -> None:
    rendered = render_native_rich("تمام، متاح.")
    assert rendered.entities == ()
