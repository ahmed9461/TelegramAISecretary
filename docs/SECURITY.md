# Security Model

## Trust Boundaries

المشروع يفصل بين مصادر موثوقة ومحتوى غير موثوق. الرسائل والصور والملفات الواردة من Contact تعامل كبيانات فقط. تعليمات المستخدم داخل نص أو مستند أو صورة لا تغير system policy أو قواعد المالك.

## Owner-only administration

كل واجهة إدارة حساسة تتحقق من Telegram user ID للمالك. فتح البوت مباشرة من مستخدم آخر لا يمنحه لوحة الإدارة أو بيانات المعرفة والذاكرة.

## Secrets

- Tokens وAPI keys لا تدخل Git.
- `.env` ونسخه الاحتياطية والمفاتيح الخاصة يجب تجاهلها.
- `.env.example` placeholders فقط.
- Settings fields الحساسة لا تظهر في repr حيث طبق ذلك.
- عند تسريب secret إلى commit يجب تدويره؛ حذف الملف من working tree وحده لا يكفي.
- production preflight يرفض password الافتراضي وmetrics token المفقود.
- `scripts.rotate_internal_secrets` يولد PostgreSQL password وmetrics token جديدين، يغير دور PostgreSQL ثم يستبدل `.env` ذريًا ويتحقق من الاتصال دون طباعتهما.
- Telegram/DeepSeek/Gemini keys تدور من لوحة المزود، ثم تحدث `.env` محليًا وتعاد الخدمات؛ لا تحفظ القيمة القديمة في backup نصي.

## Operational telemetry

- Structured logging ينقي authorization/token/password/secret/API key patterns قبل الإخراج.
- AiRun وPrometheus لا ينسخان محتوى الرسائل أو prompts أو private notes.
- metrics تستخدم Bearer token في production، وتربط API افتراضيًا على loopback.
- AuditLog metadata تمر عبر allow-by-type/block-by-key ولا تخزن المحتوى الحر الحساس.
- backup files مستبعدة من Git، وتحتاج صلاحيات خاصة ونقلًا مشفرًا عند خروجها من الجهاز.

## Knowledge confidentiality

- `PUBLIC`: يمكن عرضه للعميل.
- `INTERNAL`: يستخدم للتوجيه الداخلي ولا يجب كشفه على أنه سياسة داخلية.
- `PRIVATE`: لا يدخل LLM retrieval.
- `ContactMemory.private_notes`: Owner-only ولا تدخل سياق AI.
- اقتراح الذاكرة لا يكتب ContactMemory قبل اعتماد المالك، والـretention المنتهي يعطل مشاركة الذاكرة.
- طبقة محلية تستبعد OTP والبطاقات وIBAN وكلمات المرور ومفاتيح الخدمات والبيانات الصحية من الذاكرة المشتركة.

## Prompt Injection

- `wrap_untrusted` يحدد user-provided content عند بناء prompts.
- النص المستخرج من الصور عبر Gemini يظل untrusted.
- Bulk ingestion extractor ممنوع من تنفيذ تعليمات المصدر؛ يستخرج حقائق فقط.
- لا يسمح لمحتوى العميل بطلب كشف prompts أو policies أو PRIVATE data أو credentials.

## Hallucination & Business Commitments

الذكاء ليس مصدر الحقيقة لمعلومات المالك. الأسعار، الخصومات، التوفر، المواعيد، العقود، الموافقات والالتزامات تحتاج grounding مناسب. عند غياب المصدر يجب طلب توضيح أو التصعيد بدل الاختراع.

## Send Safety

- Approval draft مربوط بـconversation revision وTTL.
- تغير السياق يبطل draft قديم.
- فحص live `can_reply` قبل approved send.
- one-shot claim يمنع الضغط المكرر من إرسال نفس approval أكثر من مرة.
- الإرسال غير المؤكد للعميل ينتقل إلى `UNCERTAIN` ولا يعاد عميانيًا.
- retry الشبكي المضاف في M6 محصور بطلبات المالك/الإدارة حيث خطر تكرار الإجراء مقبول ومحدود؛ customer sends لا تدخل هذا retry العام.

## Conversation Safety States

`HUMAN_TAKEOVER`, `ESCALATED`, `PAUSED`, `EXCLUDED`, `OBSERVE_ONLY` تمنع أو تقيد AI حسب الحالة. Global AUTO لا يلغي هذه الحالات الأكثر تشددًا.

## Files & Bulk Ingestion

- هناك حدود حجم للمصادر والصور.
- امتدادات bulk المدعومة حاليًا نصية/هيكلية: TXT, MD, CSV, JSON, YAML/YML.
- لا نثق باسم الملف أو محتواه كتعليمات.
- الحفظ الجماعي يحدث بعد preview واعتماد المالك.

## Telegram callbacks

Callback query قد ينتهي سريعًا. handler يجب أن يجيب مبكرًا أو يستخدم `safe_callback_answer` بحيث لا يتحول `query is too old` إلى crash.

تقييم الرد يتحقق من أن `callback.from_user.id` يطابق Contact الذي استلم Approval؛ المالك أو شخص آخر لا يستطيع تسجيل تقييم لذلك الرد. التقييم لا يمنح أي صلاحية إدارية ولا يفعّل تعلمًا تلقائيًا.

## قاعدة مراجعة أمنية

أي ميزة جديدة يمكنها: إرسال مال، تغيير التزام، كشف بيانات خاصة، تنفيذ رابط/كود، أو تجاوز موافقة المالك — تعامل كميزة عالية المخاطر وتحتاج policy محلية + tests قبل تمكينها تلقائيًا.
