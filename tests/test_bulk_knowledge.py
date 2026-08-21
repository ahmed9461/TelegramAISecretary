from app.knowledge.bulk import normalize_candidates


def test_bulk_candidates_are_normalized_and_deduplicated() -> None:
    items = normalize_candidates(
        [
            {
                "type": "price",
                "title": "الباقة الشهرية",
                "content": "السعر 10 دولار والمدة 30 يومًا.",
                "tags": ["اشتراك", "سعر"],
            },
            {
                "type": "PRICE",
                "title": "الباقة الشهرية",
                "content": "السعر 10 دولار والمدة 30 يومًا.",
                "tags": ["مكرر"],
            },
            {
                "type": "unexpected",
                "title": "طريقة الدفع",
                "content": "الدفع عبر التحويل البنكي.",
                "tags": [],
            },
            {"type": "GENERAL", "title": "", "content": "ignored"},
        ]
    )

    assert len(items) == 2
    assert items[0].type == "PRICE"
    assert items[0].tags == ("اشتراك", "سعر")
    assert items[1].type == "CUSTOM"
