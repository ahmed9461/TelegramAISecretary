# Project Memory — Telegram AI Secretary

> هذا الملف هو ذاكرة المشروع التشغيلية طويلة المدى. يقرأه أي مبرمج أو AI قبل تنفيذ تعديل كبير، ثم يراجع `MASTER_SPEC.md` والملفات المتخصصة ذات الصلة.

## الحالة الحالية

- المرحلة الحالية: **V1 Final Acceptance** بعد دمج M10؛ يجري إغلاق فجوات التدقيق الفعلية ثم البوابة النهائية الشاملة.
- فرع التطوير الحالي: `codex/final-v1-acceptance`، محدث على baseline الإنتاج `aa7cd4f` بعد إصلاحات Docker/preflight.
- M6 اندمج في `main` عبر PR #2؛ merge SHA: `14011292fe2181618854dae948dae92b79ef3b86`.
- M7 اندمج في `main` عبر PR #3؛ merge SHA: `3f72caef6a9facb82fdbe2e39aa1a016d2823238`.
- M8 اندمج في `main` عبر PR #4؛ merge SHA: `00cbf89841444c322af18fcc8b143fec83a17596`.
- M9 اندمج في `main` عبر PR #5؛ merge SHA: `8039d79618eb836ffdcef9c6c221fb8b1ab2798f`.
- M10 اندمج في `main` عبر PR #6؛ merge SHA: `41deb45feaa763ab51b6df063713c8fcb18f2a22`.
- CI إغلاق M6: GitHub Actions run `32535443695` نجح على Python 3.12 و3.13، مع `compileall` وRuff correctness gate و`pytest`.
- آخر تحقق محلي كامل لـM10: **106 passed, 1 warning**، مع بوابة Ruff الكاملة و`compileall` وretrieval 14/14 ناجحين.
- تقييم الاسترجاع الثابت: **14/14 top-1**.
- رأس PostgreSQL المحلي أصبح `0008`، وبروفة migration المعزولة الكاملة ناجحة.
- بوابة Telegram الحية لـM8 نجحت في 2026-08-22، بما فيها عدم التعلم قبل الموافقة والتقييم من العميل وإحصاءات المالك.
- CI إغلاق M8 النهائي run `32541444456` نجح على Python 3.12 و3.13 قبل دمج PR #4.
- M9 أضاف Docker/systemd محصنين، readiness/metrics/سجلات JSON، AiRun/audit، backup/restore وpreflight/secret rotation.
- بوابة M9 الحية نجحت لـ`/health` و`/ready` وmetrics auth، Telegram/DeepSeek/Gemini، AI telemetry من رسالة Business فعلية، backup/restore معزول، وتدوير أسرار داخلي.
- CI الأول لـM9 في GitHub Actions run `32544367834` نجح على Python 3.12 و3.13؛ شملت مهمة 3.12 أيضًا فحص Compose وبناء صورة الإنتاج.
- CI النهائي لـM9 في run `32544458281` نجح على Python 3.12 و3.13، ثم اندمج PR #5.
- M10 وصل Flow/Custom Intent/Reminder/AUTO الفعلي بالـCore العام، مع واجهات عربية ونشر صريح ونسخ Flow ثابتة للجلسات.
- بوابة M10 الحية نجحت للتدفق الكامل، تذكير مستقبلي مرة واحدة، AUTO حي بصياغة مهنية، API/0008/Docker/backup/restore/preflight، ثم نُظفت البيانات الاصطناعية المحددة فقط.
- CI التنفيذي لـM10 في GitHub Actions run `32546910568` نجح على Python 3.12 و3.13 عند commit `bc5b7787`، مع بناء صورة الإنتاج في مهمة 3.12.
- CI التوثيق النهائي لـM10 في GitHub Actions run `32547007628` نجح على Python 3.12 و3.13، ثم اندمج PR #6.
- تدقيق V1 كشف placeholders إدارية ومعالجة media/Rich/Menu ناقصة؛ لا تُعلن V1 مكتملة قبل إغلاقها. أُغلقت شاشات المحادثات/الأشخاص/الأمان/الإيقاف والرد لمرة واحدة حيًا، مع حجب الأسرار من ملخص المحادثة.
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

