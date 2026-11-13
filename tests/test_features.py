from collections import Counter

import pytest

from asof.features import cosine, jaccard
from asof.sections import cosine_similarity, jaccard_similarity, tokens


def test_feature_similarity_matches_text_similarity() -> None:
    a = "Our supply chain risks increased because of tariffs and labor shortages."
    b = "Our supply chain risks decreased because of new suppliers and tariffs."
    ca, cb = dict(Counter(tokens(a))), dict(Counter(tokens(b)))
    assert cosine(ca, cb) == pytest.approx(cosine_similarity(a, b))
    assert jaccard(ca, cb) == pytest.approx(jaccard_similarity(a, b))


def test_missing_features_are_nan() -> None:
    import math

    assert math.isnan(cosine(None, {"a": 1}))
    assert math.isnan(jaccard({}, {"a": 1}))
