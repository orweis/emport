"""emport - Python dynamic imports and object filtering.

A small, dependency-free helper module for:

* importing a package by its dotted path and keeping only the classes that
  derive from a given base class (a lightweight plugin-discovery pattern),
* building ``__all__`` dynamically from the modules found in a package
  directory,
* introspecting the call stack (the calling function / module),
* a few class-introspection helpers (:class:`ObjectUtils`).

Security note
-------------
:func:`emport_by_class` and :func:`emport_objects_by_class` *import* the
module named by ``from_path``. Importing a module executes its top-level code
(and that of every package ``__init__`` and module it imports). Never pass
untrusted input (user input, request parameters, config files writable by
others, database values ...) as ``from_path`` or ``import_items``. Use the
optional ``allowed_prefixes`` argument to restrict which packages may be
imported. See the "Security" section of the README for details.
"""

from __future__ import annotations

import glob
import inspect
import keyword
import os
import sys
import warnings
from collections.abc import Iterable, Sequence
from importlib.machinery import BYTECODE_SUFFIXES, SOURCE_SUFFIXES
from types import CodeType, FrameType, ModuleType
from typing import Any

__author__ = "orw"
__version__ = "0.2.0"

__all__ = [
    "Emport",
    "InvalidImportPathError",
    "ObjectUtils",
    "PyFrame",
    "StackDepthError",
    "co_to_dict",
    "dynamic_all",
    "emport_by_class",
    "emport_objects_by_class",
    "get_caller",
    "get_caller_module",
]

#: A ``(name, object)`` pair, as returned by :func:`inspect.getmembers`.
Member = tuple[str, Any]


class InvalidImportPathError(ValueError, ModuleNotFoundError):
    """Raised when an import path is malformed or not in ``allowed_prefixes``.

    It subclasses both :class:`ValueError` and :class:`ModuleNotFoundError`
    (and therefore :class:`ImportError`), so code written against earlier
    versions, which got one of those from ``__import__`` for malformed paths,
    keeps working.
    """


class StackDepthError(ValueError, AttributeError):
    """Raised when a requested stack ``depth`` is deeper than the call stack.

    It subclasses :class:`AttributeError` because earlier versions failed with
    ``AttributeError: 'NoneType' object has no attribute ...`` in that case.
    """


class ObjectUtils:
    """Class-introspection helpers (kept as static/class methods for
    backward compatibility)."""

    @staticmethod
    def is_derived_of(obj: Any, possible_parent_class: type) -> bool:
        """Return ``True`` if ``obj`` is a class that is, or derives from,
        ``possible_parent_class``.

        Like :func:`issubclass`, but returns ``False`` instead of raising for
        non-class objects. Note that a class counts as derived of itself.
        """
        if hasattr(obj, "__bases__"):
            return possible_parent_class in inspect.getmro(obj)
        return False

    @staticmethod
    def get_properties(obj: Any) -> dict:
        """Return a dict of the non-callable attributes of ``obj``.

        Attributes whose name starts with ``__`` (e.g. dunders) are excluded.
        Name-mangled privates (``_Class__name``) are *included*.
        """
        return {
            name: value
            for name, value in inspect.getmembers(obj, lambda x: not callable(x))
            if not name.startswith("__")
        }

    @staticmethod
    def get_members_who_are_instance_of(obj: Any, class_type: type) -> list[Member]:
        """Return the ``(name, value)`` members of ``obj`` that are instances of
        ``class_type``, sorted by name."""
        return inspect.getmembers(obj, lambda x: isinstance(x, class_type))

    @classmethod
    def get_class_members_who_derive_of(cls, obj: Any, parent_class: type) -> list[Member]:
        """Return the ``(name, class)`` members of ``obj`` that are classes
        deriving from ``parent_class``, sorted by name.

        ``parent_class`` itself is *excluded* even if it is a member of ``obj``.
        """

        def predicate(x: Any) -> bool:
            return (
                inspect.isclass(x) and cls.is_derived_of(x, parent_class) and x is not parent_class
            )

        return inspect.getmembers(obj, predicate)


class PyFrame:
    """Context manager yielding the frame of the code that created it.

    ``with PyFrame() as frame:`` binds ``frame`` to the frame of the function
    containing the ``with`` statement. The internal frame reference is dropped
    on exit to avoid reference cycles.
    """

    def __init__(self) -> None:
        self._frame: FrameType | None = inspect.currentframe()

    def __enter__(self) -> FrameType:
        frame = self._frame
        if frame is None or frame.f_back is None:  # pragma: no cover
            raise RuntimeError("stack frame introspection is not supported here")
        return frame.f_back

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        del self._frame