## ما تم إنجازه حتى M10

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
- استرجاع عربي/إنجليزي deterministic مع normalization ووزن للعنوان والوسوم ونوع المعلومة.
- استبعاد المعرفة الخاصة والمنتهية، وكشف التعارض بين الحقائق الفعالة بدل الاختيار الصامت.
- دفعات معرفة قابلة للمراجعة والتراجع، ومنع إعادة استيراد المصدر نفسه بصمته.
- versioning عند تعديل المعرفة بدل محو النسخة السابقة.
- حفظ provenance المستخدم في approval كـsnapshot دائم لا يتغير إذا تغيرت المعرفة لاحقًا.
- صياغات إدارة وapproval عربية مهنية لا تعرض أكواد السياسة أو أسماء مزودي الذكاء.
- منع عبارة «كيف أقدر أساعدك اليوم؟» وتوجيه السكرتير لاستخدام سياق النشاط عندما يتوفر.
- اقتراح تحديث ذاكرة الشخص من المحادثة دون أي كتابة قبل اعتماد المالك.
- فصل summary/facts/preferences/private notes مع provenance وconfidence وretention.
- تنقية محلية للبيانات الحساسة وتصدير/مسح ذاكرة من واجهة Telegram.
- تقييم دوري قابل للضبط من العميل الحقيقي، وإحصاءات رضا للمالك دون تعلم تلقائي.
- `AiRun` لكل تشغيل نصي/صورة مع trace، زمن، نتيجة، قرار، token usage ومراجع معرفة دون نسخ نص الرسالة.
- سجل audit للرد الموافق عليه/المرفوض والعمليات الإدارية الحساسة، مع metadata منقاة.
- API تشغيلية: `/health` liveness، `/ready` يعتمد DB/Alembic/config، و`/metrics` محمي اختياريًا بـBearer.
- سجلات JSON منقاة مع trace IDs، وصورة Docker تعمل كمستخدم `secretary` غير جذر.
- backup PostgreSQL custom-format مع checksum/retention وبروفة restore معزولة وحذف قاعدة البروفة دائمًا.
- production preflight حي وتدوير ذري لأسرار PostgreSQL والقياسات.
- Flow/Custom Intent Engine فعلي، بإنشاء ومعاينة ونشر صريح وجلسات snapshot مستقلة.
- تذكيرات owner-only بمنطقة زمنية قابلة للضبط وتسليم one-shot.
- AUTO آمن يرسل فعليًا عبر approval claim ويسجل outgoing وSYSTEM audit.

## دليل إغلاق M6 المحلي — 2026-08-22

- Bulk Knowledge: ثبت أن الإلغاء لا يحفظ شيئًا، ثم حفظ الاعتماد الصريح ثلاث معلومات PUBLIC فقط.
- Source provenance: عرضت بطاقة الموافقة عناصر المعرفة الثلاثة المسترجعة، وكلها PUBLIC كما اختار المالك.
- Native rich: وصل الرد إلى Telegram Business بكيانات تنسيق أصلية، دون raw Markdown/HTML.
- Contextual UI: ظهر الزر السياقي للسؤال المطابق ونفذ الرد الثابت، واختفى من سؤال مستقل غير مطابق بينما بقي الزر الدائم.
- Intent continuity: حفظ approval intent المصنف حتى الإرسال، وظهر زر تجريبي يعتمد على `GREETING` وحده في Telegram ونفذ إجراءه.
- منع التكرار: سجلت الموافقة المطابقة حالة `SENT` ومعرف رسالة Telegram واحدًا فقط، وظهر الرد مرة واحدة في المحادثة.
- Network resilience: اختبار fault injection يثبت محاولتين محدودتين لطلب المالك مع backoff، وعدم إعادة إرسال طلب العميل غير المؤكد.
- حذفت بعد الاختبارات فقط عناصر المعرفة الثلاثة والزرين السياقيين الاصطناعيين، وتأكد بقاء الزر السابق الحقيقي.

## دليل إغلاق M7 — 2026-08-22

- retrieval eval: 14/14 top-1، و72 اختبارًا محليًا.
- اختبار حي للاستيراد المكرر والتعارض والمصادر المحفوظة والنسخ والتراجع والصياغة المهنية.
- بروفة PostgreSQL كاملة حتى `0005`، وCI ناجح على Python 3.12/3.13.
- اندمج PR #3 في `main` بالـSHA `3f72caef6a9facb82fdbe2e39aa1a016d2823238`.

## دليل M8 المحلي والحي — 2026-08-22

