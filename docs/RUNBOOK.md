# Runbook — Telegram AI Secretary V1

## المتطلبات

- Python 3.12+
- Docker Desktop على Windows أو PostgreSQL 16/17
- Telegram bot مع Secretary/Business capability المطلوبة
- Owner Telegram numeric ID
- DeepSeek API key
- Gemini API key لمسارات الصور والصوت والمستندات المدعومة

## إعداد Windows لأول مرة

```powershell
cd D:\Desktop\telegram_ai_secretary_clean
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

حرر `.env` محليًا. لا تضع القيم الحقيقية في Git.

## PostgreSQL

الإعداد المحلي في `docker-compose.yml` يستخدم host port 5433 لتقليل التعارض مع PostgreSQL محلي:

```powershell
docker compose up -d postgres
docker compose ps
```

المتوقع:

```text
127.0.0.1:5433->5432/tcp
```

لا تستخدم `docker compose down -v` أثناء تحديث عادي لأنه يحذف volume البيانات.

## Migrations

شغل Alembic CLI من البيئة الافتراضية:

```powershell
alembic upgrade head
alembic current
```

لا تستخدم `python -m alembic` في هذه البيئة؛ حزمة Alembic الحالية لا توفر `alembic.__main__` بهذه الطريقة.

Migrations المعروفة حاليًا:

```text
0001_initial
0002_stability
0003_secretary_brain
0004_m7_knowledge_operations
0005_m7_approval_provenance
0006_m8_memory_intelligence
0007_m9_production_observability
0008_m10_advanced_automation
0009_v1_payments
0010_smart_secretary_state_source
```

## الاختبارات

```powershell
pytest
```

آخر نتيجة محلية كاملة لمرشح V1 قبل CI والنشر:

```text
130 passed, 1 warning
```

التحذير الحالي StarletteDeprecationWarning متعلق بـFastAPI TestClient/httpx ولا يمنع نجاح suite.

للتجميع:

```powershell
python -m compileall -q app scripts tests
```

لتقييم جودة الاسترجاع بصورة مستقلة:

```powershell
python scripts/evaluate_retrieval.py
```

النتيجة الحالية: `14/14 top-1`.

لتقييم الاستقلالية والسياق والاسترجاع وأسباب التحويل بصورة مستقلة:

```powershell
python scripts/evaluate_smart_secretary.py
python scripts/evaluate_smart_secretary.py --live-provider
```

الأمر الأول deterministic ومطلوب في CI المحلي. الأمر الثاني يستخدم DeepSeek على dataset اصطناعية فقط ولا يطبع المفتاح، ويقيس intent/risk/action الفعلية. لا تعتبر نتيجة offline بديلًا عن Telegram Business UI gate.

بروفة migration تستخدم قاعدة PostgreSQL مؤقتة: `upgrade head` ثم `downgrade base` ثم `upgrade head`، ويجب أن تنتهي عند رأس المصدر الحالي `0010`. شغّلها بأداة `python -m scripts.rehearse_migrations`؛ تقرأ الرأس ديناميكيًا، تنشئ اسمًا محدودًا وآمنًا وتحذف القاعدة المؤقتة في `finally`. لا تنفذ downgrade على قاعدة حقيقية لمجرد الاختبار.

لاختبار حد retry دون قطع شبكة حقيقية أو المخاطرة بتكرار رد عميل:

```powershell
pytest tests/test_resilient_bot.py
```

هذا الاختبار يحقن `TelegramNetworkError`: طلب المالك يعاد بعدد محدود مع backoff، أما طلب العميل غير المؤكد فيفشل مغلقًا دون retry.

## تشغيل البوت

```powershell
python -m app.telegram.run
```

بعد التشغيل من حساب المالك أرسل `/start` عند الحاجة لفتح لوحة الإدارة.

## تحديث النسخة المحلية من فرع V1

```powershell
cd D:\Desktop\telegram_ai_secretary_clean
git switch codex/final-v1-acceptance
git pull
.\.venv\Scripts\Activate.ps1
pytest
python -m app.telegram.run
```

يجب أن يعرض `alembic current` الرأس المطابق للكود (`0010` لمرشح 1.1.0) قبل تشغيله.

## اختبار حي أساسي

1. أرسل رسالة من حساب Telegram ثانٍ إلى الحساب الشخصي للمالك.
2. تحقق من وصول approval card في بوت الإدارة.
3. جرّب Reject ثم Send.
4. جرّب Edit وتأكد أن النص المعدل هو الذي يصل.
5. جرّب Sources.
6. جرّب Learn from edit وتأكد من وجود confirmation.
7. اختبر رسالة جديدة بعد رد يدوي للمالك وتأكد أن draft القديم لا يرسل.
8. عدل/احذف رسالة العميل وتأكد من إبطال draft القديم.
9. أرسل صورة وتأكد من Gemini → DeepSeek path.
10. أنشئ Flow كمسودة، عاينه، ثم انشره وابدأه من حساب ثانٍ بالنص الحر.
11. تحقق أن تعديل/نشر نسخة أحدث لا يغير جلسة Flow بدأت سابقًا.
12. أنشئ تذكيرًا مستقبليًا في timezone المالك وتأكد أنه يصل مرة واحدة ثم يصبح غير فعال.
13. لا تختبر AUTO إلا على Contact تجريبي وحالة LOW-risk؛ تحقق من PUBLIC grounding ومن عدم وجود بطاقة موافقة أو إرسال مكرر.
14. ابدأ حوارًا بتحية ثم اسأل سؤالين متتابعين؛ يجب ألا يعيد السكرتير التحية بعد دخول الموضوع.
15. اجعل آخر سؤال يطلب عددًا ثم أرسل رقمًا منفردًا مثل `4`؛ يجب أن يربطه بالسؤال السابق دون تعديل الرسالة الأصلية أو التعلم منها.
16. أنشئ زرًا في المسودة، عاينه، غيّر ترتيبه، ثم انشره صراحة؛ يجب ألا يراه العميل قبل النشر.
17. أنشئ طلبًا مخصصًا وتأكد أن شاشة الإجراء تعرض تحسين الفهم، وردًا ثابتًا بموافقة، وتحويلًا للمتابعة البشرية، إضافة إلى أي Flow منشور.
18. اختبر Voice/Document اصطناعيين غير حساسين وتأكد أن المخرجات تدخل مسار الموافقة ولا تحفظ المحتوى في السجلات التشغيلية.
19. تحقق أن الرد المنظم يصل Native Rich Message، وأن الفشل المؤكد فقط يستخدم النص العادي مرة واحدة بلا تكرار.
20. أنشئ زر دفع نجوم تجريبيًا، عاينه وانشره، وتحقق من إنشاء رابط XTR. لا تنفذ معاملة مالية إلا ضمن اختبار مصرح ومحدد.

## الأتمتة والتذكيرات

معالج التذكير يعمل داخل عملية البوت نفسها. لا تشغل عمليتي bot بالتوازي لأن ذلك يكرر polling وقد يكرر محاولات claim. الإعدادات:

```text
SCHEDULE_POLL_SECONDS=30
SCHEDULE_BATCH_SIZE=20
SCHEDULE_CLAIM_TIMEOUT_SECONDS=300
CUSTOM_INTENT_DEFAULT_THRESHOLD=0.82
```

إذا لم يصل تذكير، افحص `schedules.enabled`, `last_run_at`, ووقت `config_json.run_at` مقارنة بـUTC دون طباعة نصوص حساسة. `last_run_at` مع `enabled=true` يعني claim جارٍ أو عاملًا انقطع؛ يحرره الفشل المؤكد فورًا، ويمكن لعامل واحد استرداده بعد انتهاء lease الافتراضية (300 ثانية). لا تعدل التذكير يدويًا في الإنتاج قبل التأكد من عدم وجود عملية إرسال جارية.

قبل AUTO أو إرسال خطوة Flow يعيد البوت قراءة اتصال Telegram Business ويتحقق من المالك و`can_reply`. عند تعذر التحقق لا يرسل ولا يعيد المحاولة عمياء، ويسجل الحالة ويبلغ المالك بصياغة مهنية.

## اختبار Bulk Knowledge

من لوحة المالك:

```text
📥 تغذية العقل
```

اختر visibility ثم الصق مصدرًا كبيرًا أو ارفع ملفًا مدعومًا. تحقق من preview ثم `✅ اعتماد الكل`. بعد ذلك اسأل من حساب آخر عن معلومة من المصدر وتحقق من ظهورها في الرد/المصادر وعدم اختراع معلومات غير موجودة.

الملفات المدعومة حاليًا:

```text
TXT, MD, CSV, JSON, YAML, YML
```

اختبار M7 يضيف التحقق من رفض الاستيراد المطابق، ظهور الدفعة في إدارة المعرفة، والتراجع عن الدفعة مع اختفاء عناصرها الفعالة من الاسترجاع.

## اختبار التعارض والمصادر

1. أنشئ معلومتين اصطناعيتين فعالتين بالنوع والعنوان نفسيهما ومحتوى مختلف.
2. اسأل عنهما من حساب الاختبار.
3. تحقق من أن الرد لا يرسل تلقائيًا وأن بطاقة المالك تشرح التعارض بصياغة عربية.
4. افتح المصادر وتحقق من المصدر والنسخة ووجود التعارض.
5. أزل/تراجع عن المصدر الاصطناعي، ثم تأكد أن الاسترجاع عاد إلى حقيقة واحدة.
6. نظف جميع البيانات الاصطناعية فقط وتأكد أن البيانات السابقة لم تتغير.

## اختبار Rich + Contextual Buttons

من `🧩 الواجهة والأزرار` اختر HYBRID وأنشئ زرًا سياقيًا مثل "طرق الدفع" بكلمات:

```text
دفع، سداد، تحويل، كريبتو، نجوم
```

اسأل من الحساب الثاني عن الدفع: يجب أن يظهر الزر. اسأل عن موضوع غير متعلق: يجب ألا يظهر الزر. تحقق أن الرد نفسه منسق بدون ظهور raw `**` أو `##` أو HTML tags.

