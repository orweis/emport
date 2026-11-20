from __future__ import annotations

import sys
import warnings

import pytest

import emport
from emport import PyFrame, StackDepthError, co_to_dict, get_caller, get_caller_module

EXPECTED_KEYS = {
    "co_argcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_consts",
    "co_names",
    "co_varnames",
    "co_filename",
    "co_name",
    "co_firstlineno",
    "co_lnotab",
}


def sample(a, b=2):
    secret = "literal-value"
    return a, b, secret


class TestCoToDict:
    def test_keys_and_values(self):
        d = co_to_dict(sample.__code__)
        assert set(d) == EXPECTED_KEYS
        assert d["co_name"] == "sample"
        assert d["co_argcount"] == 2
        assert d["co_varnames"][:3] == ("a", "b", "secret")
        assert d["co_filename"] == __file__
        assert "literal-value" in d["co_consts"]

    def test_no_deprecation_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            co_to_dict(sample.__code__)

    def test_missing_co_lnotab_yields_none(self):
        class FakeCode:
            co_argcount = co_nlocals = co_stacksize = co_flags = co_firstlineno = 0
            co_consts = co_names = co_varnames = ()
            co_filename = "f"
            co_name = "n"

        assert co_to_dict(FakeCode())["co_lnotab"] is None


def outer_caller():
    return middle_caller()


def middle_caller():
    return {
        "d0": get_caller()["co_name"],
        "d1": get_caller(1)["co_name"],
        "d2": get_caller(2)["co_name"],
        "neg": get_caller(-1)["co_name"],
    }


class TestGetCaller:
    def test_depth_semantics(self):
        result = outer_caller()
        assert result == {
            "d0": "get_caller",
            "d1": "middle_caller",
            "d2": "outer_caller",
            "neg": "get_caller",
        }

    def test_depth_beyond_stack(self):
        with pytest.raises(StackDepthError):
            get_caller(10_000)

    def test_depth_beyond_stack_is_backward_compatible(self):
        with pytest.raises(AttributeError):
            get_caller(10_000)


class TestGetCallerModule:
    def test_depth_zero_is_emport(self):
        assert get_caller_module() is emport

    def test_depth_one_is_calling_module(self):
        assert get_caller_module(1) is sys.modules[__name__]

    def test_depth_beyond_stack(self):
        with pytest.raises(StackDepthError):
            get_caller_module(10_000)


def test_pyframe_yields_enclosing_frame():
    def inner():
        with PyFrame() as frame:
            return frame.f_code.co_name

    assert inner() == "inner"
