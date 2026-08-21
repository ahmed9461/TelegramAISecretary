# Acceptance Criteria

هذه المعايير تمنع إعلان ميزة "مكتملة" لأنها موجودة شكليًا فقط.

## معيار عام لأي ميزة

الميزة تعتبر جاهزة فقط عندما يكون لها مسار فعلي في الكود، ownership/safety checks المناسبة، اختبار آلي للحالة الأساسية والحالات الخطرة المعقولة، وتوثيق محدث إذا غيرت سلوك التشغيل أو المعمارية.

## Telegram Business

- استقبال `business_message` الفعلي.
- persistence بدون تكرار.
- استعادة connection عند فقد update إن أمكن.
- عدم معالجة connection لمالك غير configured owner.
- approved send يعيد فحص `can_reply`.
- أي إرسال غير مؤكد للعميل لا يعاد تلقائيًا عميانيًا.

## Approval

- candidate مربوط بـconversation revision.
- TTL مطبق.
- رسالة/تعديل/حذف أحدث يبطل candidate القديم.
- رد يدوي من المالك يبطل draft القديم.
- الضغط المكرر لا يرسل مرتين.
- Send/Reject/Edit تعمل من Telegram owner UI.

## Brain / Knowledge

- BusinessProfile يدخل AI context.
- relevant knowledge يدخل context.
- PRIVATE لا يدخل LLM.
- INTERNAL لا يكشف كسياسة داخلية.
- unknown business-specific fact لا يخترع.
- source provenance قابل للمراجعة من approval UI.

## Contact Memory

- ذاكرة كل شخص منفصلة.
- `private_notes` لا تدخل AI.
- `share_with_ai` يوقف مشاركة الذاكرة.
- يمكن للمالك مراجعة/تعديل/مسح الذاكرة.
- memory لا تعتبر grounding كافيًا لسعر أو توفر حالي.

## Bulk Knowledge

- يقبل النص الطويل والامتدادات المعلنة فقط.
- يحترم حد الحجم/الأحرف.
- source content لا ينفذ كتعليمات.
- extractor لا يكمل معلومات ناقصة من معرفته.
- preview قبل commit.
- cancel لا يحفظ العناصر.
- duplicate normalization مطبق.
- visibility المختارة تطبق على جميع العناصر المعتمدة.

## Rich Messages

- لا يعتمد على raw HTML/Markdown من LLM.
- Telegram entities offsets صحيحة مع Unicode/emoji.
- عدم وجود rich pattern لا يفسد النص.
- إرسال Business message يتم بالنص + entities عبر Adapter.

## Dynamic Buttons

- تعريف الأزرار في DB وليس hardcoded لخدمة محددة.
- `AI_ONLY` لا يرفق قائمة العميل.
- `HYBRID` يسمح بالأزرار مع رد AI.
- URL action ينتج URL button فعليًا.
- contextual button لا يظهر في سياق غير مطابق.
- contextual matching deterministic وقابل للاختبار.
- زر HANDOFF ينقل الحالة إلى HUMAN_TAKEOVER ويبلغ المالك.

## Network Resilience

- Telegram network error في بطاقة المالك يمكن أن يعاد بمحاولات محدودة.
- retry العام لا يشمل customer send غير المؤكد.
- فشل retry النهائي يظهر في log ولا يؤدي إلى loop لا نهائي.

## Security

- owner-only لكل admin actions.
- secrets خارج Git.
- prompt injection boundaries موجودة للنص والصورة والملف.
- PRIVATE وowner-only notes لا تسرب.
- AUTO لا يتجاوز حالة محادثة أكثر تشددًا.

## Verification Gate قبل الدمج

الحد الأدنى قبل دمج milestone إلى `main`:

```text
ruff correctness gate: PASS
python -m compileall -q app tests: PASS
pytest: PASS
CI Python 3.12: PASS
CI Python 3.13: PASS
live test للميزات التي تعتمد على Telegram الحقيقي: PASS
```

لا يسجل عدد الاختبارات في docs إلا من output فعلي.

## نتيجة gate المحلي لـM6 — 2026-08-22

- `pytest`: 60 passed, 1 warning.
- Ruff correctness gate و`compileall`: PASS.
- Telegram Business live: Bulk cancel/commit، Sources، Native Rich، contextual keyword match/non-match، وintent-only match بعد approval، وتنفيذ الأزرار: PASS.
- الرد المطابق ظهر مرة واحدة وسجلت الموافقة معرف إرسال واحدًا.
- Network fault injection: owner retry محدود وcustomer uncertain send دون retry: PASS.
- CI البعيد الجديد والمراجعة والدمج ليست ضمن هذه النتيجة بعد؛ PR #2 بقي Draft و`main` لم يتغير.
