from __future__ import annotations

import sys

import pytest

import emport
from emport import Emport, InvalidImportPathError, emport_by_class, emport_objects_by_class
from tests.conftest import Base


def _names(members):
    return sorted(m.__name__ for m in members)


class TestEmportByClass:
    def test_returns_emport_wrapping_the_imported_package(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert isinstance(result, Emport)
        assert result.get_original_module() is sys.modules[plugin_package]

    def test_direct_matches_exposed_as_attributes(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert result.TopPlugin.__name__ == "TopPlugin"
        assert not hasattr(result, "Unrelated")

    def test_base_class_itself_is_excluded(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert not hasattr(result, "Base")
        assert Base not in result.get_flat_list()

    def test_submodules_become_nested_emports(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert isinstance(result.alpha, Emport)
        assert result.alpha.AlphaPlugin.__name__ == "AlphaPlugin"
        assert not hasattr(result.alpha, "AlphaHelper")
        assert _names(result.beta.get_members_list()) == ["BetaChild", "BetaPlugin"]

    def test_submodules_without_matches_are_dropped(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert not hasattr(result, "gamma")

    def test_private_modules_not_imported_by_star(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert "PrivatePlugin" not in _names(result.get_flat_list())
        assert plugin_package + "._private" not in sys.modules

    def test_flat_list_contains_all_matches(self, plugin_package):
        result = emport_by_class(plugin_package, Base)
        assert _names(result.get_flat_list()) == [
            "AlphaPlugin",
            "BetaChild",
            "BetaPlugin",
            "TopPlugin",
        ]

    def test_filter_by_intermediate_class(self, plugin_package):
        beta = __import__(plugin_package + ".beta", fromlist=["*"])
        result = emport_by_class(plugin_package, beta.BetaPlugin)
        assert _names(result.get_flat_list()) == ["BetaChild"]

    def test_explicit_import_items(self, plugin_package):
        # Only "alpha" is requested; __all__ is ignored for the fromlist.
        result = emport_by_class(plugin_package, Base, ["alpha"])
        assert plugin_package + ".beta" not in sys.modules
        assert _names(result.get_flat_list()) == ["AlphaPlugin", "TopPlugin"]

    def test_import_submodule_path(self, plugin_package):
        result = emport_by_class(plugin_package + ".beta", Base)
        assert _names(result.get_flat_list()) == ["BetaChild", "BetaPlugin"]
        # the leaf module is returned, not the top-level package
        assert result.get_original_module().__name__ == plugin_package + ".beta"

    def test_only_one_level_of_nesting(self, make_package):
        pkg = make_package(
            {
                "__init__.py": "__all__ = ['sub']\n",
                "sub/__init__.py": "from . import deep\n",
                "sub/deep.py": "from tests.conftest import Base\nclass Deep(Base):\n    pass\n",
            }
        )
        result = emport_by_class(pkg, Base)
        assert result.get_flat_list() == []

    def test_missing_module_raises(self):
        with pytest.raises(ModuleNotFoundError):
            emport_by_class("emport_no_such_module_xyz", Base)


class TestEmportObjectsByClass:
    def test_returns_name_class_tuples(self, plugin_package):
        result = emport_objects_by_class(plugin_package, Base)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
        names = [name for name, _ in result]
        assert names[0] == "TopPlugin"  # direct matches come first
        assert sorted(names) == ["AlphaPlugin", "BetaChild", "BetaPlugin", "TopPlugin"]
        for name, obj in result:
            assert obj.__name__ == name

    def test_class_reachable_twice_is_listed_twice(self, make_package):
        pkg = make_package(
            {
                "__init__.py": "from .mod import Plugin\n__all__ = ['mod']\n",
                "mod.py": "from tests.conftest import Base\nclass Plugin(Base):\n    pass\n",
            }
        )
        names = [name for name, _ in emport_objects_by_class(pkg, Base)]
        assert names == ["Plugin", "Plugin"]


@pytest.mark.parametrize("func", [emport_by_class, emport_objects_by_class])
class TestImportPathValidation:
    @pytest.mark.parametrize("bad", ["", ".relative", "..up", "a..b", "trailing."])
    def test_malformed_paths_rejected(self, func, bad):
        with pytest.raises(InvalidImportPathError):
            func(bad, Base)

    def test_error_is_backward_compatible(self, func):
        # Earlier versions surfaced these as ValueError / ModuleNotFoundError.
        with pytest.raises(ValueError):
            func("", Base)
        with pytest.raises(ModuleNotFoundError):
            func(".x", Base)

    def test_non_string_rejected(self, func):
        with pytest.raises(TypeError):
            func(None, Base)

    def test_allowed_prefixes_permits_matching(self, func, plugin_package):
        assert func(plugin_package, Base, allowed_prefixes=[plugin_package])
        assert func(plugin_package + ".alpha", Base, allowed_prefixes=(plugin_package,))
        assert func(plugin_package, Base, allowed_prefixes=plugin_package)

    def test_allowed_prefixes_blocks_before_importing(self, func, make_package, tmp_path):
        marker = tmp_path / "executed"
        pkg = make_package({"__init__.py": "open(%r, 'w').close()\n" % str(marker)})
        with pytest.raises(InvalidImportPathError):
            func(pkg, Base, allowed_prefixes=["some_other_pkg"])
        assert not marker.exists()
        assert pkg not in sys.modules

    def test_allowed_prefixes_is_not_a_plain_string_prefix(self, func, plugin_package):
        # "pkg" must not allow "pkg_evil"
        with pytest.raises(InvalidImportPathError):
            func(plugin_package, Base, allowed_prefixes=[plugin_package[:-1]])

    def test_allowed_prefixes_is_keyword_only(self, func, plugin_package):
        with pytest.raises(TypeError):
            func(plugin_package, Base, None, [plugin_package])


def test_version_is_exposed():
    assert emport.__version__ == "0.2.0"
