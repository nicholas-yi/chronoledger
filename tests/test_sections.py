import math

from asof.sections import cosine_similarity, extract_sections, html_to_text, jaccard_similarity

BODY_RISK = "Our business faces supply risk. " * 30
BODY_MDA = "Revenue grew because of demand. " * 30
DOC = f"""
<html><body>
<p>TABLE OF CONTENTS</p>
<p>Item 1. Business</p><p>Item 1A. Risk Factors</p><p>Item 7. Management's Discussion</p>
<p>Item 8. Financial Statements</p>
<p>PART I</p>
<p>Item 1. Business</p><p>{"We make widgets. " * 30}</p>
<p>Item 1A. Risk Factors</p><p>{BODY_RISK}</p>
<p>Item 2. Properties</p><p>We lease offices.</p>
<p>Item 7. Management's Discussion and Analysis</p><p>{BODY_MDA}</p>
<p>Item 8. Financial Statements</p><p>See below.</p>
<div style="display:none">Item 1A. hidden duplicate header</div>
</body></html>
"""


def test_skips_table_of_contents_and_hidden_text() -> None:
    sections = extract_sections(html_to_text(DOC))
    assert set(sections) == {"1", "1A", "7"}
    assert "supply risk" in sections["1A"].text
    assert "Properties" not in sections["1A"].text
    assert "demand" in sections["7"].text
    assert "hidden" not in sections["1A"].text


def test_offsets_point_into_text() -> None:
    text = html_to_text(DOC)
    sec = extract_sections(text)["1A"]
    assert text[sec.start:sec.end] == sec.text


def test_similarity_bounds() -> None:
    assert math.isclose(cosine_similarity("a risk b", "a risk b"), 1.0)
    assert cosine_similarity("alpha beta", "gamma delta") == 0.0
    assert 0.0 < jaccard_similarity("alpha beta", "alpha gamma") < 1.0
    assert math.isnan(cosine_similarity("", "x y"))
