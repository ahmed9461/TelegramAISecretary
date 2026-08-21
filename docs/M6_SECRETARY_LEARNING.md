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

في مسار الموافقة يحفظ النظام intent المصنف داخل metadata محدودة في حقل سبب approval الحالي، ثم يعيده إلى سياق القائمة عند الإرسال. approvals القديمة التي لا تحمل intent تستمر بالعمل عبر الكلمات دون migration جديد.

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

آخر CI بعيد موثق للفرع بعد contextual buttons/network retry:

```text
Python 3.12: success
Python 3.13: success
Ruff correctness gate: success
compileall: success
pytest: 56 passed, 1 warning
```

الـRuff full report ما زال يعرض style debt قديمًا لأنه يعمل `--exit-zero`; correctness gate فقط هو blocking حاليًا.

التحقق المحلي النهائي في 2026-08-22 بعد إضافة اختباري fault injection:

```text
pytest: 60 passed, 1 warning
python -m compileall -q app tests: success
Ruff E9/F63/F7/F82: success
```

الاختبار الحي عبر حسابين Telegram أثبت:

- cancel للتغذية الجماعية لا يحفظ عناصر.
- الاعتماد الصريح حفظ ثلاث معلومات PUBLIC واسترجعها الرد مع عرض المصادر.
- الرد وصل مرة واحدة بكيانات rich أصلية دون raw Markdown/HTML.
- الزر السياقي ظهر ونفذ الإجراء عند التطابق، ولم يظهر في السؤال غير المطابق.
- زر ثانٍ يعتمد على `GREETING` intent فقط ظهر بعد approval ونفذ الإجراء، ما يثبت استمرار intent في المسار الحقيقي.
- fault injection أعاد طلب المالك مرتين بحد أقصى وترك إرسال العميل غير المؤكد دون retry.
- أزيلت بيانات الاختبار الاصطناعية المحددة بعد التحقق، بما فيها الزران المؤقتان، مع الحفاظ على البيانات السابقة.

## 14. حالة M6

اكتمل gate التنفيذ والاختبار الحي محليًا على `m6-secretary-learning`. ما زال PR #2 Draft لأن آخر diff لم ينشر ولم يمر بعد على CI بعيد جديد ومراجعة. لا تعتبر M6 merged أو production-stable قبل الدمج الفعلي إلى `main`، ولا يبدأ M7 على هذا الفرع.
