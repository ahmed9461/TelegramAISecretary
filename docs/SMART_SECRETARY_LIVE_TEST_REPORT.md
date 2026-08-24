# Smart Secretary Autonomy & Context — Live Test Report

## Scope and verdict

تم قبول مرشح `1.1.0/0010` الخاص بفهم النية والسياق وAUTO والتحويل البشري على فرع `codex/smart-secretary-autonomy-context`. شغّل New‑VPS كود التطبيق عند `4773accf0e508906a0d015cfb2467f6864f0794a` بعد اجتياز الاختبارات الآلية وCI والاختبارات الحية من واجهة Telegram Web الفعلية. لا يحتوي هذا التقرير أسرارًا أو معرفات حسابات Telegram.

لا يعني القبول دمج الفرع في `main`: المرجع المدمج ما زال `1.0.0/0009` إلى أن يتم الدمج بإجراء مستقل.

## Automated baseline and final gates

| Gate | Baseline | Final |
|---|---:|---:|
| Offline smart-secretary eval | 30/53 | 53/53 |
| Live provider classifier eval | 0/12 | 12/12 |
| Combined smart-secretary eval | 30/65 | 65/65 |
| Existing retrieval regression | 14/14 | 14/14 |
| pytest | 130 passed | 135 passed, 1 known Starlette/httpx warning |
| Ruff / compileall | PASS | PASS |
| PostgreSQL migration rehearsal | — | `upgrade → downgrade base → upgrade` عند `0010` |
| Local Docker | — | build + health + ready + non-root + copy regression PASS |
| GitHub Actions | — | runs `32762296478` و`32768416850` PASS |

أعاد الإصلاح الأخير تشغيل pytest الكامل وevals المزود الحي والاسترجاع وRuff وcompileall من بيئة المشروع، ثم بُنيت صورة `1.1.0` محليًا. أعاد `/health` حالة سليمة، وأعاد `/ready` المراجعة `0010`، وعملت الحاوية بالمستخدم `secretary`.

## PostgreSQL and deployment evidence

- قبل ترحيل المرشح حُفظت نسخة الإنتاج `/opt/telegram-ai-secretary/backups/secretary-20260824T184053Z-57aa39b3.dump`، checksum `a214f54fba3c0d80e4638e98ba1cb49604d6bbc28d514112c26c190621b2d09a`، واستعيدت معزولًا عند `0009` بأعداد owners=1/conversations=7/messages=83.
- بعد الترحيل حُفظت `/opt/telegram-ai-secretary/backups/secretary-20260824T184744Z-7a4088aa.dump`، checksum `5a2a494d48c0bf71b28f4b98b7b0d69068b851010899b0acd2b1196bfee25bb5`، واستعيدت معزولًا عند `0010` بالأعداد نفسها.
- نُشر إصلاح الصياغة عند `4773accf0e508906a0d015cfb2467f6864f0794a` مع إبقاء صور rollback لكل من baseline `4275b48` ومرشح ما قبل الإصلاح `1fbf31d`.
- API/Bot/PostgreSQL سليمة، وAPI/Bot يعملان بالمستخدم `secretary`. `/health` أعاد `1.1.0/production` و`/ready` أعاد `0010`، وmetrics أعادت `401` بلا تفويض و`200` بالتفويض.
- production preflight الحي أعاد HTTP 200 لـTelegram وDeepSeek وGemini. لم يظهر في السجلات Traceback أو exception أو polling conflict، ولم يعمل poller محلي ثانٍ.

## Telegram Business UI scenarios

نُفذت السيناريوهات من حساب اختبار عادي يشار إليه بـContact A إلى حساب المالك، ومن واجهة Telegram Web الحقيقية. استخدمت المحادثة الداخلية رقم `2` لأغراض ربط الدليل فقط.

