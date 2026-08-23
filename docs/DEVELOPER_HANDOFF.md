# Developer / AI Handoff

استخدم هذا الملف عند تسليم المشروع لمبرمج أو AI جديد.

## قبل أي تعديل

اقرأ `docs/README.md` بالترتيب المقترح، وبالأخص `MASTER_SPEC.md`, `PROJECT_MEMORY.md`, `CONSTANTS.md`, `DECISIONS.md`, `PROGRESS.md`, وملف milestone الأحدث.

ثم افحص الكود والمigrations الفعلية قبل اقتراح schema أو إعادة هيكلة. لا تفترض أن وصفًا قديمًا في محادثة خارج Git أحدث من المستودع.

الحالة المسجلة في 2026-08-24: **M10 مدمجة في `main` عبر PR #6** بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`، وتبعتها إصلاحات تشغيل الإنتاج حتى `aa7cd4f`. يجري تطوير `V1 Final Acceptance` على `codex/final-v1-acceptance` برأس migration `0008`: أُغلقت لوحة المالك، وبقيت بوابات media/Rich/Menu والسلوك الحواري والدفع ثم الاختبار النهائي.

تحقق دائمًا من Git/Alembic عند استلام المشروع لأن الحالة قد تتغير بعد هذا السجل.

## قواعد التنفيذ

- نفذ داخل المعمارية الحالية بدل إعادة البناء من الصفر.
- لا hardcode نشاطًا أو خدمة أو سعرًا في Core.
- حافظ على Telegram كـadapter.
- لا تتجاوز local safety policy بقرار LLM.
- لا تسمح لـPRIVATE/private_notes بالدخول للـLLM.
- لا تضف تعلمًا صامتًا.
- لا تحول MemorySuggestion أو Feedback إلى ذاكرة/معرفة تلقائيًا؛ الاعتماد الصريح شرط الكتابة.
- لا تدخل الذاكرة المنتهية أو الأسرار أو private_notes إلى LLM.
- لا تستخدم blind retry لcustomer send غير المؤكد.
- لا تنشئ migration قبل فحص heads والجداول الحالية.
- لا ترفع `.env` أو secrets.
- لا تضف نص الرسائل أو prompts إلى metrics/AiRun/audit/logs؛ telemetry تبقى bounded metadata.
- لا تعتبر backup ناجحًا دون restore rehearsal معزولة، ولا تختبر downgrade على قاعدة الحقيقة.
- لا تحول `/health` إلى فحص dependencies؛ استخدم `/ready` للجاهزية وافشل مغلقًا.
- لا تبدأ M11 أو أي milestone جديدة بالاسم فقط؛ عرّف النطاق ومعايير القبول والسبب المقاس أولًا.

## قبل اعتبار المهمة منتهية

شغل الاختبارات المناسبة، `compileall`، وفحوص CI. إذا كانت الميزة تعتمد على Telegram Business الحقيقي فاختبار unit وحده لا يكفي؛ نفذ live verification.

حدث التوثيق الذي تغير مع الكود. إذا تغير قرار معماري فأضف ADR. إذا تغير التشغيل فحدث RUNBOOK. إذا فتح أو أغلق milestone فحدث PROJECT_MEMORY وPROGRESS وROADMAP وملف milestone نفسه.

عند تعديل طبقة التشغيل التي أغلقتها M9، شغّل أيضًا `docker compose config -q`، build للصورة، production preflight، backup+restore rehearsal، وhealth/ready/metrics auth live. ميز بين نجاح إعداد development وبين readiness إنتاجية؛ `APP_ENV=production` وmetrics token قويان شرط نشر حقيقي.

عند تعديل قدرات M10، أعد Flow/Intent/Reminder/AUTO live gate على Contact تجريبي. أنشئ Flow كمسودة ثم Preview ثم Publish، وتحقق من snapshot الجلسة ومن وصول reminder مرة واحدة. AUTO لا يختبر على بيانات حقيقية حساسة ولا يفعّل على محادثة مشددة؛ نظف فقط IDs الاصطناعية الموثقة بعد القياس.

إرسال AUTO/Flow يعيد فحص Business Connection و`can_reply` لحظة الإرسال. لا تحذف هذا الفحص لصالح الكاش. Reminder claim هي lease افتراضيًا 300 ثانية حتى يستطيع عامل جديد استرداد تذكير علق بعد انهيار العملية.

## عند عدم اليقين

لا تخمن حقيقة عن المشروع. ابحث في الكود/الاختبارات/المigrations. إذا وجدت تعارضًا بين docs والكود، سجل التعارض وصحح docs أو التنفيذ بدل إخفائه.
