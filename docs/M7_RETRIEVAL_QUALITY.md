# M7 — Retrieval Quality & Knowledge Operations

## الهدف

رفع جودة الاسترجاع وقابلية تدقيق المعرفة من دون إدخال vector database أو تعلم صامت، مع الحفاظ على حدود PUBLIC / INTERNAL / PRIVATE.

## التنفيذ

- normalization عربي/إنجليزي deterministic مع وزن للمحتوى والعنوان والوسوم ونوع المعلومة.
- eval dataset قابلة لإعادة التشغيل من `evals/m7_retrieval_cases.json`.
- استبعاد PRIVATE والمعرفة خارج فترة الصلاحية.
- كشف التعارض بين الحقائق الفعالة ذات النوع والعنوان المتطابقين.
- `KnowledgeBatch` لكل bulk commit مع بصمة للمصدر ومنع الاستيراد المطابق والتراجع الكامل.
- versioning append-oriented عند تعديل عنوان/محتوى المعرفة.
- approval provenance snapshot في `context_json` للمصدر والنسخة والصلاحية والتعارض.
- واجهة دفعات ونسخ ومصادر بصياغة مهنية لا تعرض أكواد التنفيذ.
- copy guard يمنع عبارة «كيف أقدر أساعدك اليوم؟» والرموز الداخلية في الرد الظاهر.

## حدود الأمان

- PRIVATE لا يدخل retrieval أو LLM.
- INTERNAL لا يتحول إلى حقيقة معلنة للعميل.
- التعارض يجبر مراجعة المالك ولا يحسمه النموذج.
- rollback وsupersede يحفظان التاريخ بدل الحذف الصامت.
- snapshot الموافقة لا يكرر محتوى المعرفة، ويظل ضمن مالك ومحادثة الموافقة.
- النشاط والخدمات والعبارات السياقية تأتي من BusinessProfile/Knowledge وليست hardcoded.

## قاعدة البيانات

- `0004_m7_knowledge_operations`: knowledge batches وحقول النسخة/المصدر والبصمة.
- `0005_m7_approval_provenance`: `approvals.context_json`.

## دليل البوابة الآلية — 2026-08-22

```text
retrieval evaluation: 14/14 top-1
pytest: 72 passed, 1 warning
compileall: PASS
Ruff correctness gate: PASS
PostgreSQL: 0005 (head)
isolated PostgreSQL upgrade/downgrade/re-upgrade: PASS
```

التحذير الوحيد المعروف متعلق بتقادم Starlette TestClient/httpx ولا يمنع التشغيل.

بروفة الترحيلات المعزولة كشفت أولًا خللًا في downgrade `0004` عند افتراض اسم قيد FK. أصلح المسار ليقرأ اسم القيد الفعلي، ثم نجحت ترقية قاعدة فارغة إلى `0005`، والعودة إلى base، والترقية ثانية إلى `0005`. أزيلت قاعدة الاختبار المؤقتة بعد البروفة.

## بوابة Telegram الحية — 2026-08-22

- import واعتماد دفعة PUBLIC: PASS.
- duplicate source block: PASS.
- conflict detection وعرض المصدر/النسخة/التعارض: PASS.
- provenance snapshot بعد rollback: PASS.
- رفض المتعارض ثم إرسال الصحيح مرة واحدة: PASS.
- إنشاء النسخة 2 من Telegram: PASS.
- تحية «كيف أقدر أساعدك؟» وصياغات بلا أكواد داخلية: PASS.
- rollback والتنظيف المحدد مع بقاء البيانات السابقة: PASS.

كشف الاختبار أن معاينة bulk وتفاصيل الدفعة كانتا تعرضان type/visibility الخام. أصلحت الصياغة، وأعيد اختبار معاينة النوع حيًا فظهرت «خدمة» بدل `[SERVICE]`.

## بوابة الإغلاق

تبقى CI على Python 3.12/3.13 والمراجعة قبل الدمج إلى `main`.