class Emport:
    """A filtered view of an imported module.

    Each kept member is exposed as an attribute (``emport_obj.MyPlugin``) and,
    in insertion order, through :meth:`get_members_list`. Members that are
    themselves sub-modules are wrapped in nested :class:`Emport` objects.

    Note: a member whose name equals one of this class's own attributes
    (e.g. a class called ``get_flat_list``) shadows that attribute on the
    instance. This is the historical behaviour and is preserved.
    """

    def __init__(self, module: Any, members: Iterable[Member]) -> None:
        self.__original__ = module
        self._members: list[Any] = []
        for name, value in members:
            self._members.append(value)
            setattr(self, name, value)

    def get_original_module(self) -> Any:
        """Return the module this Emport was built from."""
        return self.__original__

    def get_members_list(self) -> list[Any]:
        """Return the kept members (values only, no names)."""
        return self._members

    def get_flat_list(self) -> list[Any]:
        """Return all members of this Emport, and of nested Emports, as one
        flat list (values only)."""
        result: list[Any] = []
        for member in self._members:
            if isinstance(member, Emport):
                # Call through the class so member names shadowing the
                # method on a nested instance cannot break flattening.
                result.extend(Emport.get_flat_list(member))
            else:
                result.append(member)
        return result

    def __repr__(self) -> str:
        return "EMPORT - %s" % (self.__original__,)


def _walk_back(frame: FrameType, depth: int) -> FrameType:
    # range() keeps the historical semantics: a negative depth acts like 0.
    for _ in range(depth):
        parent = frame.f_back
        if parent is None:
            raise StackDepthError("depth %d is deeper than the call stack" % depth)
        frame = parent
    return frame


def get_caller_module(depth: int = 0) -> ModuleType:
    """Return the module object of a function on the call stack.

    :param depth: ``0`` is this function itself (so it returns the ``emport``
        module), ``1`` is the function that called ``get_caller_module``,
        ``2`` is that function's caller, and so on.
        A negative depth behaves like ``0``.
    :raises StackDepthError: if ``depth`` exceeds the stack.
    """
    with PyFrame() as frame:
        try:
            return sys.modules[_walk_back(frame, depth).f_globals["__name__"]]
        finally:
            del frame  # break the frame reference cycle


