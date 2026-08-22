from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.enums import Visibility
from app.db.models import KnowledgeItem, Owner
from app.knowledge.retrieval import retrieve_knowledge

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "m7_retrieval_cases.json"


def main() -> int:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    failures: list[str] = []

    with Session(engine, expire_on_commit=False) as session:
        owner = Owner(telegram_user_id=700_007, display_name="M7 retrieval evaluation")
        session.add(owner)
        session.flush()
        for item in payload["knowledge"]:
            session.add(
                KnowledgeItem(
                    owner_id=owner.id,
                    type=item["type"],
                    title=item["title"],
                    content=item["content"],
                    visibility=Visibility.PUBLIC.value,
                    tags_json=item.get("tags", []),
                    source="M7_EVALUATION",
                )
            )
        session.commit()

        for case in payload["cases"]:
            hits = retrieve_knowledge(session, owner_id=owner.id, query=case["query"], limit=1)
            actual = hits[0].title if hits else None
            if actual != case["expected_title"]:
                failures.append(
                    f"query={case['query']!r} expected={case['expected_title']!r} actual={actual!r}"
                )

    total = len(payload["cases"])
    passed = total - len(failures)
    print(f"M7 retrieval evaluation: {passed}/{total} top-1 cases passed")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
