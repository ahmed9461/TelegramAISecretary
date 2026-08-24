# Acceptance Criteria

هذه المعايير تمنع إعلان ميزة "مكتملة" لأنها موجودة شكليًا فقط.

## معيار عام لأي ميزة

الميزة تعتبر جاهزة فقط عندما يكون لها مسار فعلي في الكود، ownership/safety checks المناسبة، اختبار آلي للحالة الأساسية والحالات الخطرة المعقولة، وتوثيق محدث إذا غيرت سلوك التشغيل أو المعمارية.

## Telegram Business

- استقبال `business_message` الفعلي.
- persistence بدون تكرار.
- استعادة connection عند فقد update إن أمكن.
- عدم معالجة connection لمالك غير configured owner.
- approved send يعيد فحص `can_reply`.
- أي إرسال غير مؤكد للعميل لا يعاد تلقائيًا عميانيًا.

## Approval

- candidate مربوط بـconversation revision.
- TTL مطبق.
- رسالة/تعديل/حذف أحدث يبطل candidate القديم.
- رد يدوي من المالك يبطل draft القديم.
- الضغط المكرر لا يرسل مرتين.
- Send/Reject/Edit تعمل من Telegram owner UI.

## Brain / Knowledge

- BusinessProfile يدخل AI context.
- relevant knowledge يدخل context.
- PRIVATE لا يدخل LLM.
- INTERNAL لا يكشف كسياسة داخلية.
- unknown business-specific fact لا يخترع.
- source provenance قابل للمراجعة من approval UI.
- المعرفة المنتهية لا تدخل الاسترجاع.
- التعارض الفعال لا يختار بصمت ويجبر مراجعة المالك.
- تعديل المعرفة ينشئ نسخة جديدة ولا يمحو السابقة.
- approval يحتفظ بمصادره وقت الإنشاء حتى بعد تغير المعرفة.

## Contact Memory

- ذاكرة كل شخص منفصلة.
- `private_notes` لا تدخل AI.
- `share_with_ai` يوقف مشاركة الذاكرة.
- يمكن للمالك مراجعة/تعديل/مسح الذاكرة.
- memory لا تعتبر grounding كافيًا لسعر أو توفر حالي.

## Bulk Knowledge

- يقبل النص الطويل والامتدادات المعلنة فقط.
- يحترم حد الحجم/الأحرف.
- source content لا ينفذ كتعليمات.
- extractor لا يكمل معلومات ناقصة من معرفته.
- preview قبل commit.
- cancel لا يحفظ العناصر.
- duplicate normalization مطبق.
- visibility المختارة تطبق على جميع العناصر المعتمدة.
- إعادة المصدر نفسه لا تنشئ دفعة وعناصر مكررة.
- يمكن مراجعة دفعة كاملة والتراجع عنها دون حذف سجلها.

## Retrieval Quality

- توجد eval dataset ثابتة تتضمن أسعارًا وسياسات وFAQ وخدمات وسؤالًا بلا مصدر.
- نتيجة top-1 قابلة لإعادة التشغيل من `scripts/evaluate_retrieval.py`.
- normalization العربي يتعامل مع التشكيل واختلافات الهمزة الشائعة.
- PRIVATE والمنتهي زمنيًا مستبعدان.
- لا تضاف vector infrastructure قبل فشل مقاس يبررها.

## Rich Messages

- لا يعتمد على raw HTML/Markdown من LLM.
- Telegram entities offsets صحيحة مع Unicode/emoji.
- عدم وجود rich pattern لا يفسد النص.
- إرسال Business message يتم بالنص + entities عبر Adapter.

## Dynamic Buttons

- تعريف الأزرار في DB وليس hardcoded لخدمة محددة.
- `AI_ONLY` لا يرفق قائمة العميل.
- `HYBRID` يسمح بالأزرار مع رد AI.
- URL action ينتج URL button فعليًا.
- contextual button لا يظهر في سياق غير مطابق.
- contextual matching deterministic وقابل للاختبار.
- زر HANDOFF ينقل الحالة إلى HUMAN_TAKEOVER ويبلغ المالك.