## دفع Telegram Stars

- أمر `/terms` يعرض شروط الدفع القابلة للضبط، وأمر `/paysupport` يعرض قناة الدعم.
- لا تُسلّم الخدمة عند إنشاء الفاتورة أو `pre_checkout_query`؛ التسليم ورسالة النجاح لا يحدثان إلا بعد `successful_payment` مطابق.
- يتحقق المسار من صاحب الطلب، و`XTR`، والمبلغ، والمهلة، ومعرّف الشحنة الفريد، وتبقى إعادة إشعار النجاح idempotent.
- زر «رابط / بوابة خارجية» مناسب للروابط الخارجية الثابتة. أي API دفع ديناميكي إضافي يحتاج Adapter موثقًا، Webhook موقّعًا، وإدارة أسرار مستقلة؛ لا تضع مفاتيحه في بيانات الأزرار.

## أوضاع السلوك

- AUTO: يسمح بالمسار التلقائي عندما local policy والحالة تسمحان.
- APPROVAL: يفرض الموافقة على المحادثات القابلة للتخفيف.
- OBSERVE: يمنع AI replies ويراقب السياق.
- OFF: يوقف AI behavior.

AUTO لا يلغي HUMAN_TAKEOVER أو EXCLUDED أو PAUSED.

## API التشغيلية والمراقبة

