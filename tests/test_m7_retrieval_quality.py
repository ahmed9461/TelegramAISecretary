import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import Visibility
from app.db.models import KnowledgeItem, Owner
from app.knowledge.retrieval import normalize_search_text, retrieve_knowledge


def make_session() -> tuple[Session, Owner]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    owner = Owner(telegram_user_id=700, display_name="Owner")
    session.add(owner)
    session.flush()
    return session, owner


def test_arabic_normalization_handles_diacritics_and_alef_variants() -> None:
    assert normalize_search_text("أَسْعَار الإشتراك") == "اسعار الاشتراك"


def test_retrieval_eval_routes_price_policy_and_payment_questions() -> None:
    session, owner = make_session()
    session.add_all(
        [
            KnowledgeItem(
                owner_id=owner.id,
                type="PRICE",
                title="أسعار الاشتراك",
                content="سعر الباقة الأساسية 30 ريالًا.",
                visibility=Visibility.PUBLIC.value,
                tags_json=["تكلفة", "رسوم"],
            ),
            KnowledgeItem(
                owner_id=owner.id,
                type="POLICY",
                title="سياسة الإلغاء والاسترجاع",
                content="يمكن طلب الاسترجاع خلال سبعة أيام.",
                visibility=Visibility.PUBLIC.value,
                tags_json=["شروط"],
            ),
            KnowledgeItem(
                owner_id=owner.id,
                type="FAQ",
                title="طرق الدفع",
                content="الدفع متاح عبر التحويل أو نجوم Telegram.",
                visibility=Visibility.PUBLIC.value,
                tags_json=["سداد"],
            ),
        ]
    )
    session.commit()

    cases = {
        "كم تكلفة الاشتراك؟": "أسعار الاشتراك",
        "ما شروط استرجاع المبلغ؟": "سياسة الإلغاء والاسترجاع",
        "كيف يمكنني السداد؟": "طرق الدفع",
    }
    for query, expected_title in cases.items():
        hits = retrieve_knowledge(session, owner_id=owner.id, query=query)
        assert hits
        assert hits[0].title == expected_title
        assert hits[0].source is None


def test_retrieval_excludes_private_and_expired_items() -> None:
    session, owner = make_session()
    now = datetime.now(UTC)
    session.add_all(
        [
            KnowledgeItem(
                owner_id=owner.id,
                type="PRICE",
                title="السعر الحالي",
                content="السعر الحالي 50 ريالًا.",
                visibility=Visibility.PUBLIC.value,
            ),
            KnowledgeItem(
                owner_id=owner.id,
                type="PRICE",
                title="السعر القديم",
                content="السعر القديم 10 ريالات.",
                visibility=Visibility.PUBLIC.value,
                valid_until=now - timedelta(days=1),
            ),
            KnowledgeItem(
                owner_id=owner.id,
                type="CUSTOM",
                title="ملاحظة خاصة",
                content="السعر السري 999 ريالًا.",
                visibility=Visibility.PRIVATE.value,
            ),
        ]
    )
    session.commit()

    hits = retrieve_knowledge(session, owner_id=owner.id, query="ما السعر؟", now=now)

    assert [hit.title for hit in hits] == ["السعر الحالي"]


def test_retrieval_marks_conflicting_active_facts() -> None:
    session, owner = make_session()
    session.add_all(
        [
            KnowledgeItem(
                owner_id=owner.id,
                type="PRICE",
                title="سعر الباقة الأساسية",
                content="السعر 30 ريالًا.",
                visibility=Visibility.PUBLIC.value,
            ),
            KnowledgeItem(
                owner_id=owner.id,
                type="PRICE",
                title="سعر الباقة الأساسية",
                content="السعر 45 ريالًا.",
                visibility=Visibility.PUBLIC.value,
            ),
        ]
    )
    session.commit()

    hits = retrieve_knowledge(session, owner_id=owner.id, query="سعر الباقة الأساسية")

    assert len(hits) == 2
    assert all(hit.has_conflict for hit in hits)
    assert hits[0].conflict_ids == (hits[1].id,)


def test_retrieval_quality_dataset_passes_top_one_gate() -> None:
    dataset_path = Path(__file__).parents[1] / "evals" / "m7_retrieval_cases.json"
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    session, owner = make_session()
    for item in payload["knowledge"]:
        session.add(
            KnowledgeItem(
                owner_id=owner.id,
                type=item["type"],
                title=item["title"],
                content=item["content"],
                visibility=Visibility.PUBLIC.value,
                tags_json=item.get("tags", []),
            )
        )
    session.commit()

    for case in payload["cases"]:
        hits = retrieve_knowledge(session, owner_id=owner.id, query=case["query"], limit=1)
        actual = hits[0].title if hits else None
        assert actual == case["expected_title"], case["query"]
