from __future__ import annotations

import importlib
import sys
import textwrap
import uuid
from pathlib import Path

import pytest


class Base:
    """Base class plugins in the generated fixture package derive from."""


@pytest.fixture
def make_package(tmp_path, monkeypatch):
    """Create a throw-away package on ``sys.path``.

    ``make_package({"__init__.py": "...", "mod.py": "..."})`` returns the
    (unique) package name. Imported modules are removed from ``sys.modules``
    afterwards so tests stay independent.
    """
    monkeypatch.syspath_prepend(str(tmp_path))
    created: list[str] = []

    def _make(files: dict[str, str], name: str | None = None) -> str:
        pkg_name = name or "emport_fixture_%s" % uuid.uuid4().hex[:8]
        pkg_dir = tmp_path / pkg_name
        pkg_dir.mkdir()
        for rel, source in files.items():
            target = pkg_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(textwrap.dedent(source))
        created.append(pkg_name)
        importlib.invalidate_caches()
        return pkg_name

    yield _make

    for mod_name in list(sys.modules):
        if any(mod_name == p or mod_name.startswith(p + ".") for p in created):
            del sys.modules[mod_name]


@pytest.fixture
def plugin_package(make_package) -> str:
    """A package whose ``__all__`` is built with ``dynamic_all``.

    Layout::

        __init__.py   -> TopPlugin(Base), Base re-exported, Unrelated
        alpha.py      -> AlphaPlugin(Base), AlphaHelper (not a Base)
        beta.py       -> BetaPlugin(Base), BetaChild(BetaPlugin)
        gamma.py      -> nothing deriving from Base
        _private.py   -> PrivatePlugin(Base) (not in __all__)
    """
    base_import = "from tests.conftest import Base\n\n"
    return make_package(
        {
            "__init__.py": base_import
            + "from emport import dynamic_all\n\n"
            + "class TopPlugin(Base):\n    pass\n\n"
            + "class Unrelated:\n    pass\n\n"
            + '__all__ = dynamic_all(__file__) + ["TopPlugin", "Base", "Unrelated"]\n',
            "alpha.py": base_import
            + "class AlphaPlugin(Base):\n    pass\n\n"
            + "class AlphaHelper:\n    pass\n",
            "beta.py": base_import
            + "class BetaPlugin(Base):\n    pass\n\n"
            + "class BetaChild(BetaPlugin):\n    pass\n",
            "gamma.py": "VALUE = 1\n",
            "_private.py": base_import + "class PrivatePlugin(Base):\n    pass\n",
        }
    )


@pytest.fixture(autouse=True)
def _repo_root_on_path(monkeypatch):
    # Make ``tests.conftest`` importable from generated fixture packages.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parent.parent))
