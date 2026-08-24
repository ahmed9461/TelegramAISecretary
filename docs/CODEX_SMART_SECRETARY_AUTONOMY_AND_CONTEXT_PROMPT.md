# Codex Task — Smart Secretary Autonomy, Context & Handoff Quality

> هذا الملف تعليمات تنفيذ فعلية لـCodex داخل مشروع `TelegramAISecretary`.
> المطلوب ليس كتابة خطة أو شرح نظري فقط، بل دراسة المشروع الحالي ثم تنفيذ التحسينات واختبارها فعليًا داخل المستودع وبوابة Telegram الحية.

---

## 0) قبل أي تعديل

تعامل مع المشروع كمشروع طويل المدى قائم بالفعل، وليس تطبيقًا جديدًا.

ابدأ بقراءة الملفات المرجعية الحالية بالترتيب المناسب، وعلى الأقل:

- `docs/README.md`
- `docs/MASTER_SPEC.md`
- `docs/PROJECT_MEMORY.md`
- `docs/CONSTANTS.md`
- `docs/DECISIONS.md`
- `docs/ARCHITECTURE.md`
- `docs/AI_BEHAVIOR.md`
- `docs/KNOWLEDGE_AND_MEMORY.md`
- `docs/ACCEPTANCE_CRITERIA.md`
- `docs/DEVELOPER_HANDOFF.md`
- `docs/V1_FINAL_ACCEPTANCE.md`
- `docs/RUNBOOK.md`
- أحدث migrations والاختبارات ذات الصلة.

ثم افحص الكود الفعلي قبل اقتراح الحل. لا تعتمد على هذا الملف وحده إذا وجدت أن الكود أو التوثيق الأحدث يثبت شيئًا مختلفًا.

مهم: توجد إشارات توثيقية قديمة في بعض الملفات إلى `0.10.0/0008` بينما ملفات V1 الأحدث توثق `1.0.0/0009`. تحقق من Git/Alembic والكود الحالي أولًا، وسجل أي drift توثيقي وصححه ضمن المهمة إن كان مرتبطًا بالتغيير.

لا تفترض أن الأمثلة الواردة أدناه قائمة كلمات ثابتة يجب hardcode لها. الأمثلة فقط لتوضيح **المعنى والسلوك المطلوب**، والحل يجب أن يعمم على الصيغ واللهجات والمرادفات والسياقات المشابهة.

---

# 1) المشكلة العامة

السكرتير يعمل تقنيًا، لكن سلوكه الحالي ما زال محافظًا أكثر من اللازم في نقاط تؤثر مباشرة على جودة المنتج:

1. يفهم بعض الرسائل القصيرة أو الجديدة على أنها تحتاج تحويلًا للمالك رغم أنها رسائل اجتماعية أو استمرار طبيعي للمحادثة.
2. عند تفعيل الوضع العالمي `AUTO` ما زالت رسائل عادية كثيرة تنتهي ببطاقة موافقة للمالك، ما يجعل AUTO عمليًا قريبًا من APPROVAL.
3. سبب التحويل المعروض للمالك عام جدًا، مثل:
   `تحتاج الرسالة إلى مراجعتك لأنها قد تتضمن التزامًا أو إجراءً حساسًا.`
   بينما المطلوب أن يكون السبب مرتبطًا **بنية الرسالة والسياق الفعلي والسبب الحقيقي للمنع**.
4. الاسترجاع الحالي قد يفشل في الوصول إلى المعرفة الأنسب عندما تكون صياغة العميل دلالية وليست مطابقة لفظيًا. مثال: شخص يقول إنه غير مشترك بعد، فيُعطى خطوات تشغيل الحارس بدل أن يدخل في مسار ما قبل الاشتراك والباقات.
5. السكرتير يحتاج فهمًا أفضل لـ"أين وصلت المحادثة" بدل اعتبار كل رسالة مستقلة أو اعتبار كل موضوع جديد حساسًا.
6. نريد تحسين التعلم/التقييم من تعديلات المالك واختبارات السيناريوهات، بدون تعلم صامت وبدون تحويل تعديل واحد إلى حقيقة PUBLIC.

---

# 2) ملاحظات مؤكدة من الكود الحالي يجب التحقيق فيها

هذه ليست حلولًا مفروضة، لكنها نقاط يجب فحصها لأنها مرتبطة مباشرة بالأعراض الحالية:

## `app/conversations/context.py`

