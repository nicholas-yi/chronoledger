from asof.claim_verifier import verify_claim
from asof.reader_fields import DISPUTED_OR_NONASSERTED, text_integrity_issues
from asof.text_normalization import normalize_filing_text

CLAIM = "FictionTest's 2016 revenue was 18 USD million."
FACT = "FictionTest reported revenue of 18 USD million for 2016."


def test_cp1252_artifacts_and_invisible_formatting_are_repaired_and_counted():
    raw = "Net sales \x93grew\x94 \x96 see \x95 note\x99 and re\u200bstated vi\u00adsible\ufeff text"
    text, counts = normalize_filing_text(raw)
    assert text == "Net sales \u201cgrew\u201d \u2013 see \u2022 note\u2122 and restated visible text"
    assert counts == {"cp1252_c1_repaired": 5, "invisible_format_removed": 3}
    assert not text_integrity_issues(text) and normalize_filing_text(text) == (text, {})


def test_undefined_c1_and_bidi_controls_survive_so_the_strict_verifier_still_defers():
    text, counts = normalize_filing_text("A\x81B \u202eC")
    assert text == "A\x81B \u202eC" and counts == {"c1_undefined_kept": 1}
    assert text_integrity_issues(text)
    assert verify_claim(f"{FACT} \u202eThe board met.", CLAIM)["verdict"] == "review"


def test_normalization_never_turns_a_hidden_blocking_word_into_support():
    for raw in (f"{FACT} Figures were re\u200bstated.", f"{FACT} That figure is in\u00adcorrect."):
        assert verify_claim(raw, CLAIM)["verdict"] == "review"
        assert verify_claim(normalize_filing_text(raw)[0], CLAIM)["verdict"] == "review"
    benign = f"{FACT} The board met in Lon\u200bdon on \x93Tuesday\x94."
    assert verify_claim(benign, CLAIM)["verdict"] == "review"
    assert verify_claim(normalize_filing_text(benign)[0], CLAIM)["verdict"] == "supported"


def test_allegation_vocabulary_no_longer_matches_issuer_names_with_the_same_stem():
    for word in ("allege", "alleged", "allegedly", "alleges", "alleging", "allegation", "allegations"):
        assert DISPUTED_OR_NONASSERTED.search(f"The {word} item.")
    for name in ("Allegro", "Allegheny", "Allegion", "Allegiant"):
        assert DISPUTED_OR_NONASSERTED.search(f"{name} Corp reported results.") is None


def test_imagine_forms_still_block_but_imaging_businesses_do_not():
    for word in ("Imagine", "imagined", "imagines", "imagining", "imaginary"):
        assert DISPUTED_OR_NONASSERTED.search(f"{word} this scenario-free sentence.")
    assert DISPUTED_OR_NONASSERTED.search("Imaging segment sales rose.") is None