تشغيل API محليًا:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- `GET /health`: liveness خفيف ويعرض status/version/environment فقط.
- `GET /ready`: يعيد 200 فقط إذا DB متاحة عند رأس Alembic وكانت إعدادات Telegram/AI المطلوبة موجودة؛ وإلا 503 مع checks غير حساسة.
- `GET /metrics`: Prometheus text. إذا كان `METRICS_TOKEN` مضبوطًا، أرسل `Authorization: Bearer <token>`؛ عدم التفويض يعيد 401.

في production يجب توليد token طويل وعدم تعريض المنفذ مباشرة للإنترنت. اربط loopback وضع reverse proxy/TLS وACL مناسبين أمامه عند الحاجة.

## Docker production layout

تحقق من الملف وابن الصورة ثم شغل الخدمات:

```powershell
docker compose config -q
docker compose build api
docker compose up -d postgres
docker compose up -d migrate
docker compose up -d api bot
docker compose ps
```

الاسم الثابت للمشروع `telegram_ai_secretary`. `migrate` يجب أن ينتهي بصفر قبل api/bot. التطبيق داخل الصورة يعمل بالمستخدم غير الجذر `secretary`. المنافذ الافتراضية مربوطة بـ`127.0.0.1`.

لا تشغل bot من Compose وبالتوازي مع `python -m app.telegram.run` أو systemd؛ poller واحد فقط مسموح لكل token.