- `effective_state_for_global_mode()` يعامل الوضع العالمي كسقف أمان.
- `APPROVAL` يستطيع تشديد `AI_AUTO`.
- لكن `AUTO` لا يفك `AI_APPROVAL` تلقائيًا.

حقق في كيفية إنشاء `conversation.state` ومتى يعتبر هذا state اختيارًا صريحًا للمحادثة ومتى يكون مجرد default/inherited state.

الهدف النهائي:
- `AUTO` العالمي يجب أن يعني أن المحادثات العادية المؤهلة تعمل تلقائيًا فعلًا.
- وفي نفس الوقت لا يجوز أن يلغي تلقائيًا `HUMAN_TAKEOVER`, `EXCLUDED`, `PAUSED`, أو override صريح أكثر تشددًا للمحادثة.
- إذا كانت بنية البيانات الحالية لا تميز بين inherited state وexplicit override، صمم حلًا واضحًا بدل patch غامض.

## `app/ai/policy.py`

راجع خصوصًا القواعد الحالية:

- `HIGH_RISK` → `ESCALATE`.
- غياب grounding في معظم intents → `ESCALATE`.
- أي confidence أقل من `0.7` → `REQUIRE_APPROVAL`.
- `AI_APPROVAL` أو `MEDIUM` risk → `REQUIRE_APPROVAL`.
- INTERNAL-only grounding في AUTO → `REQUIRE_APPROVAL`.

هذه القواعد قد تكون سببًا في تحويل رسائل طبيعية أكثر من اللازم.

لا تحذف safety policy ولا تجعل LLM يملك سلطة الإرسال. المطلوب **إعادة ضبط معنى المخاطرة والإجراء** بحيث يكون التحويل حقيقيًا للحالات الحساسة، لا نتيجة تلقائية لمجرد أن الموضوع جديد أو أن النص قصير.

## `app/ai/deepseek.py`

راجع classifier prompt الحالي، وبالأخص تعريف HIGH risk.

لا تجعل مجرد ذكر:
- سعر،
- دفع،
- اشتراك،
- استرجاع كسؤال معلوماتي،
- أو موضوع مالي عام

كافيًا وحده لاعتبار الرسالة التزامًا عالي المخاطر.

يجب التفريق بين:

### معلومات آمنة
مثل:
- عرض سعر موجود في PUBLIC knowledge.
- شرح باقة.
- شرح طريقة دفع معتمدة.
- شرح سياسة الاسترجاع كما هي دون وعد.

### التزام/قرار فعلي يحتاج المالك
مثل:
- الموافقة على استرجاع مبلغ.
- منح خصم غير معتمد.
- الوعد بتعويض أو موعد ملزم غير موجود في المعرفة.
- قبول عقد أو التزام قانوني.
- كشف بيانات خاصة.
- تنفيذ إجراء حساس باسم المالك.

المخاطرة يجب أن تعتمد على **الفعل والسلطة المطلوبة والسياق** لا على كلمات الموضوع فقط.

## `app/conversations/continuity.py`

الاستمرارية الحالية تعالج ردودًا قصيرة بنمط deterministic محدود.

طوّر الفهم بحيث يحافظ السكرتير على سياق المحادثة بصورة عامة دون تحويل المشروع إلى مجموعة if-statements لعبارات محددة.

أمثلة دلالية يجب ألا تتحول للمالك تلقائيًا:

- `شكرا`
- `مشكور`
- `تمام يعطيك العافية`
- `بفكر بالموضوع`
- `خليني أفكر`
- `لا خلاص شكرا`
- `ما قصرت`
- `اوكي بشوف`

هذه الأمثلة تمثل فئات مثل:
- acknowledgment
- gratitude
- soft decline
- thinking/considering
- conversation close
- simple continuation

الحل يجب أن يعمم على الصيغ المشابهة، لا أن يكون whitelist ثابتًا لهذه النصوص.

## `app/knowledge/retrieval.py`

الاسترجاع الحالي lexical/deterministic جيد كأساس، لكنه قد يفشل عندما لا تتطابق كلمات العميل مع عنوان المعرفة مباشرة.

مثال سلوكي:
- العميل: `أنا لست مشترك بعد`
- المطلوب: فهم أنه في مرحلة pre-sales / subscription interest، ثم استرجاع الباقات أو سؤال عدد المجموعات.
- غير المطلوب: القفز مباشرة إلى خطوات تشغيل الحارس داخل المجموعة إلا إذا سأل عن التشغيل.

