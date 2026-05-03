"""Catalog sanity: shape, uniqueness, topological ordering.

Pure Python, no DB. Catches typos and accidental cycles before they can hit
the nightly materialization job.

Run: ``cd backend && uv run python -m pytest tests/ml/test_features_catalog.py -v``
"""

from __future__ import annotations

import pytest

from ml.features import catalog


def test_catalog_nonempty() -> None:
    """Signal Engine is useless without a populated catalog."""
    specs = catalog.iter_catalog()
    assert len(specs) >= 30, f"Catalog unexpectedly small: {len(specs)}"


def test_feature_keys_are_unique() -> None:
    """Every feature_key must appear at most once in the catalog."""
    keys = [s.key for s in catalog.iter_catalog()]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"Duplicate feature keys in catalog: {sorted(dupes)}"


def test_every_spec_has_required_fields() -> None:
    """Defensive: each spec must fully populate category, domain, version, builder_module."""
    for spec in catalog.iter_catalog():
        assert spec.key, f"Empty key in spec: {spec!r}"
        assert spec.category, f"{spec.key}: empty category"
        assert spec.domain, f"{spec.key}: empty domain"
        assert spec.version, f"{spec.key}: empty version"
        assert spec.builder_module, f"{spec.key}: empty builder_module"
        assert spec.description, f"{spec.key}: empty description"


def test_categories_are_from_the_allowed_set() -> None:
    """Catch typos like ``biomtric_raw``."""
    allowed = {
        "biometric_raw",
        "biometric_derived",
        "activity",
        "nutrition",
        "contextual",
        "data_quality",
    }
    for spec in catalog.iter_catalog():
        assert spec.category in allowed, (
            f"{spec.key} has unknown category {spec.category!r}; allowed: {sorted(allowed)}"
        )


def test_required_features_exist_in_catalog() -> None:
    """No feature may depend on a key that isn't registered."""
    all_keys = {s.key for s in catalog.iter_catalog()}
    for spec in catalog.iter_catalog():
        missing = [r for r in spec.requires if r not in all_keys]
        assert not missing, f"{spec.key} requires unknown key(s): {missing}"


def test_derived_suffix_dependencies_are_consistent() -> None:
    """Derived keys shaped like ``X.suffix`` should list ``X`` in requires."""
    for spec in catalog.iter_catalog():
        if "." in spec.key and spec.category in {"biometric_derived", "nutrition"}:
            parent = spec.key.rsplit(".", 1)[0]
            if parent in {s.key for s in catalog.iter_catalog()}:
                assert parent in spec.requires, (
                    f"{spec.key}: parent {parent} exists but is not in requires"
                )


def test_topological_order_places_parents_first() -> None:
    """The ordering must place every requires-target before its dependants."""
    ordered = catalog.topologically_ordered()
    seen: set[str] = set()
    for spec in ordered:
        for req in spec.requires:
            assert req in seen, (
                f"{spec.key} appears before its dependency {req!r} in topological order"
            )
        seen.add(spec.key)


def test_get_spec_returns_none_for_unknown_key() -> None:
    assert catalog.get_spec("this.is.not.a.feature") is None


def test_get_spec_returns_spec_for_known_key() -> None:
    spec = catalog.get_spec("hrv")
    assert spec is not None
    assert spec.category == "biometric_raw"
    assert spec.domain == "heart"


def test_specs_by_category_filters_correctly() -> None:
    raw = catalog.specs_by_category("biometric_raw")
    assert all(s.category == "biometric_raw" for s in raw)
    assert len(raw) >= 5


@pytest.mark.parametrize(
    "required_key",
    [
        "hrv",
        "resting_hr",
        "sleep_efficiency",
        "readiness_score",
        "steps",
        "protein_g",
        "weekday",
        "completeness_14d.biometric",
    ],
)
def test_core_features_present(required_key: str) -> None:
    """These features MUST exist in v1, downstream code relies on them."""
    assert catalog.get_spec(required_key) is not None, (
        f"Required feature {required_key!r} not in catalog"
    )
