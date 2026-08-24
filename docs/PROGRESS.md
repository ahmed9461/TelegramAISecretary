# Progress

## M0/M1 — Foundation

### Implemented

- Python project/configuration + FastAPI health/readiness.
- SQLAlchemy models and Alembic baseline.
- owners, Business Connections, contacts, conversations, messages, knowledge, menus, intents, flows, approvals and audit primitives.
- Owner-only authorization.
- conversation state machine.
- Dynamic Menu/Button primitives with `AI_ONLY / CUSTOM_MENU / HYBRID`.
- Flow Engine primitives.
- deterministic AI decision policy skeleton.
- Telegram adapter contract + aiogram Business events.
- persistence/idempotency for Business messages.
- approval revision binding and one-shot claiming.
- CI for Python 3.12/3.13.

## M2 — Gemini Vision + DeepSeek

### Implemented

- `VisionProvider` abstraction.
- Gemini image understanding with structured observation.
- `AIProvider` / DeepSeek reasoning and reply drafting.
- image → Gemini → DeepSeek → local policy → approval.
- image prompt-injection boundary.
- Telegram photo download with size limit.
- owner Send/Reject approval flow.
- failure-safe behavior when providers fail.

## M3 — Text AI & Provider Reliability

### Implemented

- text → DeepSeek → local policy → approval path.
- provider configuration isolated from secrets.
- retry/fallback improvements for AI providers.
- test settings isolation to avoid accidental `.env` dependence in unit tests.

## M4 — Hybrid Stability

### Implemented

- recover missing Business Connection through `getBusinessConnection`.
- verify live `can_reply` immediately before approved sends.
- reject unexpected owner connections.
- per-chat debounce.
- conversation revision validation before candidate creation.
- approval supersession and TTL.
- approval card status updates.
- approved/manual outgoing messages stored in history.
- edit/delete Business messages invalidate stale drafts.
- recent conversation context with untrusted markers.
- DeepSeek transient retry.
- Gemini retry/fallback.
- PostgreSQL knowledge retrieval; PRIVATE excluded.
- owner knowledge commands and message archive search.
- Docker PostgreSQL binding on localhost:5433.
- migration `0002_stability`.

### Verification at milestone close

```text
33/33 tests passed
compileall passed
```

## M5 — Secretary Brain Foundation

### Implemented

- `BusinessProfile` with configurable identity/activity/style/instructions.
- `ContactMemory` isolated per Contact.
- `ResponsePolicy` data-driven owner rules.
- migration `0003_secretary_brain`.
- `🧠 عقل السكرتير` admin UI.
- profile + memory + response policies merged into AI context.
- public-grounding rule for business facts.
- knowledge source visibility preserved.
- owner-side management for the brain foundation.

### Live result

M5 was tested live through Telegram Business and accepted for merge into `main` before M6 began.

## M6 — Secretary Learning, Bulk Knowledge & Contextual UI

**Status: مكتمل ومندمج في `main` عبر PR #2.**

### Approval & learning

- edit candidate reply before send.
- show retrieved knowledge sources.
- explicit `learn from my edit` confirmation.
- learned edit stored INTERNAL only; no silent PUBLIC fact creation.

### Memory & policy operations

- list contacts with memories.
- review/edit memory summary.
- owner-only private notes.
- enable/disable AI sharing per contact.
- clear memory.
- knowledge item view/edit/delete/change visibility.
- response policy view/edit/enable/disable/delete.
- global `AUTO / APPROVAL / OBSERVE / OFF` UI with safety ceiling semantics.

### Bulk Knowledge

- `📥 تغذية العقل` UI.
- paste large text or upload TXT/MD/CSV/JSON/YAML/YML.
- DeepSeek extraction into GENERAL/SERVICE/PRODUCT/PRICE/FAQ/POLICY/CUSTOM.
- chunking for large sources.
- normalize/deduplicate results.
- preview before save.
- save all only after explicit owner approval.
- extractor forbidden from inventing/correcting/completing absent facts.

### Telegram Rich UI

- native Telegram rich renderer using MessageEntity.
- no raw HTML/Markdown required from LLM.
- dynamic menu actually attached to Business replies through Telegram adapter.
- URL buttons rendered as URL buttons.
- admin UI for button creation.

### Contextual Buttons

