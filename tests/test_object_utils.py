from __future__ import annotations

import types

import pytest

from emport import Emport, ObjectUtils


class A:
    pass


class B(A):
    pass


class C(B):
    pass


class Mixin:
    pass


class D(Mixin, A):
    pass


class TestIsDerivedOf:
    @pytest.mark.parametrize(
        ("child", "parent", "expected"),
        [
            (B, A, True),
            (C, A, True),
            (D, A, True),
            (D, Mixin, True),
            (A, B, False),
            (A, A, True),  # a class counts as derived of itself
            (Mixin, A, False),
        ],
    )
    def test_classes(self, child, parent, expected):
        assert ObjectUtils.is_derived_of(child, parent) is expected

    @pytest.mark.parametrize("obj", [B(), 1, "str", None, lambda: None])
    def test_non_classes_return_false(self, obj):
        assert ObjectUtils.is_derived_of(obj, A) is False


class TestGetProperties:
    def test_non_callable_attributes_without_dunders(self):
        class Thing:
            number = 1
            _protected = "p"
            __mangled = "m"

            def method(self):
                return None

            @staticmethod
            def static():
                return None

        thing = Thing()
        thing.instance_attr = [1, 2]
        props = ObjectUtils.get_properties(thing)
        assert props == {
            "number": 1,
            "_protected": "p",
            "_Thing__mangled": "m",  # mangled name does not start with "__"
            "instance_attr": [1, 2],
        }

    def test_callable_instances_are_excluded(self):
        class CallableObj:
            def __call__(self):
                return None

        holder = types.SimpleNamespace(fn=CallableObj(), value=3, cls=A)
        assert ObjectUtils.get_properties(holder) == {"value": 3}

    def test_works_on_modules(self):
        module = types.ModuleType("m")
        module.X = 5
        module.f = len
        assert ObjectUtils.get_properties(module) == {"X": 5}


class TestMemberFilters:
    def test_get_members_who_are_instance_of(self):
        ns = types.SimpleNamespace(a=A(), b=B(), c=C(), other=1)
        names = [name for name, _ in ObjectUtils.get_members_who_are_instance_of(ns, B)]
        assert names == ["b", "c"]  # sorted, subclasses included

    def test_get_class_members_who_derive_of_excludes_parent(self):
        ns = types.SimpleNamespace(A=A, B=B, C=C, D=D, Mixin=Mixin, instance=B())
        result = ObjectUtils.get_class_members_who_derive_of(ns, A)
        assert result == [("B", B), ("C", C), ("D", D)]

    def test_get_class_members_who_derive_of_no_match(self):
        ns = types.SimpleNamespace(Mixin=Mixin)
        assert ObjectUtils.get_class_members_who_derive_of(ns, A) == []


class TestEmport:
    def test_members_and_attributes(self):
        module = types.ModuleType("fake")
        e = Emport(module, [("B", B), ("C", C)])
        assert e.B is B and e.C is C
        assert e.get_members_list() == [B, C]
        assert e.get_original_module() is module

    def test_flat_list_flattens_recursively(self):
        inner_most = Emport("x", [("D", D)])
        inner = Emport("y", [("C", C), ("deep", inner_most)])
        outer = Emport("z", [("B", B), ("sub", inner)])
        assert outer.get_flat_list() == [B, C, D]

    def test_flat_list_robust_to_shadowed_method_in_nested(self):
        inner = Emport("y", [("get_flat_list", C)])
        assert inner.get_flat_list is C  # historical shadowing behaviour
        outer = Emport("z", [("sub", inner)])
        assert outer.get_flat_list() == [C]

    def test_empty(self):
        e = Emport("mod", [])
        assert e.get_members_list() == []
        assert e.get_flat_list() == []

    def test_repr(self):
        assert repr(Emport("mymod", [])) == "EMPORT - mymod"
        assert repr(Emport(("tuple", 1), [])) == "EMPORT - ('tuple', 1)"
