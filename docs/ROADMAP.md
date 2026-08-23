# Roadmap

هذا الملف يوضح الاتجاه بعد الحالة الحالية ولا يحول الأفكار المستقبلية إلى التزامات منفذة.

## M0–M4 — Foundation & Stability

الحالة: **مكتمل**.

يشمل الأساس، قاعدة البيانات، Telegram Business ingestion، approvals، Gemini/DeepSeek، debounce، revision locking، edit/delete handling، retrieval الأساسي، وإدارة معرفة أولية.

## M5 — Secretary Brain Foundation

الحالة: **مكتمل ومندمج في main**.

يشمل BusinessProfile وContactMemory وResponsePolicy وواجهة `🧠 عقل السكرتير` وربط الهوية/المعرفة/الذاكرة/القواعد بسياق AI.

## M6 — Learning, Bulk Knowledge & Contextual UI

الحالة: **مكتمل ومندمج في main عبر PR #2**.

المخرجات الحالية:

- تعديل الرد المقترح والتعلم بعد تأكيد المالك.
- إدارة تفصيلية للذاكرة والمعرفة والقواعد.
- أوضاع AUTO/APPROVAL/OBSERVE/OFF.
- Bulk Knowledge بالنص والملفات المدعومة.
- Native Telegram rich messages.
- Dynamic customer buttons.
- أزرار دائمة وسياقية.
- retry محدود وآمن لرسائل الإدارة عند أعطال Telegram المؤقتة.

معيار الإغلاق تحقق في 2026-08-22: نجحت الاختبارات الآلية والحية وCI على Python 3.12/3.13، ثم اندمج PR #2 في `main`.

## M7 — Retrieval Quality & Knowledge Operations

الحالة: **مكتمل ومندمج في main عبر PR #3**.

- retrieval quality بقياس 14 حالة top-1 بدل التخمين.
- provenance دائم للمصادر المستخدمة في الموافقة.
- دفعات استيراد مع منع التكرار والتراجع الكامل.
- كشف تعارض المعلومات بدل الاختيار الصامت.
- expiration/versioning للمعرفة مع حفظ النسخ السابقة.
- تأجلت إضافة امتدادات ملفات جديدة لأن الامتدادات الحالية تغطي الحاجة المقاسة، ولا مبرر لتوسيع سطح parser بلا حالة فعلية.

## M8 — Memory Intelligence

الحالة: **مكتمل ومندمج في main عبر PR #4**.

- اقتراح تحديثات ذاكرة الشخص من المحادثة مع موافقة المالك.
- فصل facts/preferences/relationship summary بصورة أوضح.
- confidence + provenance لذاكرة الأشخاص.
- قواعد retention ومسح/تصدير للذاكرة.
- عدم ترقية أي memory إلى business knowledge تلقائيًا.
- تنقية البيانات الحساسة في طبقة محلية مستقلة عن النموذج.
- تقييم دوري قابل للضبط من العميل وإحصاءات رضا للمالك دون تعلم تلقائي.
- migration `0006` وبروفة migration معزولة كاملة.

## M9 — Production Operations

الحالة: **مكتمل ومندمج في main عبر PR #5**.

- deployment موثق على Ubuntu باستخدام systemd/Docker، مع migration service وصورة غير جذرية.
- liveness وreadiness حقيقية، trace IDs، وسجلات JSON مع تنقية الأسرار.
- metrics محمية للأخطاء، latency، AI usage/tokens، approvals، retrieval hits والتقييمات.
- `AiRun` وaudit trail محدودان ولا ينسخان نص الرسائل إلى telemetry.
- backup PostgreSQL بصيغة custom مع checksum وretention وبروفة restore في قاعدة معزولة.
- runbooks للأعطال الشائعة وproduction preflight للمزودات وقاعدة البيانات.
- تدوير ذري لأسرار PostgreSQL/metrics وإجراء موثق لبقية مزودي الخدمات.
- GitHub Actions run `32544458281` نجح على Python 3.12 و3.13 بعد توثيق الإصدار، ثم اندمج PR #5 بالـSHA `8039d79618eb836ffdcef9c6c221fb8b1ab2798f`.

## M10 — Advanced Automation

الحالة: **مكتمل ومندمج في `main` عبر PR #6** بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`.

- Flows فعلية متصلة بمحادثات Telegram Business مع draft/preview/publish ونسخة ثابتة للجلسة.
- schedules/reminders للمالك فقط مع timezone وتسليم one-shot وclaim قابل للاسترداد.
- custom intents management متقدم مع thresholds وربط اختياري بتدفق منشور.
- confidence-based AUTO فعلي ضمن حدود local safety وPUBLIC grounding وحقوق Telegram الحية.
- Core مستقل في `flows/` و`intents/` و`schedules/` مع بقاء Telegram Adapter مسؤولًا عن العرض والإرسال.
- لا يوجد WhatsApp implementation في M10؛ قابلية إضافة قنوات أخرى محفوظة دون ادعاء دعم غير منفذ.

بوابة الإغلاق تحققت: 106 اختبارات، Ruff full، compileall، retrieval 14/14، migration/backup/restore وDocker وTelegram live gates ناجحة. نجح CI التنفيذي run `32546910568` ثم CI التوثيق النهائي run `32547007628` على Python 3.12 و3.13، وبعدها اندمج PR #6.

## ما بعد M10 — Future Expansion

**لا توجد مرحلة M11 نشطة حاليًا.** الخطة الأساسية المنفذة M0–M10 مغلقة ضمن نطاق المنتج الحالي. أي مرحلة لاحقة تُفتح فقط عند وجود متطلب جديد واضح أو مشكلة مقاسة تستدعي تطويرًا إضافيًا.

أمثلة محتملة وليست التزامًا حاليًا:

- قناة إضافية عبر Adapter جديد إذا ظهر احتياج فعلي.
- توسيع الأتمتة أو الجداول إذا ظهرت حالة استخدام موثقة ومناسبة لقيود المنصة.
- بنية استرجاع أثقل فقط إذا فشلت المقاييس الحالية في جودة أو حجم لا تحله البنية البسيطة.
- تحسينات تشغيلية أو تجربة استخدام بناءً على telemetry وfeedback حقيقيين.

نجح CI النهائي run `32547007628` ثم اندمج PR #6 بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`.

## V1 Final Acceptance

الحالة: **مرشح V1 اجتاز CI وNew‑VPS؛ الدمج النهائي قيد التنفيذ**.

أغلقت هذه المرحلة لوحة المالك الفعلية، media basic handling، Native Rich Message مع fallback مؤكد، ودورة مسودة/معاينة/نشر للواجهة. وأضيفت استجابة سياقية للردود المختصرة، منع تكرار التحية، إجراءات Custom Intent الواضحة، ودفع Telegram Stars الآمن لأنها فجوات استخدام فعلية ظهرت في البوابة الحية. مرشح الإصدار هو `1.0.0` ورأس migration هو `0009`.

البوابات المحلية وقاعدة البيانات وDocker وGitHub Actions run `32670663258` والنشر النهائي على New‑VPS مع backup/restore/rollback وproduction preflight ناجحة. لا تغلق المرحلة إلا بعد دمج PR #9 وتثبيت الخادم على SHA الدمج.

## قاعدة التخطيط

لا نضيف بنية تحتية ثقيلة مثل vector DB أو multi-agent أو Redis لمجرد أنها متاحة. تضاف عندما تظهر مشكلة مقاسة في الجودة أو الأداء أو الاعتمادية لا تحلها البنية الحالية ببساطة.