- buttons can be 🌐 ALWAYS or 🎯 CONTEXTUAL.
- contextual visibility uses configured keywords and/or intents.
- matching examines current user/reply context deterministically.
- payment buttons can appear for payment context and stay hidden for unrelated questions.

### Reliability fixes discovered in live testing

- safe handling for expired callback query (`query is too old`).
- live Windows test exposed `WinError 64` after DeepSeek returned HTTP 200 while sending owner approval card.
- added `ResilientOwnerBot` with limited retry for owner/admin Bot API requests only.
- customer sends remain fail-closed and are not blindly retried to prevent duplicates.

### Latest verified CI

Commit/PR CI on 2026-08-21:

```text
Python 3.12: PASS
Python 3.13: PASS
Ruff correctness gate: PASS
compileall: PASS
pytest: 56 passed, 1 warning
```

The remaining warning is the Starlette TestClient/httpx deprecation warning. Full Ruff report still shows pre-existing formatting/style debt because that step is informational (`--exit-zero`); the blocking correctness gate passes.

### Local live closure evidence — 2026-08-22

- Bulk cancel left zero KnowledgeItems for the synthetic marker.
- Explicit bulk approval saved three PUBLIC items and made them available to retrieval.
- The approval Sources action showed all three retrieved items with the selected PUBLIC visibility.
- The approved Business reply arrived once, with native Telegram bold entities and no raw markup.
- A contextual fixed-reply button appeared for the matching payment question, executed successfully, and stayed absent from an unrelated greeting; the existing ALWAYS button remained visible.
- The classified intent now survives the approval delay and reaches menu matching; an intent-only `GREETING` button appeared and executed in a second live smoke test.
- The matching approval reached `SENT` with one `sent_telegram_message_id`, consistent with the single reply observed in Telegram.
- Added fault-injection coverage for owner retry/backoff and fail-closed customer sends.
- Removed only the three synthetic KnowledgeItems and two synthetic contextual MenuItems after verification; the pre-existing MenuItem remained.

Local verification after the added tests:

```text
pytest: 60 passed, 1 warning
compileall: PASS
Ruff correctness gate: PASS
```

أغلق CI البعيد اللاحق بوابة M6 على Python 3.12 و3.13، ثم اندمج PR #2 في `main` بالـSHA `14011292fe2181618854dae948dae92b79ef3b86`.

## M7 — Retrieval Quality & Knowledge Operations

**Status: مكتمل ومندمج في `main` عبر PR #3.**

### Implemented

- Arabic/English deterministic retrieval normalization ووزن قابل للتفسير للعنوان والوسوم ونوع المعرفة.
- eval dataset ثابت للأسعار والسياسات والدفع والدعم والخدمات والأسئلة بلا مصدر.
- استبعاد PRIVATE والمنتهي زمنيًا.
- كشف تعارض الحقائق الفعالة وإجبار موافقة المالك بدل اختيار معلومة بصمت.
- `KnowledgeBatch` مع content hash، منع duplicate import، حالة الدفعة، والتراجع عن دفعة كاملة.
- versioning لعناصر المعرفة عند تعديل العنوان/المحتوى مع حفظ النسخة السابقة.
- approval provenance snapshot محفوظ في `approvals.context_json` ويظل قابلًا للمراجعة بعد تغير المعرفة.
- واجهة إدارة للدفعات والنسخ والمصادر والتعارض بصياغة مهنية.
- copy guard يمنع عرض أكواد داخلية وأسماء المزودين وعبارة «كيف أقدر أساعدك اليوم؟».
- migrations `0004_m7_knowledge_operations` و`0005_m7_approval_provenance`.

### Automated gate — 2026-08-22

```text
retrieval evaluation: 14/14 top-1
pytest: 72 passed, 1 known warning
compileall: PASS
Ruff correctness gate: PASS
PostgreSQL migration head: 0005
isolated PostgreSQL upgrade → downgrade base → upgrade: PASS
```

التحذير المعروف هو Starlette TestClient/httpx deprecation ولا يمثل فشلًا تشغيليًا.

### Telegram live gate — 2026-08-22

