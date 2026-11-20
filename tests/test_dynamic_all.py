from __future__ import annotations

import sys

import pytest

from emport import dynamic_all


def _touch(directory, *names):
    for name in names:
        (directory / name).write_text("")


def test_lists_public_python_modules_sorted(tmp_path):
    _touch(tmp_path, "__init__.py", "zeta.py", "alpha.py", "mid.py")
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["alpha", "mid", "zeta"]


def test_skips_private_and_dunder(tmp_path):
    _touch(tmp_path, "__init__.py", "_private.py", "__main__.py", "public.py")
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["public"]


def test_ignores_directories_even_with_py_like_names(tmp_path):
    _touch(tmp_path, "__init__.py", "real.py")
    (tmp_path / "subpkg").mkdir()
    (tmp_path / "subpkg" / "__init__.py").write_text("")
    (tmp_path / "dir.py").mkdir()
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["real"]


def test_deduplicates_source_and_bytecode(tmp_path):
    _touch(tmp_path, "__init__.py", "mod.py", "mod.pyc", "only_bytecode.pyc")
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["mod", "only_bytecode"]


@pytest.mark.parametrize(
    "junk",
    [
        "backup.py.bak",  # editor/backup file (old version yielded 'backup.py')
        "stub.pyi",  # type stub, not importable
        "ext.pyx",  # Cython source, not importable without a build
        "old.pyo",  # Python 2 optimised bytecode
        "bad-name.py",  # not an identifier
        "class.py",  # keyword
        "1st.py",  # not an identifier
        "notes.txt",
        "README",
    ],
)
def test_skips_files_that_break_star_import(tmp_path, junk):
    _touch(tmp_path, "__init__.py", "good.py", junk)
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["good"]


@pytest.mark.skipif(sys.platform != "win32", reason=".pyw is a source suffix on Windows only")
def test_pyw_on_windows(tmp_path):  # pragma: no cover
    _touch(tmp_path, "__init__.py", "gui.pyw")
    assert dynamic_all(str(tmp_path / "__init__.py")) == ["gui"]


def test_directory_with_glob_metacharacters(tmp_path):
    weird = tmp_path / "we[ir]d"  # unescaped, this glob would match "wed"/"wid"/"wrd"
    weird.mkdir()
    _touch(weird, "__init__.py", "mod.py")
    assert dynamic_all(str(weird / "__init__.py")) == ["mod"]


def test_empty_package(tmp_path):
    _touch(tmp_path, "__init__.py")
    assert dynamic_all(str(tmp_path / "__init__.py")) == []


def test_star_import_works_with_result(make_package):
    pkg = make_package(
        {
            "__init__.py": "from emport import dynamic_all\n__all__ = dynamic_all(__file__)\n",
            "one.py": "X = 1\n",
            "two.py": "Y = 2\n",
            "two.py.orig": "garbage that is not python (\n",
        }
    )
    namespace: dict = {}
    exec("from %s import *" % pkg, namespace)
    assert namespace["one"].X == 1
    assert namespace["two"].Y == 2
