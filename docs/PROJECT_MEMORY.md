# Project Memory — Telegram AI Secretary

> هذا الملف هو ذاكرة المشروع التشغيلية طويلة المدى. يقرأه أي مبرمج أو AI قبل تنفيذ تعديل كبير، ثم يراجع `MASTER_SPEC.md` والملفات المتخصصة ذات الصلة.

## الحالة الحالية

- المرحلة الحالية: **M6 — Secretary Learning, Bulk Knowledge, Rich UI & Contextual Buttons**.
- فرع التطوير الحالي: `m6-secretary-learning`.
- الدمج إلى `main`: لم يتم بعد؛ اختبار Telegram الحي النهائي نجح محليًا في 2026-08-22، وPR #2 ما زال Draft حتى نشر التغييرات وإعادة CI والمراجعة.
- آخر CI موثق على الفرع: Python 3.12 و3.13 نجحا، مع `compileall` وRuff correctness gate و`pytest`.
- آخر عدد اختبارات موثق في CI: **56 passed, 1 warning**.
- آخر تحقق محلي بعد fault injection وربط intent عبر approval: **60 passed, 1 warning** مع نجاح `compileall` وRuff correctness gate.
- التحذير المعروف: Starlette/FastAPI TestClient deprecation بخصوص `httpx`; لا يمنع التشغيل.

## ما هو المنتج

سكرتير ذكاء اصطناعي عام وقابل للتخصيص لحساب Telegram الشخصي عبر **Telegram Business / Connected Business Bot الرسمي**. يستقبل رسائل العملاء، يبني سياقًا من المحادثة + معرفة المالك + ذاكرة الشخص + قواعد الرد، ثم يستخدم مزود الذكاء لصياغة الرد ويطبق سياسة أمان محلية قبل الإرسال أو طلب الموافقة.

المشروع ليس بوت متجر ثابتًا. النشاط والخدمات والأسعار والقوائم والقواعد كلها بيانات قابلة للتعديل بدون إعادة كتابة Core.

## المعمارية المعتمدة

```text
Telegram Business
      ↓
Telegram adapter / ingestion
      ↓
Conversation + contact state
      ↓
Business profile
+ relevant knowledge
+ safe contact memory
+ response policies
+ recent history
      ↓
DeepSeek classification/reply
      ↓
Local deterministic safety policy
      ↓
AUTO / APPROVAL / ESCALATE / SILENT
      ↓
Telegram Business reply
```

مسار الصور:

```text
Telegram image → Gemini Vision → structured evidence → DeepSeek → local safety → approval/reply
```

## ما تم إنجازه حتى M6

- اتصال Telegram Business الرسمي وتخزين Business Connections.
- ingest للرسائل مع idempotency وconversation revision.
- debounce لكل محادثة وإبطال النتائج القديمة.
- approvals بمدة صلاحية وحالات stale/superseded/uncertain.
- فحص `can_reply` قبل الإرسال المعتمد.
- تسجيل الردود المعتمدة واليدوية في history.
- معالجة edit/delete للرسائل.
- DeepSeek للنصوص والرد النهائي، Gemini للرؤية.
- retries للأخطاء المؤقتة لدى DeepSeek/Gemini.
- Owner-only admin UI.
- BusinessProfile قابل للتغيير.
- KnowledgeItem بمستويات PUBLIC / INTERNAL / PRIVATE.
- ContactMemory منفصلة لكل شخص.
- ResponsePolicy قابلة للإدارة.
- تعديل الرد المقترح قبل الإرسال.
- تعلم اختياري من تعديل المالك بعد تأكيد صريح فقط، ويحفظ INTERNAL.
- إدارة المعرفة والذاكرة والقواعد من الأزرار.
- أوضاع AUTO / APPROVAL / OBSERVE / OFF كسقف أمان عالمي.
- Bulk Knowledge: لصق نص كبير أو ملفات TXT/MD/CSV/JSON/YAML، استخراج منظم، معاينة، واعتماد جماعي.
- Telegram native rich text عبر MessageEntity بدون HTML/Markdown خام.
- Dynamic Menu/Button Engine.
- أزرار دائمة 🌐 وأزرار سياقية 🎯 تظهر عند مطابقة الكلمات/السياق، بدل الظهور العشوائي.
- زر رد ثابت، رابط، وتحويل للمتابعة البشرية.
- retry محدود لرسائل المالك/بطاقات الموافقة عند أخطاء Telegram الشبكية المؤقتة؛ ردود العملاء تبقى fail-closed لمنع التكرار.