- حفظ مصدر PUBLIC في دفعة واحدة، ثم رفض إعادة المصدر نفسه دون إنشاء نسخة.
- إنشاء حقيقة سعر ثانية متعارضة؛ أظهرت المصادر النسختين وعبارة التعارض المهنية.
- ظل approval provenance snapshot يعرض المصادر نفسها بعد التراجع عن دفعة التعارض.
- رفضت المسودة المتعارضة دون إرسال، ثم وصل الرد الصحيح مرة واحدة بعد إزالة التعارض.
- تعديل معلومة من Telegram أنشأ النسخة 2 مع بقاء النسخة 1 كسجل سابق.
- وصلت التحية بصيغة «كيف أقدر أساعدك؟» دون كلمة «اليوم» أو اسم provider.
- كشف الاختبار أكواد type وvisibility في شاشتين إداريتين؛ حُولت إلى أوصاف عربية، وأعيد اختبار المعاينة حيًا بنجاح.
- تراجع الاختبار عن الدفعتين، ثم أزيلت عناصر ودفعات الاختبار المحددة فقط. بقيت المعرفة الحقيقية #1 والزر الحقيقي الفعال دون تغيير.
- حالات الموافقات الثلاث: `REJECTED` لمسودة التعارض، و`SENT` للرد الصحيح والتحية، وكل إرسال يملك Telegram message ID واحدًا.

بروفة migration معزولة كشفت أن downgrade لـ`0004` اعتمد اسم قيد ثابتًا لم يكن مضمونًا في القاعدة الجديدة. عُدّل downgrade لاكتشاف اسم FK الفعلي، ثم نجح المسار الكامل `upgrade head → downgrade base → upgrade head` وانتهى عند `0005`; حُذفت قاعدة البروفة المؤقتة.

### Remote CI

