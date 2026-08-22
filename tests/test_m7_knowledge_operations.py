from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import KnowledgeBatch, KnowledgeItem, Owner
from app.knowledge.admin import rollback_knowledge_batch, supersede_knowledge
from app.knowledge.bulk import (
    KnowledgeCandidate,
    save_bulk_candidates,
    source_content_hash,
)


def make_session() -> tuple[Session, Owner]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    owner = Owner(telegram_user_id=701, display_name="Owner")
    session.add(owner)
    session.flush()
    return session, owner


def test_bulk_source_is_grouped_and_duplicate_import_is_blocked() -> None:
    session, owner = make_session()
    source = "الباقة الأساسية سعرها 30 ريالًا"
    candidates = [KnowledgeCandidate(type="PRICE", title="الباقة الأساسية", content=source)]
    source_hash = source_content_hash(source)

    first = save_bulk_candidates(
        session,
        owner=owner,
        candidates=candidates,
        visibility="PUBLIC",
        source="OWNER_BULK:test",
        source_hash=source_hash,
        source_name="اختبار",
    )
    second = save_bulk_candidates(
        session,
        owner=owner,
        candidates=candidates,
        visibility="PUBLIC",
        source="OWNER_BULK:test",
        source_hash=source_hash,
        source_name="اختبار",
    )

    assert len(first.item_ids) == 1
    assert second.duplicate_of_batch_id == first.batch_id
    assert second.item_ids == ()
    assert session.get(KnowledgeItem, first.item_ids[0]).batch_id == first.batch_id


def test_knowledge_edit_creates_a_new_version() -> None:
    session, owner = make_session()
    row = KnowledgeItem(
        owner_id=owner.id,
        type="POLICY",
        title="سياسة الاسترجاع",
        content="سبعة أيام",
        visibility="PUBLIC",
        version=1,
    )
    session.add(row)
    session.flush()

    replacement = supersede_knowledge(
        session,
        owner_id=owner.id,
        knowledge_id=row.id,
        content="أربعة عشر يومًا",
    )

    assert replacement is not None
    assert row.status == "SUPERSEDED"
    assert replacement.status == "ACTIVE"
    assert replacement.version == 2
    assert replacement.supersedes_id == row.id


def test_batch_rollback_only_disables_its_active_items() -> None:
    session, owner = make_session()
    batch = KnowledgeBatch(
        owner_id=owner.id,
        source_name="دفعة اختبار",
        visibility="PUBLIC",
        content_hash="a" * 64,
        item_count=1,
    )
    session.add(batch)
    session.flush()
    batched = KnowledgeItem(
        owner_id=owner.id,
        type="FAQ",
        title="ضمن الدفعة",
        content="محتوى",
        visibility="PUBLIC",
        batch_id=batch.id,
    )
    independent = KnowledgeItem(
        owner_id=owner.id,
        type="FAQ",
        title="مستقلة",
        content="تبقى فعالة",
        visibility="PUBLIC",
    )
    session.add_all([batched, independent])
    session.flush()

    removed = rollback_knowledge_batch(session, owner_id=owner.id, batch_id=batch.id)

    assert removed == 1
    assert batched.status == "ROLLED_BACK"
    assert independent.status == "ACTIVE"
    assert batch.status == "ROLLED_BACK"
