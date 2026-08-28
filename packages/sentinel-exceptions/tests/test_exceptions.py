"""Tests for sentinel-exceptions."""
import pytest

from sentinel_exceptions import (
    BudgetExceeded,
    SentraAuraException,
    get_status_code,
)


def test_base_exception_to_dict():
    exc = SentraAuraException("test", error_code="TEST", trace_id="t1")
    d = exc.to_dict()
    assert d["error_code"] == "TEST"
    assert d["trace_id"] == "t1"


def test_domain_exception_status_code():
    exc = BudgetExceeded("over budget")
    assert exc.error_code == "BUDGET_EXCEEDED"
    assert get_status_code(exc) == 402
