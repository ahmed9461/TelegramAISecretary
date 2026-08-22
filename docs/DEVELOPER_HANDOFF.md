# Developer / AI Handoff

استخدم هذا الملف عند تسليم المشروع لمبرمج أو AI جديد.

## قبل أي تعديل

اقرأ `docs/README.md` بالترتيب المقترح، وبالأخص `MASTER_SPEC.md`, `PROJECT_MEMORY.md`, `CONSTANTS.md`, `DECISIONS.md`, `PROGRESS.md`, وملف milestone الحالي.

ثم افحص الكود والمigrations الفعلية قبل اقتراح schema أو إعادة هيكلة. لا تفترض أن وصفًا قديمًا في محادثة خارج Git أحدث من المستودع.

الحالة المسجلة في 2026-08-22: M8 مدمج في `main` بالـSHA `00cbf898`، والتطوير الحالي M9 على `codex/m9-production-operations` برأس migration `0007`. التنفيذ والبوابة المحلية والتشغيلية/Telegram الحية مكتملة، وPR/CI والدمج هما خطوة الإغلاق التالية. تحقق دائمًا من Git/Alembic لأن هذه الجملة ستصبح تاريخية عند إغلاق المرحلة.

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

## قبل اعتبار المهمة منتهية

شغل الاختبارات المناسبة، `compileall`، وفحوص CI. إذا كانت الميزة تعتمد على Telegram Business الحقيقي فاختبار unit وحده لا يكفي؛ نفذ live verification.

حدث التوثيق الذي تغير مع الكود. إذا تغير قرار معماري فأضف ADR. إذا تغير التشغيل فحدث RUNBOOK. إذا تغير وضع milestone فحدث PROJECT_MEMORY وPROGRESS وROADMAP.

في M9 شغّل أيضًا `docker compose config -q`، build للصورة، production preflight، backup+restore rehearsal، وhealth/ready/metrics auth live. ميز بين نجاح إعداد development وبين readiness إنتاجية؛ `APP_ENV=production` وmetrics token قويان شرط نشر حقيقي.

## عند عدم اليقين

لا تخمن حقيقة عن المشروع. ابحث في الكود/الاختبارات/المigrations. إذا وجدت تعارضًا بين docs والكود، سجل التعارض وصحح docs أو التنفيذ بدل إخفائه.
