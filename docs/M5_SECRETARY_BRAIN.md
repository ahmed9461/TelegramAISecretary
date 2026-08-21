# M5 — Secretary Brain Foundation

## الهدف

تحويل المشروع من مولّد ردود عام إلى سكرتير قابل لإعادة التشكيل لأي نشاط أو خدمة بدون ربط المنطق البرمجي بمجال ثابت.

## المبادئ المعتمدة

1. **النشاط بيانات وليس كودًا.** تغيير العمل أو الخدمات لا يتطلب تعديل شروط برمجية خاصة بالمجال.
2. **المعرفة هي مصدر الحقائق الخاصة بالنشاط.** DeepSeek يصيغ الرد ولا يخترع أسعارًا أو خدمات أو التزامات.
3. **PRIVATE لا يصل إلى نموذج الذكاء الاصطناعي.** كما أن `private_notes` في ذاكرة الشخص Owner-only.
4. **INTERNAL يمكن أن يوجّه المسودة لكنه لا يكفي للـ auto-send.** الرد التلقائي على حقائق النشاط يحتاج PUBLIC grounding.
5. **ذاكرة كل شخص معزولة.** لا يتم خلط ذاكرة جهات الاتصال.
6. **الأمان المحلي أعلى من إعدادات النشاط.** القواعد المخصصة لا تلغي تصعيد المخاطر العالية أو القيود الأساسية.
7. **المرونة طويلة المدى.** الحقول العامة + JSON (`extras_json`, `facts_json`, `conditions_json`) تسمح بإضافة احتياجات مستقبلية دون إعادة هيكلة المشروع.

## طبقات M5

### BusinessProfile

هوية السكرتير الحالية: الاسم/العلامة، وصف النشاط، المجال، أسلوب الرد، اللغة، النبرة، التعليمات الخاصة، و`extras_json` لأي بيانات إضافية مستقبلية.

### KnowledgeItem

يستمر جدول المعرفة الموجود كمصدر حقيقة مرن. أنواع المعرفة تنظيميّة وليست منطقًا صلبًا:

- GENERAL
- SERVICE
- PRODUCT
- PRICE
- FAQ
- POLICY
- CUSTOM

مستويات الرؤية:

- PUBLIC: يمكن قوله للعميل ويصلح كمرجع للرد التلقائي الآمن.
- INTERNAL: يوجّه السكرتير ولا يُكشف كسياسة داخلية؛ يحتاج موافقة قبل auto-send للحقائق.
- PRIVATE: Owner-only ولا يدخل retrieval المرسل للـ LLM.

### ContactMemory

ذاكرة منفصلة لكل Contact:

- summary
- facts_json
- preferences_json
- private_notes
- share_with_ai

`private_notes` لا يخرج من قاعدة البيانات إلى سياق الذكاء الاصطناعي.

### ResponsePolicy

قواعد قابلة للتخصيص وغير مرتبطة بنشاط معين. تحتفظ بالوصف والنطاق والإجراء والأولوية والشروط والقيود في صيغة مرنة.

## مسار الرد بعد M5

```text
Telegram Business message
        ↓
Conversation context
        ↓
Business profile
+ safe contact memory
+ relevant knowledge
+ response policies
        ↓
DeepSeek classification / drafting
        ↓
Local deterministic safety policy
        ↓
Approval / escalation / safe auto path
```

## قاعدة عدم الاختراع

الحقائق الخاصة بالنشاط لا تُعامل كحقائق لمجرد أن النموذج يعرف معلومات عامة. عند غياب grounding مناسب يتم التصعيد للمالك بدل إنشاء معلومة غير معتمدة.

## Migration

```text
0003_secretary_brain
```

تضيف:

- `business_profiles`
- `contact_memories`
- `response_policies`

ولا تغيّر الجداول التشغيلية الخاصة باتصال Telegram Business أو approvals.

## واجهة Telegram

قسم `🧠 عقل السكرتير` يحتوي في أول شريحة M5 على:

- 🏢 الهوية
- 📚 المعرفة
- 👥 ذاكرة الأشخاص
- 🎛️ قواعد الرد

إضافة المعرفة تتم من الواجهة ولا تتطلب أوامر slash، مع بقاء أوامر M4 القديمة للتوافق الخلفي.

## ما لا يجب بناؤه

لا تضف شروطًا من نوع:

```python
if business == "programming":
    ...
```

أو منطقًا خاصًا بمنتج/خدمة بعينها. أي اختلاف بين الأنشطة يجب أن يعبَّر عنه في BusinessProfile أو Knowledge أو ResponsePolicy أو Flows.
