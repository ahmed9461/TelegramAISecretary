# Developer / AI Handoff

استخدم هذا الملف عند تسليم المشروع لمبرمج أو AI جديد.

## قبل أي تعديل

اقرأ `docs/README.md` بالترتيب المقترح، وبالأخص `MASTER_SPEC.md`, `PROJECT_MEMORY.md`, `CONSTANTS.md`, `DECISIONS.md`, `PROGRESS.md`, وملف milestone الحالي.

ثم افحص الكود والمigrations الفعلية قبل اقتراح schema أو إعادة هيكلة. لا تفترض أن وصفًا قديمًا في محادثة خارج Git أحدث من المستودع.

## قواعد التنفيذ

- نفذ داخل المعمارية الحالية بدل إعادة البناء من الصفر.
- لا hardcode نشاطًا أو خدمة أو سعرًا في Core.
- حافظ على Telegram كـadapter.
- لا تتجاوز local safety policy بقرار LLM.
- لا تسمح لـPRIVATE/private_notes بالدخول للـLLM.
- لا تضف تعلمًا صامتًا.
- لا تستخدم blind retry لcustomer send غير المؤكد.
- لا تنشئ migration قبل فحص heads والجداول الحالية.
- لا ترفع `.env` أو secrets.

## قبل اعتبار المهمة منتهية

شغل الاختبارات المناسبة، `compileall`، وفحوص CI. إذا كانت الميزة تعتمد على Telegram Business الحقيقي فاختبار unit وحده لا يكفي؛ نفذ live verification.

حدث التوثيق الذي تغير مع الكود. إذا تغير قرار معماري فأضف ADR. إذا تغير التشغيل فحدث RUNBOOK. إذا تغير وضع milestone فحدث PROJECT_MEMORY وPROGRESS وROADMAP.

## عند عدم اليقين

لا تخمن حقيقة عن المشروع. ابحث في الكود/الاختبارات/المigrations. إذا وجدت تعارضًا بين docs والكود، سجل التعارض وصحح docs أو التنفيذ بدل إخفائه.
