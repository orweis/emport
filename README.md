# emport

Python dynamic imports and object filtering.

`emport` is a single, dependency-free module that helps you:

- **discover plugins**: import a package by its dotted path and keep only the
  classes that derive from a given base class (`emport_by_class`,
  `emport_objects_by_class`);
- **build `__all__` automatically** from the modules in a package directory
  (`dynamic_all`);
- **inspect the call stack**: get the calling function's code details or the
  calling module (`get_caller`, `get_caller_module`);
- **introspect classes** (`ObjectUtils`).

Supported Python versions: 3.9 and newer (tested on 3.9 to 3.14). No
third-party runtime dependencies.

## Installation

`emport` is not published on PyPI. Install it from the Git repository:

```bash
pip install "git+https://github.com/orweis/emport.git"
```

Or copy `emport.py` into your project; it is self-contained.

## Quick start: plugin discovery

Given this package layout:

```text
myapp/plugins/__init__.py   ->  from emport import dynamic_all
                                __all__ = dynamic_all(__file__)
myapp/plugins/csv_export.py ->  class CsvExporter(BaseExporter): ...
myapp/plugins/pdf_export.py ->  class PdfExporter(BaseExporter): ...
```

```python
from emport import emport_by_class, emport_objects_by_class
from myapp.base import BaseExporter

plugins = emport_by_class("myapp.plugins", BaseExporter)
plugins.csv_export.CsvExporter  # nested Emport per submodule
plugins.get_flat_list()  # [CsvExporter, PdfExporter]

# or as a flat list of (name, class) tuples
emport_objects_by_class("myapp.plugins", BaseExporter)
# [('CsvExporter', CsvExporter), ('PdfExporter', PdfExporter)]

# restrict what may be imported (recommended)
emport_by_class("myapp.plugins", BaseExporter, allowed_prefixes=["myapp.plugins"])
```

## API reference

### `emport_by_class(from_path, cls, import_items=None, *, allowed_prefixes=None) -> Emport`

Imports `from_path` (an absolute dotted path) with
`__import__(from_path, fromlist=import_items or ["*"])` and keeps the classes
that derive from `cls`:

- classes defined in, or imported into, the module itself;
- classes in the module's **direct** submodules (one level deep). Each
  submodule with at least one match becomes a nested `Emport`; submodules
  without matches are dropped.

`cls` itself is never included. With the default `import_items=["*"]`, a
package's submodules are imported only if they are listed in its `__all__`
(see `dynamic_all`). `allowed_prefixes` is an optional allowlist (a string or
an iterable of strings): `from_path` must equal a prefix or be a submodule of
one (`"pkg"` allows `"pkg"` and `"pkg.sub"`, not `"pkg_other"`). Otherwise
`InvalidImportPathError` is raised before anything is imported.

### `emport_objects_by_class(from_path, cls, import_items=None, *, allowed_prefixes=None) -> list[tuple[str, type]]`

Same discovery as `emport_by_class`, but returns a flat list of
`(name, class)` tuples: the module's own matches first, then those of each
direct submodule. A class reachable both ways (e.g. re-exported in
`__init__.py`) is listed once per occurrence.

### `Emport`

A filtered view of a module. Each kept member is an attribute of the
instance.

| Method | Returns |
| --- | --- |
| `get_original_module()` | the module the view was built from |
| `get_members_list()` | the kept members (values only), nested `Emport`s included |
| `get_flat_list()` | all kept classes, recursively flattened |
| `repr(e)` | `"EMPORT - <module repr>"` |

A member whose name equals an `Emport` method (e.g. a class called
`get_flat_list`) shadows that method on the instance.

### `dynamic_all(init_file_path) -> list[str]`

Returns the sorted names of the public modules next to `init_file_path`:

```python
# in your package's __init__.py
from emport import dynamic_all

__all__ = dynamic_all(__file__)
```

Only regular files with an importable module suffix are listed (`.py`,
`.pyc`, and `.pyw` on Windows). Names that start with `_`, that are not valid
identifiers, or that are Python keywords are skipped. Sub-packages
(directories) are not listed.

### `get_caller(depth=0) -> dict` and `get_caller_module(depth=0) -> module`

`depth` counts frames from the helper itself: `0` is the helper
(`get_caller` itself, or the `emport` module), `1` is the function that
called it, `2` is that function's caller, and so on. A negative depth behaves
like `0`. A depth beyond the top of the stack raises `StackDepthError`.

```python
from emport import get_caller, get_caller_module


def handler():
    me = get_caller(1)["co_name"]  # "handler"
    who_called_me = get_caller(2)["co_name"]
    my_module = get_caller_module(1)
```

`get_caller` returns `co_to_dict(code)`: a dict with the keys `co_argcount`,
`co_nlocals`, `co_stacksize`, `co_flags`, `co_consts`, `co_names`,
`co_varnames`, `co_filename`, `co_name`, `co_firstlineno` and `co_lnotab`.
`co_lnotab` is `None` on Python versions that no longer provide it.

### `ObjectUtils`

```python
from emport import ObjectUtils


class A: ...


class B(A): ...


ObjectUtils.is_derived_of(B, A)  # True  (also True for A, A; False for non-classes)
ObjectUtils.get_properties(obj)  # {name: value} of non-callable attrs not starting with "__"
ObjectUtils.get_members_who_are_instance_of(obj, A)  # [(name, instance), ...]
ObjectUtils.get_class_members_who_derive_of(obj, A)  # [(name, subclass), ...], A excluded
```

### Exceptions

- `InvalidImportPathError`: a malformed `from_path` (empty, relative such as
  `".mod"`, or with empty parts such as `"a..b"`) or one outside
  `allowed_prefixes`. It subclasses both `ValueError` and
  `ModuleNotFoundError`.
- `StackDepthError`: the requested `depth` is beyond the call stack. It
  subclasses both `ValueError` and `AttributeError`.

## Security

`emport_by_class` and `emport_objects_by_class` **import code**. Importing a
module runs its top-level code, and the code of every package `__init__` and
module it imports, with your process's privileges.

- **Never pass untrusted input** as `from_path` or `import_items`: user input,
  HTTP parameters, CLI arguments from other users, database values, or
  config files that others can write. If an attacker controls the name, they
  can import any module on `sys.path`, including modules they planted in a
  writable directory on `sys.path` (such as the current working directory).
- When the path comes from configuration, pass `allowed_prefixes` to limit
  imports to your own plugin package(s).
- `dynamic_all` lists every module file in the package directory, and
  `from package import *` imports them all. Anyone who can write files into
  that directory can run code in your process, so keep plugin directories
  writable only by trusted users.
- `get_caller` / `co_to_dict` return `co_consts`, which holds every literal in
  the function body (possibly hard-coded secrets) plus file paths. Do not log
  or send these dicts anywhere without filtering them.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest --cov            # test suite, 95% coverage minimum
ruff check . && ruff format --check .
python -m build         # sdist + wheel into dist/
```

CI (GitHub Actions) runs lint, build and the test suite on Python 3.9 to 3.14
and on Windows and macOS.

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Version 0.2.0 has no breaking API changes.
It fixes the module on Python 3.10+, where it used to crash.

## License

Apache License 2.0. See [LICENSE](LICENSE).