## Ubuntu + systemd

المسار المعتمد `/opt/telegram-ai-secretary` والمستخدم `secretary`. ثبّت المشروع والبيئة و`.env` بصلاحية `0600`، وأنشئ `/opt/telegram-ai-secretary/work` و`/var/backups/telegram-ai-secretary` مملوكين للمستخدم. أداة backup الحالية تستخدم Docker Compose، لذلك يحتاج المستخدم صلاحية محدودة ومراجعة للوصول إلى Docker socket (عضوية `docker` تعادل عمليًا صلاحية root؛ استخدم root-run oneshot أو socket policy أضيق إذا كانت سياسة الخادم تمنعها). ثم:

```bash
sudo cp deploy/systemd/telegram-ai-secretary-*.service /etc/systemd/system/
sudo cp deploy/systemd/telegram-ai-secretary-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-ai-secretary-api.service
sudo systemctl enable --now telegram-ai-secretary-bot.service
sudo systemctl enable --now telegram-ai-secretary-backup.timer
```

عند إصدار جديد:

```bash
sudo systemctl stop telegram-ai-secretary-bot.service telegram-ai-secretary-api.service
sudo systemctl restart telegram-ai-secretary-migrate.service
sudo systemctl start telegram-ai-secretary-api.service telegram-ai-secretary-bot.service
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

لا تبدأ الخدمات إذا فشلت migration أو readiness. الوحدات تطبق `NoNewPrivileges`, filesystem/kernel hardening وcapability drop.

## Production preflight

```powershell
python -m scripts.production_preflight --live
```

يشترط `APP_ENV=production` وloopback binding ورأس Alembic الصحيح وإعداد Telegram/DeepSeek وmetrics token قوي وPostgreSQL password غير افتراضي. `--live` يتحقق من Telegram وDeepSeek وGemini دون إرسال رسالة أو طباعة المفاتيح. استخدم `--allow-development` فقط لبروفة الجهاز المحلي، ولا تعتبرها إثبات نشر production.

## PostgreSQL backup وrestore rehearsal

أنشئ نسخة custom-format مع checksum manifest وretention:

```powershell
python -m scripts.backup_postgres --output-dir backups --retention-days 30
```

اختبر أحدث ملف محدد في قاعدة عشوائية معزولة:

```powershell
python -m scripts.rehearse_postgres_restore backups\secretary-<timestamp>-<id>.dump
```

تنجح البروفة فقط إذا تطابق Alembic مع رأس المصدر وقرئت counts أساسية. تحذف الأداة قاعدة `secretary_restore_*` المحددة في `finally` ولا تمس قاعدة الحقيقة.

لاستعادة فعلية بعد حادثة:

1. أوقف api/bot وخذ نسخة من الحالة الحالية إن أمكن.
2. تحقق من checksum في manifest ومن أن ملف النسخة مخزن بصلاحيات خاصة.
3. أنشئ قاعدة بديلة جديدة؛ لا تستعد فوق قاعدة الحقيقة أولًا.
4. نفذ `pg_restore --exit-on-error --no-owner --no-privileges` إلى القاعدة البديلة.
5. تحقق من `alembic_version`, counts, readiness واختبار Telegram محدود.
6. غير `DATABASE_URL` للقاعدة المستعادة ثم أعد الخدمات. احتفظ بالقاعدة القديمة كrollback حتى اكتمال القبول.

## Secret rotation

للأسرار الداخلية المحلية، بعد backup وإيقاف api/bot:

```powershell
python -m scripts.rotate_internal_secrets --apply
```

الأداة تدور PostgreSQL password و`METRICS_TOKEN`، تستبدل `.env` ذريًا وتتحقق من الاتصال دون طباعة القيم. أعد postgres/app containers أو systemd services ثم شغل preflight وreadiness. لا تشغل الأداة على ملف env مشترك دون نافذة صيانة.

لـTelegram/DeepSeek/Gemini: أنشئ المفتاح الجديد من لوحة المزود، حدّث `.env` بصلاحيات خاصة، أعد الخدمات واختبر، ثم ألغ المفتاح السابق. لا تسجل القيم في terminal history أو issue/PR/log.

## Failure Behavior

### `/ready` يعيد 503

اقرأ `checks`: إذا `database=false` افحص اتصال PostgreSQL و`alembic current` مقابل `alembic heads`. إذا Telegram/AI false افحص وجود الإعداد فقط دون طباعته. لا تغير endpoint ليعيد 200 لتجاوز المنصة.

### `/metrics` يعيد 401

تأكد أن الخدمة والمراقب يقرآن `METRICS_TOKEN` نفسه، وأن header يبدأ `Bearer `. دوّر token إذا ظهر في log أو shell history.

### duplicate Telegram polling

أوقف جميع المشغلات ثم اختر واحدًا فقط: local process أو Compose bot أو systemd bot. تحقق من process tree/container/service قبل البدء؛ لا تنشئ session أو token جديدًا لحل التعارض.

### migration service fails

اترك api/bot متوقفين، افحص الخطأ ونسخة backup ورأس المصدر. أعد بروفة migration على قاعدة مؤقتة. لا تنفذ downgrade على القاعدة الحية تلقائيًا.

### backup/restore rehearsal fails

لا تحذف آخر نسخة ناجحة. افحص صحة PostgreSQL container والمساحة وchecksum وإصدار أدوات PostgreSQL. قاعدة البروفة ذات prefix المحدد يمكن حذفها بعد التحقق أنها ليست قاعدة الحقيقة؛ الأداة تفعل ذلك تلقائيًا.

### DeepSeek/Gemini 429/5xx/network
provider retries محدودة مع backoff. عند الفشل النهائي لا يرسل رد مختلق.

### Telegram `can_reply=false`
Fail closed؛ لا إرسال.

### stale/expired approval
Fail closed؛ لا إرسال.

### customer send uncertain
يسجل كـUNCERTAIN ولا توجد blind retry.

### Telegram network error لبطاقة المالك
`ResilientOwnerBot` يعيد المحاولة بشكل محدود لرسائل owner/admin فقط. لا يطبق هذا retry العام على customer business send.

## اختبار M8 للذاكرة والتقييم

1. أرسل من حساب ثانٍ تفضيلًا دائمًا ومعه OTP اصطناعي واضح.
2. من `👥 ذاكرة الأشخاص` اختر الشخص ثم `✨ اقتراح من المحادثة`.
3. قبل الاعتماد تحقق في DB أن ContactMemory لم تتغير وأن الاقتراح لا يحتوي OTP.
4. اعتمد الاقتراح وتحقق من facts/preferences/provenance/confidence/retention.
5. اختبر تصدير JSON ثم مسح الذاكرة مع confirmation.
6. للاختبار فقط اضبط `FEEDBACK_PROMPT_EVERY_N_RESPONSES=1` في عملية البوت، وأرسل ردًا معتمدًا.
7. من حساب العميل اضغط تقييمًا، ثم افتح `📊 الإحصائيات` من حساب المالك.
8. نظف السجلات الاصطناعية المحددة وأعد تشغيل البوت دون override ليعود الافتراضي كل 3 ردود.

لا تستخدم معلومة عميل حقيقية حساسة في الاختبار، ولا تحذف سجلًا سابقًا غير مرتبط بعلامة الاختبار.

### `query is too old`
Handlers الحديثة تستخدم safe callback acknowledgment؛ الخطأ لا يفترض أن يسقط التطبيق.

## قبل الدمج إلى main

نفذ الاختبارات الآلية والاختبار الحي للمزايا Telegram-dependent. لا تدمج milestone لمجرد أن CI أخضر إذا فشل behavior الحقيقي في Business chat.