- 83 اختبارًا ناجحًا، مع compileall وRuff correctness و14/14 regression للاسترجاع.
- PostgreSQL عند `0006`، وبروفة `upgrade → downgrade base → upgrade` نجحت في قاعدة مؤقتة وحُذفت.
- ثبت حيًا أن الاقتراح لا يكتب الذاكرة قبل الموافقة، وأن OTP/password الاصطناعيين لا يصلان للسجل.
- اعتمد المالك ذاكرة عربية مع provenance/confidence/retention، ثم صدّرها ومسحها بتأكيد.
- ظهر تقييم 1–5 في رد Business حقيقي، وسجل العميل 5 نجوم وظهرت النتيجة في لوحة المالك.
- نُظفت فقط البيانات الاصطناعية المحددة بعد الاختبار، وأعيد تشغيل البوت بالإعداد الدوري الافتراضي (كل 3 ردود).

## دليل M9 المحلي والحي — 2026-08-22

- migration `0007` اجتازت المسار الكامل `upgrade → downgrade base → upgrade` في PostgreSQL مؤقتة.
- بُنيت صورة Docker 0.9.0 من الصفر، وعملت بمستخدم غير جذر؛ `/health` أعاد 200 ورفض `/ready` قاعدة غير مُرحّلة بـ503.
- على قاعدة المشروع الحية: `/health=200`، `/ready=200`، metrics بلا token أعادت 401 ومع token أعادت Prometheus وtrace header.
- production preflight تحقق حيًا من Telegram وDeepSeek وGemini بـHTTP 200 ومن تطابق Alembic `0007`.
- أُنشئت نسخة PostgreSQL custom-format، ثم أعيدت إلى قاعدة عشوائية معزولة وتحققت المراجعة `0007` والأعداد، ثم حُذفت قاعدة الاستعادة.
- دُوّر سر PostgreSQL ورمز metrics محليًا دون طباعتهما، وأعيد تشغيل poller كشجرة واحدة، وبقيت القاعدة والبيانات سليمة.
- رسالة Telegram Business اصطناعية أنشأت AiRun ناجحًا مع latency/tokens وapproval مهني؛ رفض المالك أنشأ audit، ثم نُظفت صفوف الاختبار المحددة وأعيدت المحادثة إلى revision السابق.

## دليل M10 المحلي والحي — 2026-08-22

- 106 اختبارات ناجحة، مع Ruff full وcompileall وretrieval 14/14، ومنها فحص صلاحية AUTO لحظة الإرسال، إلغاء Flow عند الاستلام البشري، وReminder lease recovery.
- migration `0008` اجتازت rehearsal كاملة، ثم رُحلت القاعدة الحية وأعيد backup 0008 معزولًا مع owners=1/conversations=4/messages=37.
- صورة Docker 0.10.0 non-root وhealth/readiness/metrics auth/preflight الحية نجحت.
- أنشئ Flow من Telegram كمسودة، عُوين ونُشر صراحة، ثم بدأه العميل بالنص وجمع سؤالين وأكمله ووصل ملخص مهني للمالك.
- تذكير مستقبلي حسب timezone قابل للتعديل وصل مرة واحدة، وAUTO أرسل تحية «كيف أقدر أساعدك؟» مرة واحدة دون بطاقة أو أكواد.
- بعد الاختبار نُظفت العناصر الاصطناعية المحددة وعادت القاعدة إلى messages=37/revision=17 و0 Flow/Intent/Session/Schedule/AiRun اصطناعي.
- بوابة الموثوقية الأخيرة جعلت claim التذكير lease قابلة للاسترداد، وألزمت AUTO/Flow بإعادة فحص مالك الاتصال وحق الرد قبل كل إرسال؛ لا يعتمد الإرسال على صلاحية مخزنة.
- CI النهائي بعد توثيق الإغلاق نجح في run `32547007628`، ثم اندمج PR #6 إلى `main` بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`.

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

## الخطوة القادمة

إغلاق media basic handling وRich Message الحقيقي وMenu preview/publish، ثم تشغيل بوابات V1 الكاملة وCI/PR النهائي دون تخطي أي معيار.

## ترتيب المراجع عند التعارض

1. `MASTER_SPEC.md` للمبادئ الأساسية غير القابلة للتفاوض.
2. `CONSTANTS.md` للثوابت الحالية.
3. `DECISIONS.md` للقرارات المعمارية المعتمدة بعد الـbaseline.
4. ملف milestone الأحدث مثل `M10_ADVANCED_AUTOMATION.md`.
5. `PROJECT_MEMORY.md` للحالة التشغيلية الحالية.
6. الكود والاختبارات هما المرجع النهائي لما هو منفذ فعليًا.
