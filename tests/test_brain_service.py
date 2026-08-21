from app.brain.models import BusinessProfile, ContactMemory, ResponsePolicy
from app.brain.service import memory_for_ai, policies_for_ai, profile_for_ai


def test_private_contact_notes_never_enter_ai_context() -> None:
    memory = ContactMemory(
        owner_id=1,
        contact_id=2,
        summary="عميل مهتم بالخدمة",
        facts_json={"interest": "automation"},
        preferences_json={"reply_style": "short"},
        private_notes="OWNER ONLY SECRET",
        share_with_ai=True,
    )

    payload = memory_for_ai(memory, contact_memory_allowed=True)

    assert payload["summary"] == "عميل مهتم بالخدمة"
    assert "private_notes" not in payload
    assert "OWNER ONLY SECRET" not in str(payload)


def test_memory_can_be_disabled_per_contact() -> None:
    memory = ContactMemory(
        owner_id=1,
        contact_id=2,
        summary="should not leave database",
        facts_json={},
        preferences_json={},
        private_notes="",
        share_with_ai=True,
    )
    assert memory_for_ai(memory, contact_memory_allowed=False) == {}


def test_profile_is_business_agnostic_and_extensible() -> None:
    profile = BusinessProfile(
        owner_id=1,
        display_name="Example",
        activity_description="أي نشاط يمكن تغييره لاحقًا",
        industry="CUSTOM",
        reply_style="مختصر",
        language="AUTO",
        tone="ودود",
        custom_instructions="لا تخترع معلومات",
        extras_json={"future_field": "works without schema change"},
        is_active=True,
    )
    payload = profile_for_ai(profile)
    assert payload["extras"]["future_field"] == "works without schema change"


def test_enabled_response_policy_is_serialized_as_guidance() -> None:
    policy = ResponsePolicy(
        id=7,
        owner_id=1,
        name="قاعدة مرنة",
        description="عند حالة معينة اطلب موافقة",
        scope="GLOBAL",
        action="REQUIRE_APPROVAL",
        priority=100,
        conditions_json={"natural_language": "حالة معينة"},
        constraints_json={},
        enabled=True,
    )
    payload = policies_for_ai([policy])
    assert payload[0]["id"] == 7
    assert payload[0]["action"] == "REQUIRE_APPROVAL"
