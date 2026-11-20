# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - unreleased

The first versioned release. The public API is unchanged and backward
compatible; no migration is needed.

### Fixed

- `ObjectUtils.get_properties` crashed on Python 3.10+ (`collections.Callable`
  was removed). It now uses the builtin `callable()`.
- `co_to_dict` / `get_caller` no longer emit `DeprecationWarning` on Python
  3.12+ for `co_lnotab`. The key is kept, and its value is `None` on
  interpreters that no longer provide it.
- `get_caller` / `get_caller_module` with a `depth` beyond the call stack now
  raise a clear `StackDepthError` instead of
  `AttributeError: 'NoneType' object has no attribute ...`.
  `StackDepthError` subclasses `AttributeError`, so existing handlers still
  work. Frame references are released explicitly to avoid reference cycles.
- `dynamic_all` now lists only files that `from package import *` can
  actually import. The old `*.py*` glob also picked up backup files
  (`mod.py.bak` -> `mod.py`), type stubs (`.pyi`), Cython sources (`.pyx`),
  Python 2 `.pyo` files, and names that are not identifiers or are keywords.
  Any of those made `import *` fail. `.py` and `.pyc` (plus `.pyw` on Windows)
  are still listed.
- `dynamic_all` returns a sorted list, so `__all__` is deterministic. It used
  to come from a set in arbitrary order. It also handles package directories
  whose path contains glob characters such as `[`.
- `Emport.__repr__` no longer fails when the wrapped object is a tuple.
- `Emport.get_flat_list` still flattens nested `Emport`s when a member name
  shadows the `get_flat_list` method.
- Docstrings: `emport_objects_by_class` returns a list of `(name, class)`
  tuples, not an `Emport`.

### Security

- Documented the trust model. Importing runs code, so `from_path` and
  `import_items` must never come from untrusted input. See the README
  "Security" section and the function docstrings.
- `emport_by_class` / `emport_objects_by_class` validate `from_path` before
  importing and raise `InvalidImportPathError` for an empty path, a relative
  path, or a path with empty parts. The exception subclasses both
  `ValueError` and `ModuleNotFoundError`, which these inputs raised before.
- New optional keyword-only argument `allowed_prefixes` for both functions. It
  restricts imports to an allowlist of packages and is checked before any
  import happens.
- Documented that `get_caller` output includes `co_consts` (function
  literals) and should not be logged.

### Added

- `pyproject.toml` packaging (setuptools, Python >= 3.9, no runtime
  dependencies), `emport.__version__`, `__all__` and type hints.
- A pytest suite with 100% line and branch coverage, ruff lint/format config,
  a GitHub Actions CI workflow (pinned actions, read-only permissions),
  Dependabot config and a `.gitignore`.
- A rewritten README with install, API reference, security and development
  sections.

### Removed

- The duplicate `import collections` and the Python 2 style `class X(object)`
  declarations.

## 0.1.0 - historical

The original unversioned single-file release.
