# Telegram AI Secretary

سكرتير ذكاء اصطناعي شخصي عام وقابل للتخصيص لحساب Telegram عبر **Telegram Business / Connected Business Bot الرسمي**. المشروع مبني ليخدم أي نشاط أو استخدام يحدده المالك دون hardcoding لخدمات أو أسعار أو مجالات بعينها.

## الحالة الحالية

**M10 — Advanced Automation مكتملة ومندمجة في `main`** عبر PR #6 بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22`. الإصدار المرجعي الحالي هو **0.10.0**.

أغلقت M10 بعد نجاح البوابات المحلية والحية وPostgreSQL/Docker وGitHub Actions. نجح CI النهائي بعد تحديث دليل الإغلاق في run `32547007628` على Python 3.12 و3.13، ثم تم الدمج إلى `main`.

بهذا تعتبر الخطة الأساسية المنفذة من M0 حتى M10 **مغلقة وظيفيًا ضمن نطاقها الحالي**. لا توجد مرحلة M11 نشطة أو مطلوبة لإكمال النطاق الحالي؛ أي M11 مستقبلية تكون توسعة جديدة تُعرّف صراحة بعد وجود حاجة مقاسة أو متطلب جديد.

آخر بوابة إغلاق موثقة لـM10:

```text
retrieval evaluation: 14/14 top-1
Ruff full gate: PASS
compileall: PASS
pytest: 106 passed, 1 warning
PostgreSQL head: 0008
isolated migration rehearsal: PASS
Docker build/non-root smoke: PASS
backup/restore rehearsal: PASS
GitHub Actions final CI: 32547007628 PASS (Python 3.12/3.13)
```

## ما يعمل الآن

- Telegram Business connection الرسمي عبر aiogram 3.
- استقبال الرسائل وتخزين contacts/conversations/messages مع idempotency.
- debounce وconversation revision لمنع الردود القديمة.
- DeepSeek للنص/reasoning والرد النهائي.
- Gemini Vision لتحليل الصور قبل DeepSeek.
- Owner approval cards مع Send / Edit / Sources / Learn / Reject.
- فحص `can_reply` قبل approved send وحماية من الإرسال المكرر/غير المؤكد.
- BusinessProfile + Knowledge + ContactMemory + ResponsePolicy.
- PUBLIC / INTERNAL / PRIVATE knowledge boundaries.
- إدارة المعرفة والذاكرة والقواعد من Telegram.
- Bulk Knowledge: لصق نص طويل أو TXT/MD/CSV/JSON/YAML ثم preview واعتماد جماعي.
- Telegram native Rich Messages عبر MessageEntity، بدون raw HTML/Markdown من النموذج.
- Dynamic Menu/Button Engine مع `AI_ONLY / CUSTOM_MENU / HYBRID`.
- أزرار 🌐 دائمة و🎯 سياقية تظهر حسب موضوع الرسالة/الرد.
- أزرار رد ثابت، URL، وHandoff للمتابعة البشرية.
- retry محدود لرسائل الإدارة عند Telegram network errors، مع إبقاء customer sends fail-closed.
- استرجاع عربي/إنجليزي مقاس وقابل للتفسير مع استبعاد PRIVATE والمنتهي.
- كشف تعارض الحقائق ورفعها لموافقة المالك بدل الاختيار الصامت.
- دفعات معرفة قابلة للتراجع، منع استيراد المصدر نفسه، ونسخ تاريخية عند التعديل.
- مصدر approval محفوظ وقت الإنشاء وقابل للتدقيق بعد تغير المعرفة.
- رسائل مهنية لا تعرض أكواد السياسة أو أسماء المزودين للمستخدم.
- اقتراح ذاكرة من المحادثة لا يُحفظ قبل اعتماد المالك، مع provenance/confidence/retention.
- تنقية محلية للأسرار والبيانات الحساسة، وتحرير/تصدير/مسح ذاكرة من Telegram.
- تقييمات 1–5 بتكرار قابل للضبط ولوحة رضا للمالك، دون تعلم تلقائي.
- health/readiness حقيقيان، metrics محمية، structured JSON logs وtrace IDs.
- AiRun وaudit metadata منقاة للأداء والقرارات دون نسخ نص المحادثة.
- Docker/systemd production packaging مع migration gate ومستخدم غير جذر.
- PostgreSQL backup/checksum/retention وrestore rehearsal معزولة.
- production preflight وتدوير PostgreSQL/metrics secrets دون عرضها.
- Flow Engine فعلي: مسودة ومعاينة ونشر، جلسات مستقلة ونسخة ثابتة، وبدء بالنص الحر أو زر ديناميكي.
- Custom Intents قابلة للإنشاء والتعديل والتعطيل والحذف بعتبة يحددها المالك، دون تجاوز سياسة الأمان.
- تذكيرات owner-only بمنطقة زمنية قابلة للضبط وتسليم one-shot غير مكرر.
- AUTO فعلي للردود LOW-risk عالية الثقة والمبنية على PUBLIC، مع idempotency/audit وفشل مغلق عند عدم يقين الإرسال.