GitHub Actions run `32538952535` (#104) نجح بالكامل:

```text
Python 3.12: PASS
Python 3.13: PASS
Ruff correctness: PASS
compileall: PASS
pytest: PASS
```

اكتمل CI النهائي ثم اندمج PR #3 في `main` بالـSHA `3f72caef6a9facb82fdbe2e39aa1a016d2823238`.

## M8 — Memory Intelligence & Feedback

**Status: مكتمل ومندمج في `main` عبر PR #4.**

### Implemented

- جدول اقتراحات ذاكرة منفصل؛ لا يغيّر ContactMemory قبل اعتماد المالك.
- summary/facts/preferences مع provenance وconfidence وretention ومراجعة يدوية.
- استبعاد الذاكرة المنتهية أو غير المسموح بمشاركتها من سياق AI.
- تنقية OTP/بطاقة/IBAN/API secrets/بيانات صحية في طبقة محلية مستقلة عن النموذج.
- واجهة Telegram عربية للاقتراح والاعتماد/الرفض والتحرير والتصدير والمسح المؤكد.
- Feedback 1–5 من مستلم الرد فقط، بتكرار قابل للضبط وإحصاءات رضا للمالك.
- migration `0006` وأداة بروفة قاعدة مؤقتة قابلة لإعادة التشغيل.

### Automated gate — 2026-08-22

```text
pytest: 83 passed, 1 known warning
compileall: PASS
Ruff correctness gate: PASS
M7 retrieval regression: 14/14 top-1
PostgreSQL head: 0006
isolated PostgreSQL upgrade → downgrade base → upgrade: PASS
```

التشغيل الكامل لـRuff ما زال يعرض 30 ملاحظة تنسيق قديمة خارج ملفات M8؛ بوابة correctness الحاجبة وملفات M8 نفسها ناجحة. التحذير الوحيد في pytest هو Starlette TestClient/httpx المعروف.

### Telegram live gate — 2026-08-22

- اقتراح حي من محادثة تحتوي تفضيلات وOTP/password اصطناعيين؛ بقيت الذاكرة صفرًا قبل الاعتماد.
- لم تظهر القيم الحساسة في الاقتراح أو السجل، وتحولت المفاتيح إلى صياغة عربية مهنية.
- بعد الاعتماد ظهرت الحقائق والتفضيلات مع provenance/confidence وتاريخ retention.
- نجح تصدير JSON للمالك واختبار مسح الذاكرة مع confirmation دون حذف المحادثة.
- رد Business حقيقي أظهر شريط تقييم 1–5، وسجل العميل 5 نجوم.
- شاشة `📊 رضا العملاء` عرضت 5.0 من 5 وتوزيعًا صحيحًا.
- حُذفت بعد الاختبار السجلات الاصطناعية المحددة فقط: ذاكرة واحدة، 3 اقتراحات، تقييم واحد ومعلومة PUBLIC واحدة. أعيد تشغيل البوت بالإعداد الافتراضي كل 3 ردود.

### Remote CI

GitHub Actions run `32541333524` (#109) نجح بالكامل:

```text
Python 3.12: PASS
Python 3.13: PASS
Ruff correctness: PASS
compileall: PASS
pytest: PASS
```

اكتمل CI النهائي ثم اندمج PR #4 في `main` بالـSHA `00cbf89841444c322af18fcc8b143fec83a17596`.

## M9 — Production Operations

**Status: مكتمل ومندمج في `main` عبر PR #5.**

### Implemented

- `AiRun` عند migration `0007`: trace/operation/provider/model/intent/risk/action/confidence، زمن، token usage، knowledge refs وحالة الخطأ دون نسخ نص الرسالة.
- تجميع Prometheus للرسائل والموافقات وAI latency/errors/tokens وretrieval hits والتقييمات ضمن نافذة قابلة للضبط.
- `/health` خفيف للـliveness، و`/ready` يتحقق من الاتصال ورأس Alembic وإعداد Telegram/AI، و`/metrics` يدعم Bearer token بمقارنة ثابتة الزمن.
- JSON logging مع trace IDs وتنقية محلية للتوكنات وكلمات المرور والمفاتيح والأسرار.
- audit trail للردود المرسلة/المرفوضة وحذف المعرفة/السياسات/الأزرار ومسح الذاكرة والتراجع عن الدفعات، دون metadata حرة حساسة.
- Dockerfile يعمل بمستخدم غير جذر، وCompose ثابت الاسم مع postgres/migrate/api/bot وhealth checks وربط localhost فقط.
- systemd units محصنة لـmigration/api/bot وbackup timer يومي.
- backup custom-format مع checksum/manifest/retention، وبروفة restore في قاعدة عشوائية محددة الاسم تُحذف في `finally`.
- production preflight حي لـDB revision وTelegram وDeepSeek وGemini، وتدوير ذري لأسرار PostgreSQL وmetrics.
- جعل إصدار التطبيق من `app.__version__` وربطه ديناميكيًا بالحزمة لمنع اختلاف إصدار المصدر وmetadata المحلية.
- سداد ملاحظات Ruff التاريخية المتبقية وتحويل CI من correctness subset + تقرير غير حاجب إلى بوابة Ruff كاملة تشمل app/tests/scripts/migrations.

### Automated/local operations gate — 2026-08-22

```text
pytest full suite after final documentation: 92 passed, 1 known warning
M9 focused suite after readiness/rotation metrics hardening: 9 passed
compileall: PASS
Ruff full repository gate: PASS
PostgreSQL head: 0007
Alembic check: PASS
isolated PostgreSQL upgrade → downgrade base → upgrade: PASS
docker compose config: PASS
Docker image build: PASS
Docker non-root health/readiness smoke: PASS
```

التحذير الوحيد المعروف هو Starlette TestClient/httpx، ولا يمثل فشلًا تشغيليًا.

### Live operations + Telegram gate — 2026-08-22

- رُحلت قاعدة المشروع additive من `0006` إلى `0007`، وظلت Owner والمعرفة الفعالة دون تغيير.
- صورة الإنتاج 0.9.0 عملت بالمستخدم `secretary`; liveness نجح، وreadiness فشل مغلقًا بـ503 عند قاعدة smoke غير مرحّلة.
- API الحية على قاعدة المشروع: health=200، ready=200، metrics غير المفوضة=401، metrics المفوضة=200 مع trace ID.
- production preflight حي: Telegram/DeepSeek/Gemini جميعها HTTP 200، والقاعدة عند رأس المصدر.
- نسخة PostgreSQL حقيقية استعيدت في قاعدة `secretary_restore_*`: revision `0007` وcounts owners/conversations/messages صحيحة، ثم حُذفت قاعدة البروفة.
- دُوّر سر PostgreSQL وmetrics token محليًا؛ أعيد تشغيل البوت واستمر poller واحد بلا conflict أو خطأ قاعدة بيانات.
- رسالة Business اصطناعية أنشأت AiRun `SUCCESS` وقياسات latency/tokens، وأظهرت بطاقة موافقة عربية مهنية واقتراحًا متعلقًا بالنشاط دون العبارة الممنوعة.
- رفض البطاقة أنشأ audit `PROPOSED_RESPONSE_REJECTED`. بعد التحقق أزيلت فقط AiRun/approval/audit/message الاصطناعية وأعيد conversation revision؛ بقيت 37 رسالة وKnowledgeItem حقيقية فعالة واحدة، والذاكرة/feedback الاصطناعيان صفرًا.

### Remote CI

- فُتح PR #5 من `codex/m9-production-operations` إلى `main` عند commit `8b956f95d0cf52338007f0718a732e8a44a79470`.
- GitHub Actions run `32544367834`: Python 3.12 و3.13 PASS.
- تضمنت مهمة Python 3.12 بوابة Ruff الكاملة و`compileall` و`pytest` والتحقق من Compose وبناء صورة الإنتاج، وجميعها PASS.
- GitHub Actions run `32544458281` للـcommit الموثق النهائي: Python 3.12 و3.13 PASS، مع بناء صورة الإنتاج على 3.12.
- اندمج PR #5 بالـSHA `8039d79618eb836ffdcef9c6c221fb8b1ab2798f`.

## M10 — Advanced Automation

**Status: مكتمل ومندمج في `main` عبر PR #6 بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`.**

### Implemented

- Flow sessions فعلية متصلة برسائل Business، مع snapshot كامل لنسخة التدفق لمنع كسر الجلسة عند التعديل.
- معالج عربي ينشئ Flow كمسودة، يعرض Preview، وينشره فقط بقرار صريح؛ نسخة التعديل الجديدة تؤرشف السابقة عند نشرها وتعيد ربط النية بأمان.
- Custom Intents CRUD/enable/disable وthreshold من إعداد المالك؛ المطابقة عربية/إنجليزية محلية ولا تمنح إذن إرسال.
- بدء Flow بالنص الحر أو زر ديناميكي عبر Telegram Adapter، وإلغاء عام دون مفردات برمجية.
- تذكيرات owner-only بمنطقة زمنية قابلة للتعديل وclaim lease يمنع التوازي ويتيح retry بعد فشل مؤكد أو استرداد عامل منهار.
- AUTO الفعلي يستخدم نفس approval lifecycle كسجل idempotency، ويعيد فحص صلاحية Telegram لحظة الإرسال، ويسجل outgoing وAuditLog باسم SYSTEM.
- Flow يتوقف عند الاستلام البشري والحالات المقيدة، ويتحقق أن ضغط الخيار صادر من Contact نفسه، ويعيد فحص صلاحية الإرسال الحية.
- إصلاح مقارنة expiry القادمة من SQLite بلا timezone، وإصلاح `/start` لقراءة وضع المالك الحقيقي.
- migration `0008` تضيف `flow_sessions.definition_json` وجدول `schedules`.

### Automated/local gate — 2026-08-22

```text
pytest: 106 passed, 1 known warning
Ruff full repository gate: PASS
compileall: PASS
retrieval regression: 14/14 top-1
Alembic head/check: 0008 / PASS
isolated PostgreSQL upgrade → downgrade base → upgrade: PASS
Docker Compose config/build/non-root smoke: PASS
```

### Live gate — 2026-08-22

- backup قبل الترحيل عند 0007 محفوظ، ثم رُحلت القاعدة إلى 0008 ونجح check.
- backup بعد الترحيل استعيد معزولًا عند 0008: owners=1، conversations=4، messages=37.
- image 0.10.0: non-root، health 200، smoke readiness 503، والـAPI الحية ready 200 عند 0008 وmetrics auth 401/200.
- Telegram/DeepSeek/Gemini preflight الحي: HTTP 200.
- أنشأ المالك Flow من الواجهة وعُوين قبل النشر؛ بدأه العميل بالنص الحر وجمع سؤالين وأكمله، ووصل ملخص مهني للمالك.
- تذكير مستقبلي حسب Asia/Riyadh وصل مرة واحدة ثم أصبح غير فعال.
- تحية في AUTO خرجت مباشرة مرة واحدة بصياغة «كيف أقدر أساعدك؟» دون «اليوم» أو reason codes، مع AiRun SUCCESS وApproval SENT وAudit SYSTEM.
- نُظفت العناصر الاصطناعية المحددة فقط؛ عادت القاعدة إلى messages=37، revision=17، ai_runs=0، flows/intents/sessions/schedules=0.

### Remote CI

- فُتح PR #6 عند commit `bc5b7787d70c0c60a41ead552635a311b560341c`.
- نجح GitHub Actions run `32546910568` على Python 3.12 و3.13؛ شملت 3.12 بوابة Ruff/compileall/pytest وبناء صورة الإنتاج.
- نجح GitHub Actions run `32547007628` بعد تحديث دليل الإغلاق على Python 3.12 و3.13.
- اندمج PR #6 في `main` بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`.

## Documentation hardening — 2026-08-22

Documentation was promoted to a first-class project artifact. Added/updated:

- project memory.
- constants/invariants.
- architecture.
- roadmap.
- data model.
- security model.
- AI behavior.
- knowledge/memory guide.
- Telegram UI guide.
- acceptance criteria.
- M6 milestone document.
- current runbook and README.

Goal: the repository itself must be sufficient context for a new developer/AI without relying on the chat history as the only project memory.

## Final documentation closure — 2026-08-23

- تمت مزامنة حالة M10 في README وPROJECT_MEMORY وROADMAP وM10 report وACCEPTANCE_CRITERIA وDEVELOPER_HANDOFF وفهرس التوثيق.
- أصبحت كل بوابات M10 مغلقة، بما فيها CI النهائي والدمج إلى `main`.
- baseline المنتج الحالي هو `main` بالإصدار `0.10.0` ورأس migration `0008`.
- لا توجد M11 نشطة؛ أي تطوير لاحق يفتح كمرحلة جديدة بنطاق ومعايير قبول مستقلة.

## V1 Final Acceptance — Owner administration

**Status: مكتمل ضمن V1 ومندمج في `main`.**

- اندمج M10 عبر PR #6 بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22` بعد CI النهائي run `32547007628`.
- استُبدلت أقسام المحادثات/بانتظارك/الأشخاص/الأمان/الإيقاف الوهمية بشاشات owner-only فعلية.
- أضيفت إدارة حالة المحادثة، الاستلام البشري والعودة، الرد لمرة واحدة، ملخص السياق، وإعدادات AI/Memory/Exclusion لكل Contact مع audit.
- ملخص المحادثة يحجب الأنماط الحساسة محليًا ولا يحولها إلى ذاكرة طويلة المدى.
- البوابة المركزة: 5 اختبارات ناجحة وRuff/compileall ناجحان.
- البوابة الحية قرأت الشاشات الأربع وتفاصيل محادثة دون تغيير إعداد أو إرسال رد لعميل حقيقي.

## V1 Final Acceptance — Conversation, media, interface, and payments

**Status: مكتمل ومندمج في `main` عبر PR #9 بالـSHA `db68fda8046ff90a2958e9f0c33de1e6ba8fb5b2`.**

### Implemented

- حل سياقي مؤقت للأرقام ونعم/لا والردود القصيرة بالرجوع إلى آخر سؤال صادر، مع إبقاء الرسالة الأصلية كما هي وعدم إنشاء تعلم.
- منع التحية الافتتاحية بعد وجود رد سابق وتنظيف Markdown الخام والعناوين والرموز البرمجية قبل التسليم.
- Voice/Audio/Document basic handling آمن عبر Gemini ثم DeepSeek والسياسة العامة نفسها، مع redaction وسجلات metadata محدودة.
- Native Rich Message منظم فعليًا، وplain-text fallback مرة واحدة فقط بعد `TelegramBadRequest` مؤكد.
- دورة Menu draft/preview/edit/reorder/publish؛ المعاينة لا تنفذ الإجراء والتغيير لا يصل للعملاء قبل تأكيد النشر.
- Custom Intent يعرض دائمًا ثلاثة إجراءات: تحسين الفهم فقط، رد ثابت بموافقة، أو متابعة بشرية، ويضيف أي Flow منشور.
- Telegram Stars: PaymentOrder عند migration `0009`، إنشاء فاتورة XTR، تحقق pre-checkout، idempotency، وتسليم بعد successful payment فقط.
- دليل عربي شامل للمالك يغطي التشغيل والإعداد والحدود والواجهة والدفع والتقييم والتشخيص.

### Automated/local gate — 2026-08-24

```text
pytest: 130 passed, 1 known warning
Ruff full repository gate: PASS
compileall: PASS
retrieval regression: 14/14 top-1
Alembic current/head: 0009 / PASS
isolated migration rehearsal: PASS
post-migration backup/isolated restore: PASS
Docker Compose config/build/non-root: PASS
health/ready/metrics auth: 200/200/401→200
```

### Live provider/Telegram gate — 2026-08-24

- Telegram/DeepSeek/Gemini preflight الحي: HTTP 200.
- ربط النموذج الرقم `4` بسؤال عدد المجموعات دون تكرار تحية أو Markdown خام؛ بقي ضمن REQUIRE_APPROVAL.
- تحليل مستند اصطناعي نجح دون إرسال للعميل، وNative Rich Message أُرسل حيًا ثم حُذف الاختبار المحدد.
- أنشئ رابط Telegram Stars XTR بنجاح دون طباعته أو تنفيذه ماليًا.
- لم تشغل عملية bot محلية ثانية؛ poller الإنتاج على New‑VPS بقي الوحيد.

### GitHub CI and New‑VPS candidate gate — 2026-08-24

- فُتح PR #9 عند commit `137d939e530e1af7acc2e69215d607eb5ec51f14`.
- نجح GitHub Actions run `32670663258` على Python 3.12 و3.13؛ تضمنت مهمة 3.12 بناء صورة الإنتاج.
- قبل النشر حُفظ backup واستعيد معزولًا عند `0008` بأعداد owners=1/conversations=2/messages=46، وحُفظت صور API/Bot القديمة وstash Dockerfile دون حذف.
- رُحلت New‑VPS إلى `0009` ونشرت صورة `1.0.0`. health/ready والـmetrics 401/200 وproduction preflight الحي كلها PASS.
- نجح على الخادم فهم `4` كسياق للعدد دون تحية متكررة أو Markdown، ونجح مسار المستند، وإنشاء رابط XTR غير مرسل دون معاملة مالية.
- backup ما بعد النشر استعيد معزولًا عند `0009`: owners=1/conversations=2/messages=46/payment_orders=0، ثم حُذفت قاعدة البروفة وحدها.
- api/bot يعملان بالمستخدم `secretary` مع restart=0، ومسح السجلات أعاد 0 أخطاء/Traceback/تعارض polling.
- نجح CI التوثيق النهائي run `32671236353`، ثم اندمج PR #9 بعد البوابة الحية وثُبت New‑VPS على merge SHA `db68fda` مع readiness عند `0009`.

## Smart Secretary Autonomy & Context — 2026-08-24

**Status: مرشح 1.1.0 مقبول ومنشور على New‑VPS عند كود `4773acc`، وبانتظار إجراء دمج مستقل إلى `main`.**

### Implemented

- فصل inherited/explicit conversation state بمخطط additive وزر «اتباع الوضع العام».
- taxonomy دلالية عامة للرسائل الاجتماعية وpre-sales والمعلومات والدعم والقرارات الحساسة.
- HIGH يعتمد على الفعل والسلطة المطلوبة، لا على مجرد ذكر السعر/الدفع/الاسترجاع/الخصم.
- no-grounding يسمح بالرد الاجتماعي أو سؤال توضيح محدود، ولا يسمح باختراع حقيقة تجارية.
- lifecycle-aware PostgreSQL reranking دون Vector DB أو نشاط hardcoded.
- adjacent-turn continuity للعدد/الاختيار/نتيجة troubleshooting/الإغلاق مع منع stale question وtopic shift.
- handoff/review summary خاص بالحالة، وbounded AiRun decision context دون نصوص محادثة أو prompts.
- eval dataset مستقلة تشمل لهجات عربية وإنجليزية، ambiguous/negative/sensitive controls.

### Final measured gates

```text
baseline offline eval: 30/53
after offline eval: 53/53
baseline live classifier eval: 0/12
after live classifier eval: 12/12
pytest: 135 passed, 1 known warning
M7 retrieval regression: 14/14
Ruff full / compileall: PASS
isolated PostgreSQL migration rehearsal: PASS at 0010
local Docker build/health/ready/non-root: PASS
GitHub Actions runs 32762296478 and 32768416850: PASS
New-VPS 1.1.0/0010 health/ready/metrics/preflight: PASS
pre/post migration backup isolated restore: PASS
Telegram Business UI scenarios 1–7: PASS
post-fix live copy regression: PASS
```

ظهر في أول pre-sales live run عيب نحوي عام: حذف المنقّي «أهلًا» وترك «بك،». أصلح commit `4773acc` المطابقة لتتعامل مع الحركات و`بك/بكم` وحدود الكلمات، ثم نجحت اختبارات الضبط وCI وإعادة الاختبار الحي. التفاصيل والأدلة المربوطة بـAiRun في `SMART_SECRETARY_LIVE_TEST_REPORT.md`.