لا تضف نشاط GROUP GUARD أو الأسعار في Core. المشروع generic حسب ADR-002.

نفذ تحسينًا عامًا، مثل intent-aware retrieval / query enrichment / lightweight reranking أو حل أفضل تبرره evals. لا تضف vector infrastructure إلا إذا أظهرت evals أن الحل الأبسط غير كافٍ، التزامًا بقرار PostgreSQL-first retrieval.

## `app/approvals/service.py` و`app/telegram/professional_copy.py`

الـapproval يحتفظ بـreason_code وintent، لكن النص المعروض للمالك مبني غالبًا على mapping عام.

طوّر سبب التحويل ليصبح:
- مختصرًا.
- مفهومًا.
- مرتبطًا بالنية والسياق.
- بلا أكواد داخلية.
- بلا chain-of-thought أو reasoning خفي.

المطلوب **policy explanation قصيرة قابلة للمراجعة**، وليست كشف تفكير النموذج.

أمثلة شكلية فقط:

- `سبب التحويل: العميل يطلب اعتماد استرجاع مبلغ، وهذا قرار مالي يحتاج موافقة المالك.`
- `سبب التحويل: العميل طلب خصمًا غير موجود ضمن الأسعار أو السياسات المعتمدة.`
- `سبب التحويل: لا توجد معلومة PUBLIC مؤكدة عن هذه الخدمة، والرد قد ينشئ وعدًا غير موثق.`
- `سبب التحويل: العميل طلب التحدث مع المالك مباشرة.`

لا تستخدم نفس النص العام لجميع الحالات.

---

# 3) السلوك المطلوب للوضع العالمي AUTO

أعد تعريف السلوك عمليًا واختبره end-to-end.

## AUTO

عندما يختار المالك `AUTO`:

- الردود العادية الآمنة يجب أن تُرسل مباشرة للعميل بدون بطاقة موافقة كل مرة.
- يجب أن يبقى مسار الإرسال الحالي الآمن: revision/idempotency/approval ledger/live `can_reply`/audit/outgoing persistence.
- لا ترسل owner approval card للرد الذي local policy سمح له بـAUTO_REPLY.
- يمكن تسجيل القرار/telemetry بدون إزعاج المالك.
- لا تعتبر MEDIUM مجرد مرادف آلي لـapproval إذا كان التصنيف MEDIUM واسعًا أكثر من اللازم؛ أصلح taxonomy أو policy بحيث action يطابق المخاطر الحقيقية.

## APPROVAL

- الردود المقترحة التي يسمح النظام بصياغتها تمر على المالك قبل الإرسال وفق الوضع.
- لا تغير هذا الوضع إلى AUTO ضمنيًا.

## OBSERVE

- فهم/تسجيل السياق دون رد AI للعميل.

## OFF

- لا ردود AI.

## الحالات الأكثر تشددًا للمحادثة

يجب احترام:
- HUMAN_TAKEOVER
- EXCLUDED
- PAUSED
- وأي override صريح أكثر تشددًا.

لكن لا تجعل conversation state موروثًا قديمًا يجعل زر AUTO العالمي بلا فائدة.

إذا احتجت schema/state-source/override flag أو migration، افحص data model والمigrations أولًا ونفذ migration additive ومدروس مع upgrade/downgrade/rehearsal واختبارات.

---

# 4) السلوك المطلوب للنيات والمحادثة

أنشئ أو حسن taxonomy عامة للنيات بما يناسب secretary عام، لا نشاطًا واحدًا.

يجب أن يميز على الأقل دلاليًا بين فئات مثل:

- greeting
- thanks / acknowledgment
- conversation close
- decline / not interested
- considering / thinking
- pre-sales interest
- pricing inquiry
- package/product selection
- how-to / onboarding
- technical support / troubleshooting
- request for factual information
- request owner/human
- complaint
- refund information inquiry
- refund authorization/request requiring decision
- discount information vs discount grant/request
- private/sensitive data request
- binding commitment / promise
- unclear request

الأسماء الدقيقة لك، لكن لا تحصر الحل بهذه القائمة إذا ظهرت taxonomy أفضل بعد فحص النظام.

## قاعدة مهمة

ليس كل intent يحتاج business grounding.