## Quick Start — Windows

```powershell
cd D:\Desktop\telegram_ai_secretary_clean
.\.venv\Scripts\Activate.ps1

docker compose up -d postgres
alembic upgrade head
pytest
python -m app.telegram.run
```

إذا كانت البيئة غير موجودة بعد:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

املأ `.env` محليًا فقط. لا ترفع Tokens أو API keys إلى Git.

## AI Routing

```text
Text:
Telegram → conversation/brain context → DeepSeek → local safety → approval/auto → reply

Image:
Telegram image → Gemini Vision → structured evidence → DeepSeek → local safety → approval/reply
```

## Knowledge Model

المعرفة هي مصدر حقائق النشاط، وليست معرفة النموذج العامة. `PUBLIC` يمكن قوله للعميل، `INTERNAL` يوجه السكرتير بدون كشف التعليمات الداخلية، و`PRIVATE` لا يدخل LLM أصلًا. ذاكرة الشخص منفصلة ولا تستخدم كإثبات لسعر أو توفر حالي.

## Documentation

ابدأ من [`docs/README.md`](docs/README.md). أهم الملفات:

- [`docs/MASTER_SPEC.md`](docs/MASTER_SPEC.md) — المرجع التأسيسي.
- [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md) — ذاكرة المشروع الحالية.
- [`docs/CONSTANTS.md`](docs/CONSTANTS.md) — الثوابت.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — المعمارية.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — القرارات.
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — التقدم.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — المراحل القادمة.
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — التشغيل.
- [`docs/SECURITY.md`](docs/SECURITY.md) — الأمان.
- [`docs/AI_BEHAVIOR.md`](docs/AI_BEHAVIOR.md) — سلوك AI.
- [`docs/KNOWLEDGE_AND_MEMORY.md`](docs/KNOWLEDGE_AND_MEMORY.md) — المعرفة والذاكرة.
- [`docs/TELEGRAM_UI.md`](docs/TELEGRAM_UI.md) — Rich والأزرار.
- [`docs/ACCEPTANCE_CRITERIA.md`](docs/ACCEPTANCE_CRITERIA.md) — معايير القبول.
- [`docs/M6_SECRETARY_LEARNING.md`](docs/M6_SECRETARY_LEARNING.md) — تفاصيل M6.
- [`docs/M7_RETRIEVAL_QUALITY.md`](docs/M7_RETRIEVAL_QUALITY.md) — تفاصيل M7.
- [`docs/M8_MEMORY_INTELLIGENCE.md`](docs/M8_MEMORY_INTELLIGENCE.md) — تفاصيل M8.
- [`docs/M9_PRODUCTION_OPERATIONS.md`](docs/M9_PRODUCTION_OPERATIONS.md) — تفاصيل وإغلاق M9.
- [`docs/M10_ADVANCED_AUTOMATION.md`](docs/M10_ADVANCED_AUTOMATION.md) — تفاصيل وإغلاق M10.

## قاعدة المشروع

لا تعِد كتابة Core لنشاط جديد. إذا تغير النشاط أو الأسعار أو الخدمات أو طريقة العرض، عدّل البيانات/المعرفة/القواعد/القوائم. أي تغيير معماري جوهري يسجل في `docs/DECISIONS.md`.