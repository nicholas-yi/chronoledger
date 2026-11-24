
import pytest

from asof.periods import HoldoutAccessError


def test_feature_build_checks_dates_before_client_or_cached_skip(monkeypatch) -> None:
    from asof import features

    monkeypatch.setattr(features, "feature_path", lambda _: pytest.fail("no source lookup"))
    with pytest.raises(HoldoutAccessError):
        features.build([(1, "fake", "a.htm", "10-K")])


