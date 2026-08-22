# Architecture — Telegram AI Secretary

## الهدف

الحفاظ على Core عام وقابل للتبديل، مع عزل Telegram والـAI providers عن منطق المعرفة والذاكرة والقرار.

## الطبقات

```text
Channel Adapter
  app/telegram/*
        ↓
Conversation & Ingestion
  app/conversations/*
        ↓
Brain Context
  app/brain/*
  app/knowledge/*
  app/memory/*
  app/interface/*
  app/intents/*
  app/flows/*
        ↓
AI Providers
  app/ai/*
  app/vision/*
        ↓
Deterministic Safety / Approval
  app/security/*
  app/approvals/*
        ↓
Persistence
  app/db/* + Alembic
```

`app/main.py` يبقى مدخل FastAPI الصحي/التشغيلي، بينما `app/telegram/run.py` هو مدخل polling الخاص بـTelegram.

## مسار رسالة نصية

1. يصل `business_message` من Telegram.
2. يتحقق Adapter من Business Connection ويستعيدها عند الحاجة.
3. تسجل الرسالة idempotently في Contact/Conversation/Message.
4. ترتفع conversation revision.
5. debounce يجمع الرسائل المتتابعة بسرعة ويمنع العمل القديم.
6. يبنى سياق AI من recent messages + profile + knowledge + memory + policies.
7. DeepSeek يصنف intent/risk/confidence ويولد candidate reply عندما تسمح السياسة.
8. local policy تحسم `AUTO_REPLY / REQUIRE_APPROVAL / ESCALATE / SILENT / ASK_FOLLOWUP`.
9. في APPROVAL تحفظ المسودة مع revision وTTL وتظهر بطاقة للمالك.
10. قبل الإرسال يعاد فحص اتصال Telegram و`can_reply`.
11. الرد المرسل يسجل في history.

## مسار صورة

1. Telegram Adapter يحمل الصورة في الذاكرة مع حد للحجم.
2. Gemini Vision يستخرج summary/text/evidence بصورة منظمة.
3. المخرجات المرئية تعامل كبيانات غير موثوقة من جهة المستخدم.
4. DeepSeek يستخدم الأدلة المرئية مع بقية السياق.
5. نفس local safety/approval path يطبق قبل الإرسال.

## عقل السكرتير

BusinessProfile يحدد الهوية والنبرة والتعليمات العامة. KnowledgeItem هو مصدر الحقائق الخاصة بالنشاط. ContactMemory يخصص السياق لكل شخص دون خلط. ResponsePolicy يضيف قواعد مالك عامة أو مقيدة. لا يحق لأي طبقة من هذه الطبقات تعطيل قواعد الأمان الأساسية.

## Knowledge Retrieval

المرحلة الحالية تستخدم PostgreSQL retrieval deterministic على KnowledgeItem مع normalization عربي/إنجليزي ووزن قابل للتفسير. `PRIVATE` والمنتهي زمنيًا مستبعدان، و`PUBLIC` و`INTERNAL` قد يدخلان السياق مع تمييز visibility. التعارض بين حقائق فعالة يرفع إشارة إلى local policy. الواجهة قابلة للاستبدال لاحقًا بإضافة embeddings/vector search دون تغيير Telegram Adapter، لكن ذلك يحتاج فشلًا مقاسًا أولًا.

## Bulk Ingestion

`app/knowledge/bulk.py` يستقبل مصدرًا كبيرًا، يقسمه، يطلب من extractor إنتاج records منظمة، يطبع/ينظف النتائج ويزيل التكرار، ثم يحفظها فقط بعد معاينة وموافقة المالك من `bulk_knowledge_ui.py`. كل commit في M7 يرتبط بـKnowledgeBatch وبصمة محتوى، ويمكن التراجع عنه دون حذف التاريخ.

## Dynamic Interface

MenuProfile + MenuItem يمثلان واجهة قابلة للبيانات. `app/interface/service.py` يحمل القائمة المناسبة. visibility rules تحدد زرًا دائمًا أو سياقيًا. `app/telegram/keyboards.py` يحول التعريف العام إلى InlineKeyboardMarkup. Adapter هو المكان الوحيد الذي يربط هذه البنية بـaiogram.

## Rich Text

النموذج ينتج نصًا نظيفًا بدون HTML/Markdown خام. `app/telegram/rich_text.py` يحول البنية النصية المحدودة إلى Telegram MessageEntity. ثم يرسل Adapter النص + entities.

## حالات المحادثة

الحالات الأساسية:

- `AI_AUTO`
- `AI_APPROVAL`
- `OBSERVE_ONLY`
- `HUMAN_TAKEOVER`
- `ESCALATED`
- `PAUSED`
- `EXCLUDED`

الوضع العالمي `AUTO / APPROVAL / OBSERVE / OFF` لا يستبدل حالة المحادثة؛ بل يعمل كسقف أمان.

## حدود المسؤولية

Telegram-specific types لا تدخل Core. AI لا يقرر وحده الإرسال. قاعدة البيانات لا تحتوي أسرار provider. PRIVATE لا يغادر طبقة البيانات إلى LLM. retry الشبكي لرسائل العميل لا يتم عميانيًا عند حالة إرسال غير مؤكدة.
