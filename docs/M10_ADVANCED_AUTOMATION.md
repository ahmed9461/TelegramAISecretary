# M10 — Advanced Automation

## الحالة

التنفيذ والبوابات المحلية وPostgreSQL/Docker وTelegram الحية مكتملة على `codex/m10-advanced-automation`. فُتح PR #6، ونجح CI التنفيذي على Python 3.12/3.13 في run `32546910568`. بقي CI لتحديث دليل الإغلاق ثم الدمج فقط بعد نجاحه.

## النطاق المنفذ

- Flow Engine فعلي متصل برسائل Telegram Business، وليس runtime منفصلًا للاختبار فقط.
- إنشاء التدفق من واجهة عربية: اسم ووصف وعبارات بدء وأسئلة ورسالة إكمال، ثم مسودة ومعاينة ونشر صريح.
- Custom Intents قابلة للإنشاء والتعديل والتشغيل والإيقاف والحذف، بعتبة ثقة يحددها المالك وربط اختياري بتدفق منشور.
- جلسة Flow مستقلة لكل محادثة تحفظ نسخة definition كاملة؛ تعديل/نشر نسخة أحدث لا يغير جلسة جارية.
- بدء التدفق من النص الحر أو زر ديناميكي `START_FLOW` عبر Telegram Adapter.
- تذكيرات المالك one-shot بمنطقة زمنية قابلة للتعديل، وclaim مؤقت يمنع التسليم المتوازي ويسترد التذكير تلقائيًا بعد انهيار العامل.
- مسار AUTO الحقيقي يرسل الرد الآمن مرة واحدة عبر approval ledger نفسه، ويعيد فحص صلاحية Telegram لحظة الإرسال، ويحفظ outgoing/audit باسم `SYSTEM`.
- شاشة `/start` تقرأ الوضع الحقيقي بدل عرض «موافقة» كنص ثابت.

## حدود الأمان

- النية المخصصة Routing signal فقط؛ لا تتجاوز Risk/State/Knowledge/Policy.
- لا تنشأ نية أو تدفق ولا ينشران بصمت. النشر زر صريح بعد المعاينة.
- التدفقات المنشورة تنفذ نصوص المالك المحددة ولا تحول المعرفة PRIVATE إلى ردود.
- AUTO يتطلب حالة `AI_AUTO` ومخاطرة LOW وثقة كافية، ويحتاج PUBLIC grounding لأي حقيقة نشاط غير التحية/طلب المالك.
- INTERNAL لا يكفي للإرسال التلقائي وPRIVATE لا يدخل LLM.
- التذكيرات للمالك فقط في M10؛ لا توجد متابعة صامتة أو رسائل مجدولة للعملاء.

## البوابة الآلية والمحلية — 2026-08-22

```text
pytest: 106 passed, 1 known warning
Ruff full repository gate: PASS
compileall: PASS
PostgreSQL head/check: 0008 / PASS
isolated PostgreSQL upgrade → downgrade base → upgrade: PASS at 0008
Docker Compose config: PASS
Docker image 0.10.0 build: PASS
Docker non-root smoke: PASS
```

يغطي اختبار M10 المتكامل إرسال AUTO مرة واحدة، وإيقافه عند سحب صلاحية Telegram، وحفظ outgoing/audit. ويغطي كذلك عزل المالك/المحادثة، إلغاء Flow عند الاستلام البشري، نسخة Flow الثابتة، threshold/disable للنوايا، lease/retry للتذكير، ومصفوفة أمان AUTO.

## البوابة الحية — 2026-08-22

- أُخذ backup عند 0007 قبل الترحيل، ثم رُحلت قاعدة المشروع additive إلى `0008` ونجح Alembic check.
- أُخذ backup جديد عند `0008` واستعيد في قاعدة معزولة: owners=1، conversations=4، messages=37، ثم حذفت قاعدة البروفة.
- صورة 0.10.0 عملت بالمستخدم `secretary`; health=200، وready=503 على قاعدة smoke غير مرحّلة.
- API الحية على قاعدة المشروع: health=200/version 0.10.0، ready=200 عند 0008، metrics=401 دون token و200 معه.
- preflight الحي أعاد HTTP 200 لـTelegram وDeepSeek وGemini مع إعدادات منقاة.
- من واجهة المالك: أُنشئ Flow تجريبي كمسودة، عُوين، نُشر صراحة، ثم بدأه العميل بالنص الحر وجمع إجابتين وأكمله.
- ملخص المالك عرض نصوص الأسئلة العربية بدل مفاتيح `question_*`.
- ضُبطت المنطقة الزمنية حيًا وأُنشئ تذكير مستقبلي؛ وصل مرة واحدة في موعده ثم أصبح غير فعال.
- في الحالة AUTO الأصلية، أرسلت تحية حية مباشرة مرة واحدة؛ ظهر للعميل «كيف أقدر أساعدك؟» بلا «اليوم» وبلا أكواد، وسجل AiRun/Approval/Audit القرار قبل تنظيفه.
- بعد التحقق حُذفت فقط عناصر الاختبار: 8 رسائل DB اصطناعية، Flow/Intent/Session/Schedule التجريبية وtelemetry/audit المرتبطة. عادت القاعدة إلى messages=37، conversation revision=17، و0 عناصر أتمتة اصطناعية.

## بوابة الدمج

- [x] التنفيذ.
- [x] 106 tests + Ruff + compileall + retrieval 14/14.
- [x] migration rehearsal + live migration 0008.
- [x] backup/restore 0008.
- [x] Docker non-root/API gates.
- [x] Flow/Intent/Reminder/AUTO Telegram live gate.
- [x] synthetic cleanup + single poller.
- [x] GitHub CI Python 3.12/3.13 للـcommit التنفيذي في run `32546910568`.
- [ ] merge PR بعد نجاح CI فقط.