رسائل اجتماعية بحتة مثل الشكر أو إنهاء الحوار يمكن للسكرتير الرد عليها طبيعيًا حتى بدون KnowledgeItem، لأنها لا تدعي حقيقة تجارية.

وفي المقابل، أي حقيقة تجارية متغيرة مثل السعر أو السياسة أو التوفر تظل محتاجة owner-controlled grounding وفق ADR-010.

## no-grounding behavior

راجع قاعدة `NO_GROUNDING` الحالية.

لا تجعل غياب knowledge يؤدي دائمًا إلى إزعاج المالك إذا كان الرد الآمن الممكن هو مجرد:
- طلب توضيح،
- اعتراف بعدم توفر معلومة مؤكدة،
- أو رد اجتماعي طبيعي لا يحتوي حقيقة تجارية.

صعّد عندما يكون غياب المعرفة يجعل الرد المحتمل ينشئ التزامًا/معلومة مهمة غير موثقة أو عندما يطلب العميل المالك فعلًا.

---

# 5) فهم مرحلة المحادثة

نريد السكرتير أن يعرف أين وصل الحوار.

مثال متعدد الأدوار:

1. العميل: `أنا مو مشترك للحين`
2. السكرتير: يعرض مسار الاشتراك المناسب أو يسأل عن عدد المجموعات.
3. العميل: `عندي 3`
4. السكرتير: يربطها بالسؤال السابق ويعطي الباقة المناسبة من PUBLIC knowledge.
5. العميل: `بفكر بالموضوع`
6. السكرتير: رد طبيعي قصير مثل `أكيد، خذ راحتك وإذا احتجت أي توضيح أنا حاضر.` بدون handoff.
7. العميل: `لا خلاص شكرا`
8. السكرتير: يغلق الحوار طبيعيًا بدون handoff.

مثال آخر:

1. العميل يسأل عن مشكلة تقنية.
2. السكرتير يبدأ troubleshooting grounded.
3. العميل يرد `ايوه سويته` أو `ما نفع`.
4. يجب أن يعرف السكرتير أي خطوة تم اختبارها وألا يبدأ من الصفر.
5. إذا استنفدت الخطوات المعتمدة والمشكلة مستمرة، عندها يكون handoff مبررًا وسببه واضحًا.

افحص:
- recent message window
- conversation summary
- continuity resolver
- resolved user message
- retrieval query
- memory boundaries

وطور أقل تغيير معماري قوي يحقق الاستمرارية بدون تعلم صامت أو تحويل كل transcript إلى memory.

---

# 6) تحسين سبب التحويل / الموافقة

نريد بطاقة المالك تشرح:

- **ما نية العميل؟**
- **لماذا لم يسمح النظام بالإرسال التلقائي؟**
- **ما الجزء الحساس فعليًا؟**

لكن لا تعرض:
- chain-of-thought.
- system prompt.
- أسرار.
- raw provider names.
- أكواد policy الداخلية كرسالة للمستخدم.

يمكن تخزين metadata bounded مثل:
- normalized intent
- risk category
- reason_code
- safe reason_detail / review_summary
- grounding status
- conflict indicator

إذا احتاج ذلك تعديلًا في schema، قيّم الحاجة أولًا؛ يمكن استخدام `context_json` إن كان مناسبًا وآمنًا بدل migration غير ضرورية.

الـreason_detail يجب أن يكون **وصف قرار** وليس reasoning داخلي طويل.

---

# 7) تحسين التعلم بدون تعلم صامت

المشروع لديه مبدأ صريح: لا silent learning.

حافظ عليه.

راجع مسار:
- `✏️ تعديل الرد`
- `🧠 تعلّم من تعديلي`
- feedback/evals

وطوّر الاستفادة منه إن احتاج الأمر بحيث:

- تعديلات الأسلوب يمكن أن تحسن guidance INTERNAL بعد تأكيد المالك.
- لا تتحول صياغة واحدة إلى PRICE/POLICY/PUBLIC fact تلقائيًا.
- لا تتعلم من كلام العميل كحقيقة نشاط.
- لا تستخدم تقييمات العملاء لتغيير prompt بصمت.

المقصود بـ"تدريب السكرتير" هنا هو تحسين behavior/evals/feedback loop والمعرفة المعتمدة، وليس fine-tuning عشوائي لنموذج خارجي.

إذا وجدت فرصة لإضافة eval harness يحاكي تعديلات المالك ويقيس تحسن classification/retrieval/action، نفذها.

---

