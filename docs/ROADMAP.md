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

الحالة: **منفذ واجتاز البوابة المحلية وTelegram الحية وCI على Python 3.12/3.13؛ دمج PR #4 قيد الإغلاق**.

- اقتراح تحديثات ذاكرة الشخص من المحادثة مع موافقة المالك.
- فصل facts/preferences/relationship summary بصورة أوضح.
- confidence + provenance لذاكرة الأشخاص.
- قواعد retention ومسح/تصدير للذاكرة.
- عدم ترقية أي memory إلى business knowledge تلقائيًا.
- تنقية البيانات الحساسة في طبقة محلية مستقلة عن النموذج.
- تقييم دوري قابل للضبط من العميل وإحصاءات رضا للمالك دون تعلم تلقائي.
- migration `0006` وبروفة migration معزولة كاملة.

## M9 — Production Operations

مخطط.

- deployment موثق على Ubuntu باستخدام systemd/Docker حسب الدور.
- health/readiness/structured logs.
- metrics للأخطاء، latency، AI usage، approvals، retrieval hits.
- backup/restore PostgreSQL.
- runbooks للأعطال الشائعة.
- secret rotation procedure.

## M10 — Advanced Automation

مستقبلي ويعتمد على قياسات الحاجة.

- Flows فعلية أكثر من primitives الحالية.
- schedules/reminders عند وجود use case واضح.
- custom intents management متقدم.
- confidence-based AUTO أوسع بعد evals كافية.
- adapters لقنوات أخرى مع الحفاظ على نفس Core.

## قاعدة التخطيط

لا نضيف بنية تحتية ثقيلة مثل vector DB أو multi-agent أو Redis لمجرد أنها متاحة. تضاف عندما تظهر مشكلة مقاسة في الجودة أو الأداء أو الاعتمادية لا تحلها البنية الحالية ببساطة.
