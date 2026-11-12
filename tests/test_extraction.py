from asof.extraction import Link, candidate_chunks, ground

CHUNK = (
    "Sales to Veltrona Systems accounted for 14% of our total net revenue in fiscal 2024. "
    "We compete with Orbique Labs."
)


def test_grounded_link_accepted() -> None:
    link = Link("Veltrona Systems", "customer", 14.0,
                "Sales to Veltrona Systems accounted for 14% of our total net revenue in fiscal 2024.")
    assert ground(link, CHUNK) is None


def test_whitespace_and_case_insensitive() -> None:
    link = Link("veltrona  systems", "customer", None,
                "sales to Veltrona Systems   accounted for 14% of our total net revenue")
    assert ground(link, CHUNK) is None


def test_fabricated_evidence_rejected() -> None:
    link = Link("Veltrona Systems", "customer", 14.0, "Veltrona Systems is our largest customer.")
    assert ground(link, CHUNK) == "evidence_not_in_source"


def test_partner_from_prior_knowledge_rejected() -> None:
    # The model names a real-world company that the quote does not mention.
    link = Link("Apple", "customer", None, "We compete with Orbique Labs.")
    assert ground(link, CHUNK) == "partner_not_in_evidence"


def test_wrong_percentage_rejected() -> None:
    link = Link("Veltrona Systems", "customer", 41.0,
                "Sales to Veltrona Systems accounted for 14% of our total net revenue in fiscal 2024.")
    assert ground(link, CHUNK) == "pct_not_in_evidence"


def test_candidate_chunks_keep_only_relevant_sentences() -> None:
    text = "We were founded in 1999. " + CHUNK + " Our headquarters are in Ohio."
    chunks = candidate_chunks(text)
    assert len(chunks) == 1
    assert "Veltrona" in chunks[0] and "Ohio" not in chunks[0]
