# M6 — Secretary Learning, Bulk Knowledge & Contextual UI

## الهدف

نقل M5 من عقل يمكن تعبئته يدويًا إلى سكرتير عملي للاستخدام اليومي: إدارة الذاكرة والمعرفة والقواعد، تعديل الرد والتعلم الصريح، تغذية جماعية للمعلومات، Rich Telegram responses، وأزرار تظهر حسب السياق بدل الظهور العشوائي.

## 1. Approval Editing & Explicit Learning

بطاقة الرد المقترح أصبحت تدعم تعديل candidate قبل الإرسال. إذا عدل المالك الرد، يرسل النص الجديد نفسه عند الاعتماد.

زر `🧠 تعلّم من تعديلي` لا يعمل بصمت. بعد confirmation فقط يحفظ التعديل كتوجيه `INTERNAL`. لا يحوله تلقائيًا إلى PRICE/PUBLIC fact.

## 2. Source Provenance

زر `📚 المصادر` يعيد عرض KnowledgeItems المسترجعة التي ساعدت في بناء السياق، مع استبعاد PRIVATE. هذا يسمح للمالك بفحص grounding بدل الاعتماد على صياغة النموذج وحدها.

## 3. Contact Memory Management

واجهة `👥 ذاكرة الأشخاص` أصبحت فعلية:

- اختيار Contact.
- مراجعة/تعديل summary.
- private owner notes.
- تشغيل/إيقاف share_with_ai.
- مسح الذاكرة.

private notes تبقى خارج LLM.

## 4. Knowledge Management

يمكن من Telegram مراجعة KnowledgeItem ثم:

- تعديل العنوان.
- تعديل المحتوى.
- تغيير PUBLIC/INTERNAL/PRIVATE.
- حذف العنصر.

الإدخال الفردي ما زال موجودًا للصيانة السريعة، لكنه لم يعد الطريقة الأساسية لإدخال كمية كبيرة من المعلومات.

## 5. Response Policies

واجهة قواعد الرد تدعم المراجعة والتعديل والتفعيل/التعطيل والحذف، مع actions مثل REQUIRE_APPROVAL / ESCALATE / GUIDE_ONLY حسب ما تدعمه الطبقة الحالية.

## 6. Global Behavior

واجهة `⚙️ السلوك` تدير:

- AUTO
- APPROVAL
- OBSERVE
- OFF

الوضع العام سقف أمان. AUTO لا يغير HUMAN_TAKEOVER/EXCLUDED/PAUSED إلى حالة أخف تلقائيًا.

## 7. Bulk Knowledge Ingestion

القسم الجديد `📥 تغذية العقل` يسمح باختيار visibility ثم إرسال نص طويل أو ملف.

الامتدادات الحالية:

```text
.txt .md .csv .json .yaml .yml
```

الحدود الحالية في Telegram UI:

```text
MAX_FILE_BYTES = 4 MiB
MAX_SOURCE_CHARS = 160,000
```

المسار:

```text
source
  ↓
chunking
  ↓
DeepSeek knowledge extractor
  ↓
normalize + deduplicate
  ↓
preview
  ↓
owner: ✅ اعتماد الكل / ❌ إلغاء
  ↓
KnowledgeItem rows
```

Extractor ممنوع من اختراع/تصحيح/إكمال معلومات غائبة.

## 8. Native Rich Telegram Messages

أضيف renderer يحول النص المنظم إلى Telegram native MessageEntity. لا نمرر HTML أو Markdown خام من DeepSeek. Adapter يرسل `text + entities` عبر Business Connection.

## 9. Dynamic Customer Buttons

`🧩 الواجهة والأزرار` أصبحت واجهة فعلية لإنشاء:

- رد ثابت.
- رابط.
- تحويل للمتابعة البشرية.

الأزرار تخزن كـMenuItem في DB وتتحول إلى aiogram keyboard داخل Telegram adapter فقط.

## 10. Contextual Buttons

الأزرار نوعان من حيث visibility:

### 🌐 ALWAYS
يظهر مع كل رد عندما يسمح mode.

### 🎯 CONTEXTUAL
يحمل keywords و/أو intents في `visibility_rules_json`. قبل الإرسال يفحص النظام أحدث رسالة واردة ونص الرد، ويعرض الزر فقط إذا طابق السياق.

مثال:

```text
زر: طرق الدفع
keywords: دفع، سداد، تحويل، كريبتو، نجوم
```

سؤال عن الدفع → يظهر. سؤال عن ساعات العمل → لا يظهر.

هذا matching deterministic وليس LLM button selection.

## 11. Telegram Callback Safety

`safe_callback_answer` يتعامل مع callback المنتهي مثل `query is too old` دون إسقاط handler أو طباعة crash غير ضروري.

## 12. Telegram Network Resilience

ظهر في الاختبار الحي خطأ Windows/Telegram network مؤقت أثناء إرسال بطاقة approval بعد نجاح DeepSeek. لذلك أضيف `ResilientOwnerBot`:

- يعيد محاولات محدودة فقط للطلبات الموجهة إلى owner chat.
- يستخدم backoff قصير.
- لا يطبق retry العام على customer business sends لأن قبول Telegram للطلب ثم فقد الرد قد يؤدي إلى duplicate message.

## 13. Verification

آخر CI موثق للفرع بعد contextual buttons/network retry:

```text
Python 3.12: success
Python 3.13: success
Ruff correctness gate: success
compileall: success
pytest: 56 passed, 1 warning
```

الـRuff full report ما زال يعرض style debt قديمًا لأنه يعمل `--exit-zero`; correctness gate فقط هو blocking حاليًا.

## 14. حالة M6

M6 ما زالت على `m6-secretary-learning` وPR #2 Draft حتى يكتمل الاختبار الحي النهائي. لا تعتبر merged أو production-stable قبل الدمج الفعلي إلى `main`.