## Network Resilience

- Telegram network error في بطاقة المالك يمكن أن يعاد بمحاولات محدودة.
- retry العام لا يشمل customer send غير المؤكد.
- فشل retry النهائي يظهر في log ولا يؤدي إلى loop لا نهائي.

## Security

- owner-only لكل admin actions.
- secrets خارج Git.
- prompt injection boundaries موجودة للنص والصورة والملف.
- PRIVATE وowner-only notes لا تسرب.
- AUTO لا يتجاوز حالة محادثة أكثر تشددًا.

## Verification Gate قبل الدمج

الحد الأدنى قبل دمج milestone إلى `main`:

```text
ruff correctness gate: PASS
python -m compileall -q app tests: PASS
pytest: PASS
CI Python 3.12: PASS
CI Python 3.13: PASS
live test للميزات التي تعتمد على Telegram الحقيقي: PASS
```

لا يسجل عدد الاختبارات في docs إلا من output فعلي.

## نتيجة gate المحلي لـM6 — 2026-08-22

- `pytest`: 60 passed, 1 warning.
- Ruff correctness gate و`compileall`: PASS.
- Telegram Business live: Bulk cancel/commit، Sources، Native Rich، contextual keyword match/non-match، وintent-only match بعد approval، وتنفيذ الأزرار: PASS.
- الرد المطابق ظهر مرة واحدة وسجلت الموافقة معرف إرسال واحدًا.
- Network fault injection: owner retry محدود وcustomer uncertain send دون retry: PASS.
- نجح CI البعيد لاحقًا على Python 3.12/3.13، ثم اندمج PR #2 في `main`.

## نتيجة gate الآلي لـM7 — 2026-08-22

- retrieval eval: 14/14 top-1.
- `pytest`: 72 passed, 1 warning.
- Ruff correctness و`compileall`: PASS.
- PostgreSQL migrations: `0005 (head)`.
- isolated PostgreSQL upgrade/downgrade/re-upgrade: PASS.
- Telegram live: import/duplicate/conflict/provenance/version/rollback/professional copy: PASS.
- CI البعيد run `32538952535`: Python 3.12/3.13 PASS.
- اكتمل CI واندَمج PR #3 في `main`.

## M8 — Memory Intelligence & Feedback

- [x] اقتراح المحادثة لا يكتب ContactMemory قبل موافقة المالك.
- [x] اعتماد/رفض/انتهاء/استبدال الاقتراحات محكوم بالمالك وownership checks.
- [x] facts/preferences/summary تحمل provenance وconfidence وretention.
- [x] private_notes لا تدخل LLM، والذاكرة المنتهية أو غير المشتركة مستبعدة.
- [x] تنقية محلية تمنع الأسرار وOTP وبيانات الدفع والصحة من الذاكرة المشتركة.
- [x] تحرير وتصدير ومسح مؤكد من واجهة عربية مهنية.
- [x] تقييم 1–5 لا يقبله إلا مستلم الرد، والتكرار قابل للضبط.
- [x] لوحة المالك تعرض متوسط وتوزيع رضا العملاء.
- [x] التقييم لا يسبب تعلمًا صامتًا.
- [x] migration `0006` اجتازت بروفة upgrade/downgrade/re-upgrade معزولة.
- [x] Telegram live gate نجحت، ثم نُظفت البيانات الاصطناعية فقط.
- [x] محليًا: 83 passed، compileall وRuff correctness و14/14 retrieval regression.
- [x] CI Python 3.12/3.13 في run `32541333524`.
- [x] دمج PR #4 بالـSHA `00cbf89841444c322af18fcc8b143fec83a17596`.

## M9 — Production Operations

