"""E20–E21a / E20a–E20c — canon-json-v1 digest contract."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.personnel_intake.domain.reconciliation.digest import (
    DIGEST_ALGORITHM_CANON_JSON_V1,
    CanonJsonV1DigestBuilder,
    DigestBuilderRegistry,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError


@pytest.fixture
def builder() -> CanonJsonV1DigestBuilder:
    return CanonJsonV1DigestBuilder()


def test_e20_golden_vectors(builder: CanonJsonV1DigestBuilder) -> None:
    assert builder.version == DIGEST_ALGORITHM_CANON_JSON_V1
    assert builder.canonical_json({}) == "{}"
    assert (
        builder.payload_digest({})
        == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )

    assert builder.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert (
        builder.payload_digest({"b": 1, "a": 2})
        == "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )

    # Recursive exclude_none omits null dict entries; list nulls preserved.
    assert builder.canonical_json({"a": None, "b": 1}) == '{"b":1}'
    assert (
        builder.payload_digest({"a": None, "b": 1})
        == "eb8ed3ccb5023093b56f490a46501e88d09736687e609fdbc1c71b3df8b9ccd3"
    )
    nested = {"nested": {"z": None, "y": [1, None, 2]}, "x": True}
    assert builder.canonical_json(nested) == '{"nested":{"y":[1,null,2]},"x":true}'
    assert (
        builder.payload_digest(nested)
        == "17ec1ce14adaf07c65861ce2374f522c64de21eae5b9c5ffa49f2c33016c70ff"
    )


def test_e20a_non_finite_float_rejected(builder: CanonJsonV1DigestBuilder) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        builder.payload_digest({"v": float("nan")})
    assert exc.value.code == "INVALID_DIGEST_INPUT"

    with pytest.raises(ReconciliationValidationError) as exc:
        builder.payload_digest({"v": float("inf")})
    assert exc.value.code == "INVALID_DIGEST_INPUT"


def test_e20b_non_string_dict_keys_rejected(builder: CanonJsonV1DigestBuilder) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        builder.payload_digest({1: "x"})
    assert exc.value.code == "INVALID_DIGEST_INPUT"

    with pytest.raises(ReconciliationValidationError) as exc:
        builder.payload_digest({("a",): 1})
    assert exc.value.code == "INVALID_DIGEST_INPUT"


def test_e20c_unsupported_values_rejected(builder: CanonJsonV1DigestBuilder) -> None:
    for value in (datetime(2026, 7, 24), Decimal("1.5"), b"bytes", object()):
        with pytest.raises(ReconciliationValidationError) as exc:
            builder.payload_digest({"v": value})
        assert exc.value.code == "INVALID_DIGEST_INPUT"


def test_e21_claim_mismatch(builder: CanonJsonV1DigestBuilder) -> None:
    with pytest.raises(ReconciliationValidationError) as exc:
        builder.verify_or_compute({"a": 1}, "0" * 64)
    assert exc.value.code == "PLUGIN_DIGEST_MISMATCH"


def test_e21a_null_claim_computes(builder: CanonJsonV1DigestBuilder) -> None:
    digest = builder.verify_or_compute({"a": 1}, None)
    assert digest == builder.payload_digest({"a": 1})
    assert len(digest) == 64


def test_registry_unsupported_version() -> None:
    registry = DigestBuilderRegistry()
    with pytest.raises(ReconciliationValidationError) as exc:
        registry.resolve("canon-json-v2")
    assert exc.value.code == "UNSUPPORTED_DIGEST_ALGORITHM"