# 8) الاختبارات الآلية المطلوبة

لا تعتبر المهمة مكتملة بمجرد أن unit test واحد ينجح.

أضف regression tests + eval dataset مناسبة.

## A) AUTO vs APPROVAL

اختبر على الأقل:

- global AUTO + safe grounded info → AUTO_REPLY.
- global AUTO + greeting/social acknowledgment → AUTO_REPLY دون grounding تجاري.
- global AUTO + real high-risk commitment → ESCALATE/REQUIRE_APPROVAL حسب التصميم.
- global AUTO + HUMAN_TAKEOVER → no AI send.
- global AUTO + EXCLUDED/PAUSED → no AI send.
- global APPROVAL + safe reply → approval.
- OBSERVE/OFF → no AI send.

واختبر السيناريو الذي كشف المشكلة فعليًا: تغيير global mode إلى AUTO على محادثة كانت في الحالة الافتراضية السابقة لا يجب أن يبقيها approval بلا سبب، مع الحفاظ على explicit per-conversation override إن كان موجودًا.

## B) social/closure intents

أنشئ مجموعة متنوعة من الصيغ العربية واللهجية والإنجليزية البسيطة، لا تعتمد فقط على الأمثلة التالية:

- شكر.
- موافقة بسيطة.
- تفكير.
- رفض مهذب.
- إنهاء محادثة.
- رجوع بعد فترة قصيرة.

يجب ألا تصبح HIGH/MEDIUM-sensitive لمجرد غياب business grounding.

## C) presales intent + retrieval

اختبر مع knowledge fixture عام (ليس GROUP GUARD hardcoded في Core):

- `أنا غير مشترك بعد`
- `كيف أبدأ؟`
- `أبغى أشترك`
- `وش الباقات؟`
- `عندي ثلاث مجموعات`
- `محتار أي باقة`

يجب أن يصل retrieval إلى معلومات pre-sales/pricing ذات الصلة، لا onboarding بعد الاشتراك بلا سبب.

## D) true sensitive cases

اختبر أن النظام ما زال يحمي فعليًا:

- اعتماد refund/compensation.
- منح خصم غير معتمد.
- وعد مالي/زمني ملزم غير grounded.
- contract/legal commitment.
- private data disclosure.
- إجراء حساس باسم المالك.
- explicit request to talk to owner.

## E) multi-turn continuity

اختبر حوارات من 4–8 turns وليس رسائل منفردة فقط.

القرار والرد يجب أن يفهما:
- السؤال السابق.
- إجابة رقمية قصيرة.
- `نعم/لا`.
- `ما نفع` بعد troubleshooting.
- `بفكر` بعد عرض باقة.
- تغير الموضوع بوضوح، بدون سحب سؤال قديم خطأً.

## F) approval reason quality

اختبر أن السبب المعروض:
- ليس النص العام نفسه لكل الحالات.
- يذكر سببًا مرتبطًا بالقرار.
- لا يحتوي provider name/reason enum/raw policy code.
- لا يكشف INTERNAL/PRIVATE.
- لا يحتوي chain-of-thought.

---

# 9) Evals المطلوبة

المشروع لديه `evals/` وretrieval regression قائم.

أنشئ eval suite جديدة مستقلة وقابلة للتكرار، مثل:

- intent classification eval
- risk/action eval
- continuity eval
- retrieval intent-aware eval
- approval reason eval

لا تجعل dataset كلها happy-path.

أدخل:
- paraphrases
- لهجة خليجية/سعودية/يمنية عربية طبيعية
- spelling variations
- punctuation/no punctuation
- short replies
- ambiguous messages
- negative controls
- truly sensitive controls

سجل baseline قبل التعديل إذا أمكن، ثم النتيجة بعد التعديل.

لا تدّع نسبة تحسن دون output فعلي.

---

# 10) الاختبارات الحية باستخدام مهارة استخدام الكمبيوتر

هذه المهمة **تتطلب live verification حقيقية** لأنها تتعلق بتجربة Telegram Business الفعلية، وليس unit tests فقط.

بعد نجاح الاختبارات الآلية والنشر إلى بيئة الاختبار/الخادم المناسب:

1. استخدم **مهارة استخدام الكمبيوتر (computer-use skill)** المتاحة لديك.
2. اختبر من واجهة Telegram الفعلية.
3. استخدم Contact/حساب اختبار فقط، ولا تختبر على عميل حقيقي.
4. لا تطبع أو تصور secrets/tokens/.env.
5. لا تشغل poller ثاني بنفس token بالتوازي مع production poller.
6. لا تنفذ دفعًا حقيقيًا أو التزامًا ماليًا.
7. لا تحذف بيانات حقيقية عند تنظيف الاختبارات؛ نظف فقط IDs الاصطناعية التي أنشأتها ووثقتها.

إذا مهارة استخدام الكمبيوتر غير متاحة فعليًا في جلستك، **لا تدّع أنك استخدمتها**. أكمل كل ما تستطيع من integration/live API tests، وسجل بوضوح أن بوابة UI الحية لم تنفذ وما الذي يحتاج جلسة computer-use.

## سيناريوهات UI حية إلزامية

### سيناريو 1 — AUTO فعلي

- من بوت المالك حوّل الوضع إلى `AUTO`.
- من Contact الاختبار أرسل سؤالًا آمنًا grounded.
- تحقق أن الرد يصل للعميل مباشرة.
- تحقق أن المالك **لا تصله بطاقة موافقة لهذا الرد**.
- تحقق من DB/audit/AiRun أن الإرسال سجل مرة واحدة.

### سيناريو 2 — رسالة اجتماعية

بعد محادثة طبيعية أرسل من Contact الاختبار معنى مثل:
- `بفكر بالموضوع`
- ثم صياغة أخرى مثل `لا خلاص مشكور`

تحقق:
- لا owner handoff.
- لا approval card في AUTO.
- رد طبيعي قصير أو إغلاق مناسب.

لا تعتمد نجاح السيناريو على هذه النصوص حرفيًا؛ جرّب paraphrase إضافية.

### سيناريو 3 — pre-sales

Contact يقول معنى: `أنا مو مشترك للحين`.

المطلوب:
- السكرتير يدخل في pre-sales.
- يسترجع PUBLIC knowledge المناسبة.
- يعرض الباقات أو يسأل السؤال المنطقي التالي حسب المعرفة.
- لا يقفز تلقائيًا إلى خطوات تشغيل خدمة بعد الاشتراك إلا إذا طلب العميل ذلك.

### سيناريو 4 — true sensitive

Contact يطلب إجراءً فعليًا يحتاج سلطة المالك، مثل اعتماد تعويض/استرجاع أو خصم غير معتمد.

المطلوب:
- لا auto-send لالتزام جديد.
- تظهر بطاقة مراجعة/تحويل.
- سبب التحويل محدد ومرتبط بالنية.

### سيناريو 5 — APPROVAL

غيّر الوضع إلى APPROVAL.

- أرسل سؤالًا آمنًا.
- يجب أن تصلك بطاقة موافقة.
- أرسلها مرة واحدة فقط بعد اعتماد المالك.

### سيناريو 6 — context

نفذ محادثة متعددة turns:
- سؤال من السكرتير.
- رقم/اختيار قصير.
- follow-up.
- شكر/تفكير.

تحقق أن الردود مرتبطة بالسياق ولا تعيد التحية ولا تحول كل turn للمالك.

---

# 11) Observability

حسن telemetry إذا احتجت، مع الالتزام بـADR-027.

يجب أن نستطيع تشخيص القرار من metadata bounded مثل:

- intent
- risk
- action
- reason_code
- confidence
- effective state
- global mode
- whether state was explicit/inherited إذا أضفت هذا المفهوم
- public grounding present?
- conflicting grounding?
- knowledge refs

لكن ممنوع نسخ body الرسالة أو prompt أو secrets داخل metrics/AiRun/audit لمجرد سهولة debugging.

---

# 12) مبادئ التنفيذ غير القابلة للتفاوض

- لا hardcode GROUP GUARD أو أي نشاط داخل Core.
- لا hardcode عبارات `شكرا/بفكر/...` كحل وحيد؛ عالج الفئات دلاليًا.
- لا تجعل LLM يقرر الإرسال وحده.
- local deterministic policy تبقى صاحبة القرار النهائي.
- لا تسمح PRIVATE أو private_notes بالوصول للنموذج.
- INTERNAL يوجه ولا يُكشف.
- حقائق النشاط المتغيرة تحتاج owner-controlled grounding.
- لا silent learning.
- لا blind retry لcustomer send غير المؤكد.
- live `can_reply` check قبل الإرسال يبقى موجودًا.
- لا تكسر idempotency/revision binding/approval ledger.
- لا تضف vector DB لمجرد أنها تبدو أذكى؛ اثبت الحاجة بالـeval أولًا.
- لا تنشئ migration قبل فحص head الحالي والجداول الفعلية.
- لا تستخدم production customer chats في الاختبار.
- لا تضع secrets في Git أو logs أو screenshots.

