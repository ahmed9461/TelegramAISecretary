# Runbook — Current M6

## المتطلبات

- Python 3.12+
- Docker Desktop على Windows أو PostgreSQL 16/17
- Telegram bot مع Secretary/Business capability المطلوبة
- Owner Telegram numeric ID
- DeepSeek API key
- Gemini API key لمسار الصور

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
```

## الاختبارات

```powershell
pytest
```

آخر نتيجة موثقة على CI للفرع M6 الحالي:

```text
56 passed, 1 warning
```

التحذير الحالي StarletteDeprecationWarning متعلق بـFastAPI TestClient/httpx ولا يمنع نجاح suite.

للتجميع:

```powershell
python -m compileall -q app tests
```

## تشغيل البوت

```powershell
python -m app.telegram.run
```

بعد التشغيل من حساب المالك أرسل `/start` عند الحاجة لفتح لوحة الإدارة.

## تحديث النسخة المحلية من فرع M6

```powershell
cd D:\Desktop\telegram_ai_secretary_clean
git switch m6-secretary-learning
git pull
.\.venv\Scripts\Activate.ps1
pytest
python -m app.telegram.run
```

M6 الحالية لا تحتاج migration إضافية فوق `0003` ما لم يضاف migration لاحقًا فعلًا.

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

## اختبار Rich + Contextual Buttons

من `🧩 الواجهة والأزرار` اختر HYBRID وأنشئ زرًا سياقيًا مثل "طرق الدفع" بكلمات:

```text
دفع، سداد، تحويل، كريبتو، نجوم
```

اسأل من الحساب الثاني عن الدفع: يجب أن يظهر الزر. اسأل عن موضوع غير متعلق: يجب ألا يظهر الزر. تحقق أن الرد نفسه منسق بدون ظهور raw `**` أو `##` أو HTML tags.

## أوضاع السلوك

- AUTO: يسمح بالمسار التلقائي عندما local policy والحالة تسمحان.
- APPROVAL: يفرض الموافقة على المحادثات القابلة للتخفيف.
- OBSERVE: يمنع AI replies ويراقب السياق.
- OFF: يوقف AI behavior.

AUTO لا يلغي HUMAN_TAKEOVER أو EXCLUDED أو PAUSED.

## Failure Behavior

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

### `query is too old`
Handlers الحديثة تستخدم safe callback acknowledgment؛ الخطأ لا يفترض أن يسقط التطبيق.

## قبل الدمج إلى main

نفذ الاختبارات الآلية والاختبار الحي للمزايا Telegram-dependent. لا تدمج M6 لمجرد أن CI أخضر إذا فشل behavior الحقيقي في Business chat.
