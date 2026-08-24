# Documentation Index

ابدأ من هنا عند تسليم المشروع إلى مبرمج أو AI جديد.

## الحالة المرجعية الحالية

الخطة الأساسية M0–M10 وV1 مكتملة ومندمجة في `main` عبر PR #9 بالـSHA `db68fda8046ff90a2958e9f0c33de1e6ba8fb5b2`، والمرجع المدمج `1.0.0/0009`. نطاق **Smart Secretary Autonomy & Context** نفذ المرشح `1.1.0/0010` بتمييز inherited/explicit state وintent/risk taxonomy واستمرارية واسترجاع أفضل؛ اجتاز الاختبارات وCI وبوابة Telegram Business الحية ويعمل على New‑VPS عند كود `4773accf0e508906a0d015cfb2467f6864f0794a`، ولم يدمج بعد في `main`. لا توجد M11 عامة مفتوحة؛ هذا نطاق جودة مستقل محدد بملف `CODEX_SMART_SECRETARY_AUTONOMY_AND_CONTEXT_PROMPT.md`.

## القراءة بالترتيب

1. `MASTER_SPEC.md` — المواصفات التأسيسية والمبادئ غير القابلة للتفاوض.
2. `PROJECT_MEMORY.md` — أين وصل المشروع الآن وما الذي تم فعليًا.
3. `CONSTANTS.md` — الثوابت التي لا تتغير ضمن تعديل عادي.
4. `ARCHITECTURE.md` — طبقات المشروع ومسارات الرسائل.
5. `DECISIONS.md` — القرارات المعمارية المعتمدة.
6. `PROGRESS.md` — سجل الإنجاز حسب المراحل.
7. `ROADMAP.md` — ما هو مخطط بعد المرحلة الحالية وما ليس منفذًا بعد.
8. `RUNBOOK.md` — التثبيت، الاختبار، التشغيل والتعامل مع الأعطال.
9. `DATA_MODEL.md` — معنى الجداول والكيانات.
10. `SECURITY.md` — trust boundaries والأسرار والإرسال الآمن.
11. `AI_BEHAVIOR.md` — كيف يستخدم DeepSeek/Gemini والسياق والـgrounding.
12. `KNOWLEDGE_AND_MEMORY.md` — الفرق بين معرفة النشاط وذاكرة الأشخاص.
13. `TELEGRAM_UI.md` — Owner UI وRich Messages والأزرار الدائمة/السياقية.
14. `ACCEPTANCE_CRITERIA.md` — متى نعتبر الميزة جاهزة فعلًا.
15. `DEVELOPER_HANDOFF.md` — تعليمات تسليم المشروع لمبرمج/AI جديد.
16. `M5_SECRETARY_BRAIN.md` — تفاصيل M5.
17. `M6_SECRETARY_LEARNING.md` — تفاصيل وإغلاق M6.
18. `M7_RETRIEVAL_QUALITY.md` — تفاصيل وإغلاق M7.
19. `M8_MEMORY_INTELLIGENCE.md` — تفاصيل M8 والبوابة الحية.
20. `M9_PRODUCTION_OPERATIONS.md` — التشغيل والمراقبة والنشر والنسخ الاحتياطي وبوابة M9.
21. `M10_ADVANCED_AUTOMATION.md` — التدفقات والنوايا والتذكيرات وAUTO وإغلاق M10.
22. `V1_FINAL_ACCEPTANCE.md` — تدقيق نطاق V1 والفجوات والبوابات النهائية.
23. `USER_MANUAL_AR.md` — كتيب المالك الشامل لإعداد السكرتير واستخدامه اليومي.
24. `THIRD_PARTY_INSPIRATION.md` — المصادر المفتوحة التي أخذنا منها patterns فقط.

## قاعدة التحديث

أي تعديل كبير يجب أن يحدث الملف المتخصص المناسب. إذا غير القرار بنية النظام: حدث `DECISIONS.md`. إذا غير طريقة التشغيل: حدث `RUNBOOK.md`. إذا أغلق milestone أو فتح التالية: حدث `PROGRESS.md`, `ROADMAP.md`, و`PROJECT_MEMORY.md`.

لا تعتمد على محادثة خارج المستودع كذاكرة وحيدة للمشروع.
