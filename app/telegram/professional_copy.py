from __future__ import annotations

from app.ai.intents import canonicalize_intent

_DECISION_REASONS = {
    "HIGH_RISK": "تحتاج الرسالة إلى مراجعتك لأنها قد تتضمن التزامًا أو إجراءً حساسًا.",
    "NO_GROUNDING": "لا توجد معلومات موثوقة كافية لصياغة جواب دقيق.",
    "LOW_CONFIDENCE": "تحتاج الصياغة إلى مراجعتك لأن درجة اليقين ليست كافية.",
    "APPROVAL_POLICY": "إعداداتك الحالية تتطلب موافقتك قبل الإرسال.",
    "NON_PUBLIC_GROUNDING": "المعلومات المتاحة داخلية، لذلك يلزم اعتمادك قبل مشاركتها.",
    "KNOWLEDGE_CONFLICT": "وجدت أكثر من معلومة فعالة لنفس الموضوع وتحتاج منك تحديد المعتمد.",
    "OBSERVE_ONLY": "وضع المراقبة مفعل؛ لم يُرسل أي رد.",
    "SAFE_AUTO": "الرد مستند إلى معلومات موثوقة ويسمح الإعداد الحالي بإرساله.",
    "SAFE_SOCIAL_REPLY": "الرسالة اجتماعية ولا تتضمن حقيقة تجارية أو التزامًا جديدًا.",
    "SAFE_CLARIFICATION": "يمكن طلب توضيح قصير دون ذكر معلومات تجارية غير مؤكدة.",
    "OWNER_REQUESTED": "العميل طلب التحدث مع المالك مباشرة.",
    "REFUND_DECISION": "العميل يطلب اعتماد استرجاع مبلغ، وهذا قرار مالي يحتاج موافقة المالك.",
    "UNAPPROVED_DISCOUNT": "العميل يطلب منح خصم غير موجود ضمن العروض المعتمدة.",
    "BINDING_COMMITMENT": "العميل يطلب التزامًا ملزمًا باسم المالك يحتاج قرارًا مباشرًا منه.",
    "PRIVATE_DATA_REQUEST": "العميل يطلب كشف بيانات خاصة لا يحق للسكرتير مشاركتها.",
    "SENSITIVE_ACTION": "العميل يطلب تنفيذ إجراء حساس باسم المالك.",
}

_INTENT_REVIEW_REASONS = {
    "REFUND_AUTHORIZATION": (
        "العميل يطلب اعتماد استرجاع مبلغ، وهذا قرار مالي يحتاج موافقة المالك."
    ),
    "DISCOUNT_REQUEST": "العميل يطلب منح خصم غير موجود ضمن العروض المعتمدة.",
    "BINDING_COMMITMENT": "العميل يطلب التزامًا ملزمًا باسم المالك يحتاج قرارًا مباشرًا منه.",
    "PRIVATE_DATA_REQUEST": "العميل يطلب كشف بيانات خاصة لا يحق للسكرتير مشاركتها.",
    "SENSITIVE_ACTION": "العميل يطلب تنفيذ إجراء حساس باسم المالك.",
    "REQUEST_OWNER": "العميل طلب التحدث مع المالك مباشرة.",
}

_POLICY_ACTIONS = {
    "REQUIRE_APPROVAL": "مراجعة المالك قبل الإرسال",
    "ESCALATE": "تحويل المحادثة للمالك",
    "GUIDE_ONLY": "توجيه أسلوب السكرتير فقط",
}

_POLICY_SCOPES = {
    "GLOBAL": "جميع المحادثات",
    "CONTACT": "شخص محدد",
    "INTENT": "نوع طلب محدد",
}

_MENU_ACTIONS = {
    "SEND_MESSAGE": "رد ثابت",
    "OPEN_URL": "فتح رابط",
    "HANDOFF": "تحويل للمتابعة الشخصية",
    "START_FLOW": "بدء إجراء منظم",
    "START_PAYMENT": "دفع آمن بنجوم Telegram",
}

_KNOWLEDGE_TYPES = {
    "GENERAL": "معلومة عامة",
    "SERVICE": "خدمة",
    "PRODUCT": "منتج",
    "PRICE": "سعر",
    "FAQ": "سؤال شائع",
    "POLICY": "سياسة",
    "EXAMPLE": "مثال معتمد",
    "CUSTOM": "معلومة مخصصة",
}


def decision_reason_text(reason_code: str, *, intent: str = "", risk: str = "") -> str:
    normalized_intent = canonicalize_intent(intent) if intent else ""
    if normalized_intent in _INTENT_REVIEW_REASONS:
        return _INTENT_REVIEW_REASONS[normalized_intent]
    if reason_code == "KNOWLEDGE_CONFLICT" and normalized_intent == "PRICING_INQUIRY":
        return "وجدت معلومات متعارضة عن السعر، وتحتاج منك تحديد السعر المعتمد."
    if reason_code == "NO_GROUNDING" and normalized_intent in {
        "PRICING_INQUIRY",
        "REFUND_INFORMATION",
        "DISCOUNT_INFORMATION",
        "FACTUAL_INFORMATION",
        "PRESALES_INTEREST",
        "PACKAGE_SELECTION",
        "HOW_TO",
        "TECHNICAL_SUPPORT",
    }:
        return "لا توجد معلومة موثقة كافية عن هذا الطلب، وأي جواب تفصيلي قد يكون غير دقيق."
    if reason_code.startswith("STATE_"):
        return "حالة المحادثة الحالية لا تسمح برد آلي."
    return _DECISION_REASONS.get(
        reason_code,
        "تحتاج الرسالة إلى مراجعتك قبل اتخاذ الإجراء المناسب.",
    )


def policy_action_text(action: str) -> str:
    return _POLICY_ACTIONS.get(action, "إجراء مخصص يحدده المالك")


def policy_scope_text(scope: str) -> str:
    return _POLICY_SCOPES.get(scope, "نطاق مخصص")


def menu_action_text(action: str) -> str:
    return _MENU_ACTIONS.get(action, "إجراء مخصص")


def knowledge_type_text(item_type: str | None) -> str:
    value = str(item_type or "").upper()
    return _KNOWLEDGE_TYPES.get(value, "معلومة مخصصة")


def knowledge_visibility_text(visibility: str | None) -> str:
    return {
        "PUBLIC": "🌍 عام — يمكن قوله للعميل",
        "INTERNAL": "🏠 داخلي — يوجّه السكرتير",
        "PRIVATE": "🔒 خاص — لا يُشارك مع خدمة الصياغة",
    }.get(str(visibility or "").upper(), "مستوى استخدام مخصص")


def relevance_text(score: float) -> str:
    if score >= 0.72:
        return "صلة قوية"
    if score >= 0.4:
        return "صلة جيدة"
    return "صلة محدودة"


def knowledge_source_text(source: str | None) -> str:
    value = (source or "").strip()
    if value.startswith("OWNER_BULK:"):
        name = value.split(":", 1)[-1].strip() or "مصدر جماعي"
        return f"تغذية جماعية — {name}"
    return {
        "OWNER_TELEGRAM": "إضافة مباشرة من المالك",
        "OWNER_BULK_IMPORT": "تغذية جماعية من المالك",
        "OWNER_APPROVAL_EDIT": "تعلّم صريح من تعديل المالك",
    }.get(value, value or "مصدر غير مسمى")
