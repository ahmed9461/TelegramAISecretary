# Telegram AI Secretary

سكرتير ذكاء اصطناعي شخصي عام وقابل للتخصيص لحساب Telegram عبر **Telegram Business / Connected Business Bot الرسمي**. المشروع مبني ليخدم أي نشاط أو استخدام يحدده المالك دون hardcoding لخدمات أو أسعار أو مجالات بعينها.

## الحالة الحالية

التطوير الحالي على **M7 — Retrieval Quality & Knowledge Operations** في الفرع `codex/m7-retrieval-quality`. اندمج M6 في `main` عبر PR #2، واجتازت M7 بوابتها الحية؛ CI البعيد والمراجعة قيد الإغلاق قبل الدمج.

آخر gate محلي موثق لـM7:

```text
retrieval evaluation: 14/14 top-1
Ruff correctness gate: PASS
compileall: PASS
pytest: 72 passed, 1 warning
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

## قاعدة المشروع

لا تعِد كتابة Core لنشاط جديد. إذا تغير النشاط أو الأسعار أو الخدمات أو طريقة العرض، عدّل البيانات/المعرفة/القواعد/القوائم. أي تغيير معماري جوهري يسجل في `docs/DECISIONS.md`.
