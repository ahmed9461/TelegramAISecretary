# Data Model

هذا الملف يشرح الدور المنطقي للبيانات. تعريف SQLAlchemy وAlembic هما المرجع النهائي للتفاصيل الفعلية.

## الهوية والاتصال

### owners
يمثل مالك السكرتير وإعداداته العامة مثل الوضع الافتراضي.

### business_connections
يحفظ اتصال Telegram Business المرتبط بالمالك، صلاحياته، حالته وآخر ظهور. لا يحفظ Telegram user session غير رسمي.

## الأشخاص والمحادثات

### contacts
جهة الاتصال القادمة من Telegram. مرتبطة بالمالك ومعزولة عنه.

### conversations
محادثة المالك مع Contact. تحتوي state، summary، business connection، revision وتواريخ النشاط.

### messages
أرشيف الرسائل الواردة والصادرة مع Telegram message ID وحالة edit/delete. يستخدم لبناء recent context والبحث المحلي.

## عقل السكرتير

### business_profiles
هوية النشاط/العلامة، وصف النشاط، المجال، أسلوب الرد، اللغة، النبرة، custom instructions و`extras_json`.

### knowledge_items
مصدر الحقائق القابلة للاسترجاع. أهم المفاهيم: type، title، content، visibility، tags، active/validity metadata، `batch_id`، `version`، `supersedes_id` و`content_hash`. تعديل المحتوى ينشئ نسخة جديدة ويحوّل السابقة إلى `SUPERSEDED`.

### knowledge_batches
سجل عملية استيراد معرفة: المالك، اسم/نوع المصدر، visibility، بصمة المحتوى، عدد العناصر، الحالة وmetadata. يسمح بمنع استيراد المصدر نفسه والتراجع عن عناصر دفعة كاملة دون حذف التاريخ.

### contact_memories
ذاكرة معزولة لشخص واحد: summary، facts_json، preferences_json، private_notes وshare_with_ai.

### response_policies
قواعد المالك: name، description، scope، action، priority، conditions_json، constraints_json، enabled.

## الموافقات والتشغيل

### approvals
مسودة رد مربوطة بالمحادثة وrevision وtrigger message، مع candidate response وحالة lifecycle وTTL ومعلومات رسالة بطاقة المالك والإرسال النهائي. في M7 يحتوي `context_json` على intent وsnapshot محدود لمصادر المعرفة والتعارض وقت إنشاء المسودة.

### escalations
تمثل الحالات التي تحتاج تدخلًا من المالك عندما يكون ذلك مستخدمًا في المسار.

### ai_runs
سجل عمليات AI عندما يستخدمه المسار، لأغراض التتبع والتقييم.

### feedback
مكان لتسجيل تغذية راجعة/تقييمات عند استخدامها.

### audit_logs
سجل تغييرات وأحداث إدارية ذات قيمة تدقيقية.

## الواجهة الديناميكية

### menu_profiles
تعريف واجهة وقيم مثل mode وscope وwelcome_message.

### menu_items
زر ديناميكي يمكن أن يكون له parent، label/emoji، action type، action config، ترتيب، enabled وvisibility rules. في M6 تستخدم `visibility_rules_json` لتمييز زر دائم أو سياقي.

### custom_intents
تعريف intent قابل للبيانات بدل hardcoding النشاط.

## Flows

### flows
تعريف flow قابل للإصدار والحالة.

### flow_steps
خطوات flow مثل ask text/choice/file أو complete.

### flow_sessions
حالة تنفيذ flow لمحادثة محددة مع version/state/progress.

## Schedules

### schedules
طبقة زمنية مستقبلية/تشغيلية حسب ما هو معرف في schema الحالي. لا تعتبر أي ميزة schedule مكتملة لمجرد وجود الجدول.

## قواعد ownership والعزل

- كل business knowledge/policy/profile مرتبط بالمالك.
- ContactMemory مرتبط بContact واحد ولا يخلط بين الأشخاص.
- Conversation وMessage لا يشاركان بين مالكين.
- PRIVATE وprivate_notes لا يذهبان إلى LLM.
- حذف كيان رئيسي يجب أن يحترم علاقات FK وسياسة cascade المعرفة في الموديلات والمigrations.

## Migrations الحالية

- `0001_initial`
- `0002_stability`
- `0003_secretary_brain`
- `0004_m7_knowledge_operations`
- `0005_m7_approval_provenance`

قبل إنشاء migration جديد: افحص رأس Alembic الحالي والموديلات الموجودة، ولا تنشئ جدولًا مكررًا لمفهوم موجود أصلًا.