- [x] `/health` liveness لا يخفي فشل dependencies داخل نتيجة نجاح زائفة للجاهزية.
- [x] `/ready` يتحقق من DB ورأس Alembic وإعداد Telegram/AI ويعيد 503 عند الفشل.
- [x] `/metrics` محمي بـBearer عند ضبط token ولا يعرض نصوص رسائل أو PII.
- [x] AiRun يسجل trace/قرار/latency/tokens/retrieval refs ونجح في مسار Telegram حي.
- [x] السجلات JSON وتخفي credentials مع trace IDs للطلبات وAI.
- [x] العمليات الحساسة الأساسية تكتب audit metadata منقاة ضمن نفس transaction.
- [x] صورة Docker تعمل كمستخدم غير جذر وCompose يربط PostgreSQL/API على localhost.
- [x] systemd units تفصل migration عن api/bot وتطبق hardening مع backup timer.
- [x] backup custom-format يملك checksum/manifest/retention ولا يدخل Git.
- [x] restore rehearsal تستخدم قاعدة معزولة وتتحقق من revision/counts وتحذفها بعد الاختبار.
- [x] production preflight يتحقق حيًا من Telegram/DeepSeek/Gemini والقاعدة دون طباعة الأسرار.
- [x] أسرار PostgreSQL/metrics قابلة للتدوير ذريًا، ودُورت فعليًا ثم أعيد اختبار التشغيل.
- [x] بوابة Telegram الحية أثبتت AiRun/metrics/audit والصياغة المهنية، ثم نُظفت بيانات الاختبار المحددة فقط.
- [x] CI Python 3.12/3.13 للـcommit التنفيذي في run `32544367834`، بما فيه بناء صورة الإنتاج على 3.12.
- [x] CI Python 3.12/3.13 بعد commit توثيق بوابة الإصدار في run `32544458281`.
- [x] دمج PR #5 بالـSHA `8039d79618eb836ffdcef9c6c221fb8b1ab2798f` بعد نجاح CI والبوابة الحية.

## M10 — Advanced Automation

- [x] Flow ينشأ كمسودة ويعرض Preview ولا ينشر دون ضغط المالك الصريح.
- [x] Custom Intent CRUD وتشغيل/إيقاف وthreshold دون enum أو نشاط hardcoded.
- [x] النص الحر والزر الديناميكي يستطيعان بدء Flow منشور.
- [x] FlowSession مستقلة لكل محادثة وتحفظ snapshot/version لا تتغير عند نشر نسخة أحدث.
- [x] بيانات الإجابات لا تختلط بين مالك أو محادثة، وملخص المالك يعرض labels مهنية.
- [x] النية Routing فقط ولا تتجاوز Risk/State/PUBLIC grounding/approval.
- [x] Reminder يستخدم timezone المالك، يصل مرة واحدة، ولا يرسل follow-up للعميل.
- [x] AUTO الحقيقي يرسل فقط LOW-risk عالي الثقة وفق السياسة المحلية، ويسجل outgoing/idempotency/audit.
- [x] AUTO وFlow يفشلان مغلقًا عند غياب صلاحية Telegram الحية، وFlow يتوقف عند الاستلام البشري.
- [x] Reminder claim يُسترد بعد مهلة قابلة للضبط إذا انهار العامل قبل التسليم.
- [x] HIGH/MEDIUM أو INTERNAL-only أو conflict أو state مشددة لا تتجاوز الموافقة/التصعيد.
- [x] migration `0008` وبروفة upgrade/downgrade/re-upgrade وbackup/restore نجحت.
- [x] Telegram live: draft/preview/publish/route/two-step completion/reminder/AUTO/professional copy ثم تنظيف محدد.
- [x] محليًا: 106 passed، Ruff full، compileall، retrieval 14/14، Docker non-root/API gates.
- [x] CI Python 3.12/3.13 للـcommit التنفيذي في run `32546910568`.
- [x] CI Python 3.12/3.13 لتحديث دليل الإغلاق في run `32547007628`.
- [x] دمج PR #6 بالـSHA `41deb45feaa763ab51b6df063713c8fcb18f2a22` بعد نجاح CI والبوابات الحية.

## إغلاق baseline الحالي

