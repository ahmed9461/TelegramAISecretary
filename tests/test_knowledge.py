from app.db.enums import Visibility
from app.knowledge.service import KnowledgeRecord


def test_only_public_knowledge_is_quotable() -> None:
    public = KnowledgeRecord("1", "x", "public", Visibility.PUBLIC)
    internal = KnowledgeRecord("2", "y", "internal", Visibility.INTERNAL)
    assert public.can_quote_to_contact()
    assert not internal.can_quote_to_contact()