| Scenario | Status | Observed evidence |
|---|---|---|
| 1 — AUTO grounded direct send/no owner card/single audit | PASS | سؤال باقة خمس مجموعات أنتج `PACKAGE_SELECTION / LOW / AUTO_REPLY / SUCCESS` ورد باقة 8 مجموعات بسعر 15.99 شهريًا؛ سجل إرسال واحد ولم تظهر بطاقة موافقة للمالك. |
| 2 — social/considering/close/paraphrase | PASS | ثلاث صياغات مختلفة صُنفت `CONSIDERING` ثم `CONVERSATION_CLOSE` ثم `ACKNOWLEDGMENT` وأرسلت ردودًا طبيعية في AUTO بلا handoff أو موافقة معلقة. |
| 3 — pre-sales retrieval | PASS | `PRESALES_INTEREST / LOW / AUTO_REPLY / SUCCESS` استرجع عناصر معرفة PUBLIC للباقات والخطوات وربط عدد المجموعات السابق بالسياق بدل القفز إلى عمليات ما بعد الاشتراك. |
| 4 — true sensitive + specific reason | PASS | طلب اعتماد استرجاع كامل وخصم صُنّف `REFUND_AUTHORIZATION / HIGH / ESCALATE / SUCCESS` ولم يُرسل ردًا آليًا؛ عرضت بطاقة المالك سببًا مهنيًا محددًا لقرار مالي يحتاج موافقته. لم ينفذ دفع أو خصم أو استرجاع حقيقي. |
| 5 — APPROVAL single send | PASS | في APPROVAL أنشأ سؤال معلومات `FACTUAL_INFORMATION / LOW / REQUIRE_APPROVAL` وموافقة واحدة. ضغط المالك «إرسال الرد» في الواجهة، فتحولت إلى SENT وسُجل معرف Telegram صادر واحد فقط. |
| 6 — multi-turn context | PASS | طلب جديد سأل عن العدد، والرد القصير `3` اختار باقة 4 مجموعات، ثم متابعة سبع مجموعات اختارت باقة 8، ثم إغلاق طبيعي؛ استخدم النظام turn مجاورًا ولم يعد إلى سؤال قديم. |
| 7 — post-fix professional opening | PASS | بعد نشر `4773acc` أرسلت صياغة pre-sales جديدة حيًا. سجل AiRun `PRESALES_INTEREST / LOW / AUTO_REPLY / SUCCESS` مع `SAFE_AUTO` و`state_source=INHERITED`، وبدأ الرد «يسعدني مساعدتك من البداية» بلا الذيل النحوي المكسور «بك،». |

بعد الاختبارات أعيد الوضع العام إلى AUTO، وبقيت حالة Contact A `AI_AUTO` موروثة (`state_is_explicit=false`)، وعدد الموافقات المعلقة صفر.

## Live finding and structural fix

كشف السيناريو الثالث أن منقّي افتتاحيات الرد حذف «أهلًا» وحدها من «أهلًا بك» فترك «بك،» في أول الجملة. أصلحت `app/ai/copy.py` على مستوى معالجة لغة المخرجات عمومًا: أصبحت المطابقة واعية بالحركات، وتستهلك `بك/بكم` الاختيارية، وتحترم حدود الكلمات كي لا تحذف بادئة كلمة صحيحة مثل «أهلاوية». أضيفت حالات regression للتحية المفردة والجمع والحركات والضابط السلبي، ثم نجحت الوحدة وCI وإعادة الاختبار الحي.

## Safety notes

- لم تنفذ معاملة دفع أو استرجاع أو خصم أو التزام مالي حقيقي.
- لم تُحذف بيانات أو رسائل الاختبار الحية، ولم يُنشأ poller موازٍ.
- احتُفظ بنسخ PostgreSQL وصور rollback، ولم تُعرض أسرار في المخرجات أو هذا التقرير.
- احتفظ Telegram Web بمسودة بعد أول Enter مع أن الرسالة أُرسلت، لذلك تكرر إدخال pre-sales مرة واحدة أثناء إعادة التحقق؛ استجاب النظام مرتين بأمان وبردين سليمين. هذه ملاحظة في جلسة واجهة الاختبار وليست تكرارًا من bot/poller.