- [x] M0–M10 موثقة ومغلقة ضمن نطاقها الحالي.
- [x] بقي `main` على baseline `0.10.0/0008` حتى اجتاز مرشح V1 البوابة الحية، ثم رُقي إلى `1.0.0/0009` عبر PR #9.
- [x] لا توجد M11 نشطة أو مطلوبة لإكمال النطاق الحالي.
- [x] أي milestone لاحقة يجب أن تملك نطاقًا جديدًا، سببًا واضحًا، ومعايير قبول مستقلة قبل التنفيذ.
## V1 Final Acceptance

- [x] لوحة المحادثات فعلية وتعرض الحالة والسياق والرد المعلق دون raw enums.
- [x] المالك يستطيع الاستلام/الإعادة/الإيقاف/الاستبعاد والرد لمرة واحدة من Telegram.
- [x] الأشخاص يدعمون AI/Memory toggles والوصول للذاكرة مع audit وowner isolation.
- [x] شاشة الأمان تفحص Business Connection وتشرح الحدود المهنية بلا placeholder.
- [x] ملخص المحادثة يحجب الأنماط الحساسة قبل الحفظ وسياق AI.
- [x] Voice/Document basic handling حي وآمن.
- [x] `sendRichMessage` فعلي مع fallback مؤكد بلا duplicate retry.
- [x] Menu preview/publish واختبار التعديل دون نشر صامت.
- [x] الردود المختصرة مرتبطة بالسؤال السابق دون تعلم أو تعديل للرسالة الأصلية.
- [x] التحية لا تتكرر بعد دخول المحادثة في الموضوع، ولا يظهر Markdown خام أو reason code للعميل.
- [x] Custom Intent يقدم إجراءات متعددة مفهومة حتى عند عدم وجود Flow منشور.
- [x] Telegram Stars يتحقق من XTR/المبلغ/العميل ولا يسلم إلا بعد `successful_payment` مطابق وغير مكرر.
- [x] دليل مالك عربي شامل يغطي الإعداد والتشغيل والخصوصية والقوائم والدفع والتشخيص.
- [x] بوابة V1 المحلية/DB/Docker/backup/live/CI النهائية ودمج PR #9 وتثبيت New‑VPS على SHA الدمج.

## Smart Secretary Autonomy & Context — Candidate 1.1.0

- [x] global AUTO يخفف الحالة الموروثة القديمة ولا يلغي override صريحًا أو HUMAN_TAKEOVER/EXCLUDED/PAUSED.
- [x] social/thanks/acknowledgment/considering/decline/close لا تحتاج business grounding.
- [x] published price/refund/discount information منفصل عن اعتماد refund/discount/commitment فعلي.
- [x] request-owner ينتقل محليًا للتحويل حتى لو صنفه المزود LOW.
- [x] pre-sales paraphrases تسترجع الباقات بدل onboarding بعد الاشتراك.
- [x] الرد القصير يستخدم الـturn المجاور وtopic shift لا يعيد استخدام سؤال قديم.
- [x] أسباب التحويل متعددة ومحددة ولا تحتوي provider/reason enum/chain-of-thought.
- [x] no silent learning وPUBLIC/INTERNAL/PRIVATE boundaries لم تتغير.
- [x] offline Smart Secretary eval: `53/53` بعد baseline `30/53`.
- [x] live provider classifier eval: `12/12` بعد baseline `0/12`.
- [x] M7 retrieval regression: `14/14`.
- [x] PostgreSQL migration rehearsal: `upgrade → downgrade base → upgrade` عند `0010`.
- [x] Docker/ready/preflight والـbackup/restore بعد migration: `1.1.0/0010` non-root، health/ready وmetrics 401→200، واستعادة معزولة قبل/بعد الترحيل.
- [x] GitHub Actions Python 3.12/3.13: runs `32762296478` و`32768416850` ناجحان.
- [x] Telegram Business UI scenarios باستخدام Contact اختبار فقط: AUTO والاجتماعي وpre-sales والحساس وAPPROVAL والسياق وإعادة اختبار افتتاحية الرد كلها PASS.
- [x] إصلاح regression عام لمنقّي الافتتاحية يمنع ترك `بك،` ويحافظ على الكلمات ذات البادئة المشابهة، مع اختبار آلي وحي.
