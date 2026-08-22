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

**Status: التنفيذ والاختبار الحي وCI مكتملة على `codex/m7-retrieval-quality`؛ دمج PR #3 قيد الإغلاق.**

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

لا تسجل المرحلة مندمجة حتى تكتمل مراجعة ودمج PR #3.

## Documentation hardening — 2026-08-22

Documentation is being promoted to a first-class project artifact. Added/updated:

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