def co_to_dict(co: CodeType) -> dict:
    """Return selected attributes of a code object as a dict.

    The ``co_lnotab`` key is kept for backward compatibility. It is read
    without emitting the Python 3.12+ ``DeprecationWarning`` and is ``None``
    on interpreters that no longer provide it.

    Warning: ``co_consts`` contains every literal in the function body
    (possibly including hard-coded secrets). Do not log or transmit this dict
    blindly.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        lnotab = getattr(co, "co_lnotab", None)
    return {
        "co_argcount": co.co_argcount,
        "co_nlocals": co.co_nlocals,
        "co_stacksize": co.co_stacksize,
        "co_flags": co.co_flags,
        "co_consts": co.co_consts,
        "co_names": co.co_names,
        "co_varnames": co.co_varnames,
        "co_filename": co.co_filename,
        "co_name": co.co_name,
        "co_firstlineno": co.co_firstlineno,
        "co_lnotab": lnotab,
    }


def get_caller(depth: int = 0) -> dict:
    """Return :func:`co_to_dict` of the code object of a function on the stack.

    :param depth: ``0`` is ``get_caller`` itself, ``1`` is the function that
        called ``get_caller``, ``2`` is that function's caller, and so on.
        A negative depth behaves like ``0``.
    :raises StackDepthError: if ``depth`` exceeds the stack.

    See the warning on :func:`co_to_dict` about logging the result.
    """
    with PyFrame() as frame:
        try:
            return co_to_dict(_walk_back(frame, depth).f_code)
        finally:
            del frame  # break the frame reference cycle


def _validate_import_path(from_path: Any, allowed_prefixes: Iterable[str] | None) -> None:
    if not isinstance(from_path, str):
        raise TypeError("from_path must be a str, got %s" % type(from_path).__name__)
    if not from_path:
        raise InvalidImportPathError("from_path must not be empty")
    if from_path.startswith("."):
        raise InvalidImportPathError("relative import paths are not supported: %r" % from_path)
    if any(not part for part in from_path.split(".")):
        raise InvalidImportPathError("malformed dotted import path: %r" % from_path)
    if allowed_prefixes is not None:
        if isinstance(allowed_prefixes, str):
            allowed_prefixes = [allowed_prefixes]
        for prefix in allowed_prefixes:
            if from_path == prefix or from_path.startswith(prefix + "."):
                return
        raise InvalidImportPathError("import of %r is not allowed by allowed_prefixes" % from_path)


def _import(
    from_path: str,
    import_items: Sequence[str] | None,
    allowed_prefixes: Iterable[str] | None,
) -> ModuleType:
    _validate_import_path(from_path, allowed_prefixes)
    # __import__ (rather than importlib.import_module) is used on purpose: a
    # non-empty fromlist returns the leaf module and, with ["*"], also imports
    # the submodules listed in a package's __all__ - which is what lets
    # emport discover classes in submodules.
    return __import__(from_path, None, None, list(import_items or ["*"]), 0)


def _submodules(module: ModuleType) -> list[Member]:
    # type(module) rather than ModuleType, as in earlier versions.
    return ObjectUtils.get_members_who_are_instance_of(module, type(module))


def emport_by_class(
    from_path: str,
    cls: type,
    import_items: Sequence[str] | None = None,
    *,
    allowed_prefixes: Iterable[str] | None = None,
) -> Emport:
    """Import ``from_path`` and keep only the classes deriving from ``cls``.

    Classes found directly in the module are kept, and so are classes found
    in its *direct* submodules (one level deep); each submodule with at least
    one match becomes a nested :class:`Emport`. ``cls`` itself is excluded.

    SECURITY: importing runs the target module's code. ``from_path`` and
    ``import_items`` must come from trusted sources only.

    :param from_path: absolute dotted module/package path, e.g. ``"pkg.plugins"``.
    :param cls: base class to filter the module contents by.
    :param import_items: the ``fromlist`` passed to ``__import__``
        (default ``["*"]``).
    :param allowed_prefixes: optional allowlist of package prefixes; if given,
        ``from_path`` must equal one of them or be a submodule of one, else
        :class:`InvalidImportPathError` is raised before anything is imported.
    :return: an :class:`Emport` with the filtered contents.
    """
    module_obj = _import(from_path, import_items, allowed_prefixes)
    clean_items = ObjectUtils.get_class_members_who_derive_of(module_obj, cls)
    for sub_name, sub_module in _submodules(module_obj):
        results = ObjectUtils.get_class_members_who_derive_of(sub_module, cls)
        if results:  # keep only submodules with matches
            clean_items.append((sub_name, Emport(sub_module, results)))
    return Emport(module_obj, clean_items)


def emport_objects_by_class(
    from_path: str,
    cls: type,
    import_items: Sequence[str] | None = None,
    *,
    allowed_prefixes: Iterable[str] | None = None,
) -> list[Member]:
    """Like :func:`emport_by_class`, but return a flat list.

    SECURITY: importing runs the target module's code. ``from_path`` and
    ``import_items`` must come from trusted sources only.

    :return: a list of ``(name, class)`` tuples: first the matches in the
        module itself, then the matches of each direct submodule. A class
        reachable both ways appears more than once.
    """
    module_obj = _import(from_path, import_items, allowed_prefixes)
    results = ObjectUtils.get_class_members_who_derive_of(module_obj, cls)
    for _sub_name, sub_module in _submodules(module_obj):
        results.extend(ObjectUtils.get_class_members_who_derive_of(sub_module, cls))
    return results


#: File suffixes that the default import system loads as Python modules.
_MODULE_SUFFIXES = tuple(SOURCE_SUFFIXES) + tuple(BYTECODE_SUFFIXES)


def dynamic_all(init_file_path: str) -> list[str]:
    """Return the names of the public modules next to ``init_file_path``.

    Intended for a package's ``__init__.py``::

        from emport import dynamic_all
        __all__ = dynamic_all(__file__)

    Only regular files with an importable module suffix (``.py``, ``.pyc``,
    plus ``.pyw`` on Windows) are considered; names starting with ``_``,
    names that are not valid identifiers and keywords are skipped.
    Sub-packages (directories) are not included. The result is sorted.

    SECURITY: every listed module is imported by ``from package import *``,
    so anyone who can write files into the package directory can run code.
    """
    directory = os.path.dirname(init_file_path)
    names = set()
    for path in glob.glob(os.path.join(glob.escape(directory), "*")):
        if not os.path.isfile(path):
            continue
        name, suffix = os.path.splitext(os.path.basename(path))
        if suffix not in _MODULE_SUFFIXES:
            continue
        if name.startswith("_") or not name.isidentifier() or keyword.iskeyword(name):
            continue
        names.add(name)
    return sorted(names)