---

# 13) معايير القبول النهائية

لا تعتبر المهمة مكتملة حتى تتحقق كل النقاط التالية:

## Intelligence

- [ ] الرسائل الاجتماعية/الختامية لا تتحول للبشر دون سبب حقيقي.
- [ ] الرسائل القصيرة تفهم ضمن السياق عندما تكون continuation.
- [ ] تغير الموضوع الواضح لا يربط خطأً بسؤال قديم.
- [ ] pre-sales intent يستطيع استرجاع knowledge المناسبة حتى مع صياغة غير مطابقة حرفيًا.
- [ ] business facts لا تُخترع.

## AUTO

- [ ] global AUTO يؤدي فعلًا إلى auto-send للرسائل الآمنة المؤهلة.
- [ ] لا approval card للمالك في SAFE_AUTO.
- [ ] explicit stricter conversation states تبقى محترمة.
- [ ] auto send مرة واحدة فقط ومسجل في outgoing/audit.

## Safety

- [ ] الالتزامات المالية/القانونية/الخاصة الحقيقية لا ترسل تلقائيًا.
- [ ] الخصم أو refund authorization غير المعتمد يحتاج المالك.
- [ ] PUBLIC/INTERNAL/PRIVATE boundaries باقية سليمة.
- [ ] no-grounding لا يؤدي إلى hallucination.

## Handoff UX

- [ ] سبب التحويل خاص بالحالة وليس generic boilerplate فقط.
- [ ] السبب يذكر النية/نوع القرار بصورة مهنية.
- [ ] لا chain-of-thought ولا أكواد داخلية ولا provider names.

## Tests

- [ ] pytest PASS.
- [ ] Ruff correctness PASS.
- [ ] `python -m compileall -q app tests` PASS.
- [ ] retrieval regression الحالية لا تتراجع.
- [ ] evals الجديدة PASS وفق thresholds موثقة.
- [ ] PostgreSQL migration rehearsal إذا أضفت migration.
- [ ] Docker/ready/preflight gates عند تغيير runtime/deployment.
- [ ] Telegram Business live tests PASS.
- [ ] computer-use UI scenarios PASS، أو blocker موثق بصدق إذا الأداة غير متاحة.
- [ ] GitHub Actions Python 3.12/3.13 PASS قبل الدمج.

---

# 14) التوثيق والتسليم

بعد التنفيذ:

1. حدث `docs/AI_BEHAVIOR.md` إذا تغير intent/risk/action/grounding behavior.
2. حدث `docs/DECISIONS.md` إذا تغير معنى global mode/state precedence أو retrieval architecture.
3. حدث `docs/ACCEPTANCE_CRITERIA.md` بالسلوك الجديد واختباراته الفعلية.
4. حدث `docs/PROJECT_MEMORY.md` و`docs/PROGRESS.md` إذا اعتُمدت مرحلة/تحسين جديد.
5. حدث `docs/RUNBOOK.md` فقط إذا تغير التشغيل.
6. أنشئ تقريرًا حيًا مثل:
   `docs/SMART_SECRETARY_LIVE_TEST_REPORT.md`
   ويحتوي السيناريوهات والنتائج الفعلية وIDs الاختبار الاصطناعية التي نُظفت، بدون أسرار أو نصوص خاصة لا داعي لها.
7. إذا وجدت drift بين `docs/README.md` وحالة V1 الأحدث، صححه ضمن التوثيق المناسب بدل ترك مرجع رئيسي قديم.

في نهاية المهمة أعطني:

- Root causes التي ثبتت من الكود والاختبارات.
- الملفات التي تغيرت ولماذا.
- مقارنة baseline vs after للـevals.
- نتائج الاختبارات المحلية.
- نتائج CI.
- نتائج Telegram live + computer-use.
- هل AUTO أصبح فعليًا كما هو مطلوب؟
- أمثلة موجزة للـhandoff reasons الجديدة.
- أي مخاطر أو حدود باقية.

**لا تكتفِ بقول "تم تحسين الذكاء". أثبت التحسن بالاختبارات والـevals والسلوك الحي.**
