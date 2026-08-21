from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_admin_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="💬 المحادثات", callback_data="a:conversations"),
            InlineKeyboardButton(text="🔔 بانتظارك", callback_data="a:pending"),
        ],
        [
            InlineKeyboardButton(text="🧠 عقل السكرتير", callback_data="brain:home"),
            InlineKeyboardButton(text="📥 تغذية العقل", callback_data="brain:ingest"),
        ],
        [
            InlineKeyboardButton(text="👥 الأشخاص", callback_data="a:contacts"),
            InlineKeyboardButton(text="🧩 الواجهة والأزرار", callback_data="interface:home"),
        ],
        [
            InlineKeyboardButton(text="⚙️ السلوك", callback_data="behavior:home"),
            InlineKeyboardButton(text="⏰ الأوقات", callback_data="a:schedules"),
        ],
        [
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data="a:stats"),
            InlineKeyboardButton(text="🛡️ الأمان", callback_data="a:security"),
        ],
        [InlineKeyboardButton(text="⏸ إيقاف السكرتير", callback_data="a:pause")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ إرسال الرد", callback_data=f"approval:send:{approval_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ تعديل الرد", callback_data=f"approval_edit:start:{approval_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📚 المصادر", callback_data=f"approval_meta:sources:{approval_id}"
                ),
                InlineKeyboardButton(
                    text="🧠 تعلّم من تعديلي",
                    callback_data=f"approval_edit:learn:{approval_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ رفض", callback_data=f"approval:reject:{approval_id}"
                )
            ],
        ]
    )