## دليل إغلاق M6 المحلي — 2026-08-22

- Bulk Knowledge: ثبت أن الإلغاء لا يحفظ شيئًا، ثم حفظ الاعتماد الصريح ثلاث معلومات PUBLIC فقط.
- Source provenance: عرضت بطاقة الموافقة عناصر المعرفة الثلاثة المسترجعة، وكلها PUBLIC كما اختار المالك.
- Native rich: وصل الرد إلى Telegram Business بكيانات تنسيق أصلية، دون raw Markdown/HTML.
- Contextual UI: ظهر الزر السياقي للسؤال المطابق ونفذ الرد الثابت، واختفى من سؤال مستقل غير مطابق بينما بقي الزر الدائم.
- Intent continuity: حفظ approval intent المصنف حتى الإرسال، وظهر زر تجريبي يعتمد على `GREETING` وحده في Telegram ونفذ إجراءه.
- منع التكرار: سجلت الموافقة المطابقة حالة `SENT` ومعرف رسالة Telegram واحدًا فقط، وظهر الرد مرة واحدة في المحادثة.
- Network resilience: اختبار fault injection يثبت محاولتين محدودتين لطلب المالك مع backoff، وعدم إعادة إرسال طلب العميل غير المؤكد.
- حذفت بعد الاختبارات فقط عناصر المعرفة الثلاثة والزرين السياقيين الاصطناعيين، وتأكد بقاء الزر السابق الحقيقي.

## قواعد الاستمرارية

1. لا تعيد بناء المشروع من الصفر ما دام التعديل يمكن دمجه في المعمارية الحالية.
2. لا تربط Core بنشاط تجاري معين.
3. افحص models + migrations الحالية قبل إضافة جدول أو migration جديد.
4. أي قرار معماري جديد يسجل في `DECISIONS.md`.
5. أي مرحلة أو إنجاز مهم يحدث `PROGRESS.md` وملف milestone المناسب.
6. أي تغيير في تشغيل المشروع يحدث `RUNBOOK.md`.
7. لا تكتب عدد اختبارات إلا بعد تشغيل فعلي محلي أو CI.
8. لا تضع Tokens/Keys/Passwords أو بيانات حقيقية حساسة داخل Git.
9. لا يوجد تعلم صامت من ردود المالك.
10. لا تُعامل ذاكرة العميل كمصدر حقيقة للأسعار أو الالتزامات الحالية.

## الخطوة القادمة بعد تثبيت M6

انتهى gate المحلي لـM6. الخطوة المباشرة هي مراجعة diff الحالي، نشره على PR #2، إعادة CI على Python 3.12/3.13، ثم إخراج PR من Draft ودمجه فقط بعد المراجعة. بعد الدمج يبدأ M7 على فرع مستقل لتحسين جودة retrieval وعمليات المعرفة؛ لا يبدأ M7 داخل فرع M6.

## ترتيب المراجع عند التعارض

1. `MASTER_SPEC.md` للمبادئ الأساسية غير القابلة للتفاوض.
2. `CONSTANTS.md` للثوابت الحالية.
3. `DECISIONS.md` للقرارات المعمارية المعتمدة بعد الـbaseline.
4. ملف milestone الأحدث مثل `M6_SECRETARY_LEARNING.md`.
5. `PROJECT_MEMORY.md` للحالة التشغيلية الحالية.
6. الكود والاختبارات هما المرجع النهائي لما هو منفذ فعليًا.
