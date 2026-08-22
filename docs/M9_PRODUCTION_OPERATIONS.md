# M9 — Production Operations

## الحالة

التنفيذ والبوابة المحلية والتشغيلية/Telegram الحية مكتملة في `codex/m9-production-operations`. فُتح PR #5 ونجح CI الأول على Python 3.12/3.13 في run `32544367834`. بقي CI توثيق الإصدار ثم الدمج بعد نجاحه.

## نطاق المرحلة

M9 لا تغير هوية السكرتير أو سياسة PUBLIC/INTERNAL/PRIVATE ولا تضيف تعلمًا. تضيف طبقة تشغيل قابلة للملاحظة والاستعادة:

- liveness/readiness بعقدين منفصلين.
- structured logs وtrace IDs مع redaction.
- AiRun وmetrics وaudit بلا نسخ محتوى المحادثات.
- Docker/systemd production packaging.
- PostgreSQL backup/restore rehearsal.
- production preflight وsecret rotation.

## التنفيذ

### الصحة والقياسات

- `/health`: استجابة خفيفة تشمل الإصدار والبيئة فقط.
- `/ready`: DB query + تطابق `alembic_version` مع رأس المصدر + متطلبات إعداد Telegram/AI.
- `/metrics`: Prometheus aggregates ضمن `METRICS_WINDOW_DAYS`؛ Bearer token عند ضبط `METRICS_TOKEN`.
- HTTP middleware يولد/يمرر `x-trace-id` ويكتبه كسجل منظم.

### AiRun وAudit

Migration `0007` تضيف `ai_runs`. المساران النصي والبصري يسجلان النتيجة الناجحة/الفاشلة/المهملة، الزمن، القرار، الثقة، token usage ومراجع المعرفة. لا يخزن AiRun نص المستخدم أو candidate reply.

Audit يغطي الردود المرسلة/المرفوضة وحذف المعرفة/السياسات/الأزرار ومسح الذاكرة والتراجع عن الدفعات. metadata تمنع content/text/message/token/password/secret/api_key.

### التغليف والنشر

- Dockerfile مبني على Python 3.12 ويعمل بالمستخدم غير الجذر `secretary`.
- Compose ثابت الاسم ويرتب `postgres → migrate → api/bot` مع localhost ports وhealth checks.
- systemd units منفصلة للهجرة وAPI والبوت وbackup timer وتطبق hardening.

### النسخ والاستعادة والأسرار

- backup أداة custom-format تكتب SHA-256 manifest وتزيل النسخ المسماة فقط بعد retention.
- restore rehearsal تنشئ قاعدة `secretary_restore_<random>`، تستعيد وتتحقق من revision/counts ثم تحذفها في `finally`.
- preflight يرفض production غير الآمن ويتحقق اختياريًا من Telegram/DeepSeek/Gemini live.
- secret rotation الداخلية تغير PostgreSQL/metrics ذريًا وتتحقق من الاتصال دون طباعة القيمة.

## أدلة البوابة — 2026-08-22

### آلي ومحلي

```text
full pytest after final docs: 92 passed, 1 known warning
M9 focused after readiness/rotation metrics hardening: 9 passed
Ruff full repository gate: PASS
compileall: PASS
retrieval regression: 14/14 top-1
Alembic head/check: 0007 / PASS
isolated upgrade → downgrade base → upgrade: PASS
docker compose config: PASS
Docker build: PASS
```

التحذير الوحيد المعروف هو Starlette TestClient/httpx، ولا يمنع البوابة.

### تشغيل حي

- صورة 0.9.0 عملت كمستخدم `uid=999(secretary)`؛ health=200 وready=503 على قاعدة smoke غير مرحّلة، وهو السلوك الصحيح.
- API على القاعدة الحية: health=200، ready=200، metrics بلا token=401 ومع token=200 وtrace header.
- Telegram/DeepSeek/Gemini preflight أعاد HTTP 200، والقاعدة طابقت `0007`.
- backup حي استعيد إلى قاعدة معزولة عند `0007` مع owners=1, conversations=4, messages=37، ثم حذفت قاعدة البروفة.
- دُورت أسرار PostgreSQL/metrics، ثم أعيد البوت كشجرة poller واحدة دون conflict أو DB error.
- رسالة Business اصطناعية أنشأت AiRun `SUCCESS` مع latency=7785ms و3141 token، وبطاقة عربية مهنية مرتبطة بالنشاط.
- رفض المالك أنشأ AuditLog. بعد القياس حذفت الصفوف الاصطناعية المحددة وأعيد revision؛ بقيت المعرفة الحقيقية الفعالة والرسائل السابقة دون تغيير.

## بوابة الدمج

- [x] التنفيذ.
- [x] tests/local gates.
- [x] Docker/systemd/config gates.
- [x] database migration rehearsal.
- [x] backup/restore rehearsal.
- [x] provider/API/Telegram live gate.
- [x] synthetic cleanup + single poller.
- [x] final full suite after docs: 92 passed.
- [x] GitHub CI Python 3.12/3.13 في run `32544367834` للـcommit التنفيذي.
- [ ] GitHub CI بعد commit توثيق بوابة الإصدار.
- [ ] merge PR بعد CI فقط.
