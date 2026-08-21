# Roadmap

هذا الملف يوضح الاتجاه بعد الحالة الحالية ولا يحول الأفكار المستقبلية إلى التزامات منفذة.

## M0–M4 — Foundation & Stability

الحالة: **مكتمل**.

يشمل الأساس، قاعدة البيانات، Telegram Business ingestion، approvals، Gemini/DeepSeek، debounce، revision locking، edit/delete handling، retrieval الأساسي، وإدارة معرفة أولية.

## M5 — Secretary Brain Foundation

الحالة: **مكتمل ومندمج في main**.

يشمل BusinessProfile وContactMemory وResponsePolicy وواجهة `🧠 عقل السكرتير` وربط الهوية/المعرفة/الذاكرة/القواعد بسياق AI.

## M6 — Learning, Bulk Knowledge & Contextual UI

الحالة: **اجتاز الاختبار الحي محليًا؛ بانتظار نشر آخر diff وإعادة CI ومراجعة PR #2 قبل الدمج**.

المخرجات الحالية:

- تعديل الرد المقترح والتعلم بعد تأكيد المالك.
- إدارة تفصيلية للذاكرة والمعرفة والقواعد.
- أوضاع AUTO/APPROVAL/OBSERVE/OFF.
- Bulk Knowledge بالنص والملفات المدعومة.
- Native Telegram rich messages.
- Dynamic customer buttons.
- أزرار دائمة وسياقية.
- retry محدود وآمن لرسائل الإدارة عند أعطال Telegram المؤقتة.

معيار الإغلاق المحلي تحقق في 2026-08-22: نجحت الاختبارات الآلية، والتغذية الجماعية بالإلغاء والاعتماد، وRich، والزر السياقي بالكلمات في حالتي التطابق وعدم التطابق، والزر المعتمد على intent بعد approval، ووصل كل رد معتمد مرة واحدة. غطى fault injection retry المحدود للمالك ومنع retry لإرسال العميل غير المؤكد. يبقى gate المستودع البعيد: نشر التغييرات، CI جديد على Python 3.12/3.13، مراجعة PR ثم الدمج.

## M7 — Retrieval Quality & Knowledge Operations

مخطط، غير منفذ بعد.

- تحسين retrieval quality بقياسات فعلية بدل التخمين.
- eval dataset لأسئلة الأسعار/السياسات/FAQ والأسئلة بدون مصدر.
- source provenance أوضح لكل رد.
- دعم مصادر معرفة أكبر وملفات إضافية عند الحاجة، مع parser isolation.
- مراجعة/دمج/تعطيل مصادر أو دفعات استيراد كاملة.
- كشف تعارض المعلومات بين مصادر متعددة بدل اختيار صامت.
- expiration/versioning أفضل للمعرفة الحساسة زمنيًا.

## M8 — Memory Intelligence

مخطط.

- اقتراح تحديثات ذاكرة الشخص من المحادثة مع موافقة المالك.
- فصل facts/preferences/relationship summary بصورة أوضح.
- confidence + provenance لذاكرة الأشخاص.
- قواعد retention ومسح/تصدير للذاكرة.
- عدم ترقية أي memory إلى business knowledge تلقائيًا.

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
