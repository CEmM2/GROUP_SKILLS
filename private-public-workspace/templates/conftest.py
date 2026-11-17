"""Run the private tests against the public packages in ``public/``.

Copy to ``private_tests/conftest.py``. Keep only the parts the repository
needs; each is explained where it starts.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

PRIVATE_TESTS = Path(__file__).resolve().parent
WORKSPACE_ROOT = PRIVATE_TESTS.parent
PUBLIC_ROOT = WORKSPACE_ROOT / "public"

# 1. Helpers beside this file (``_layout.py``) are imported by name.
if str(PRIVATE_TESTS) not in sys.path:
    sys.path.insert(0, str(PRIVATE_TESTS))

# 2. Private tests that import the public test package (``from tests.ref import
#    ...``) and private helpers that used to sit inside it (``tests.spike``):
#    import the public package, then add the private folder to its search path,
#    so no import has to change. Set PUBLIC_TEST_PARENT to the folder that holds
#    the public ``tests`` package and PRIVATE_PART to where its private part went.
PUBLIC_TEST_PARENT: Path | None = None  # e.g. PUBLIC_ROOT / "packages" / "core"
PRIVATE_PART: Path | None = None  # e.g. PRIVATE_TESTS / "core"
if PUBLIC_TEST_PARENT is not None:
    if str(PUBLIC_TEST_PARENT) not in sys.path:
        sys.path.insert(0, str(PUBLIC_TEST_PARENT))
    import tests  # the public test package

    if PRIVATE_PART is not None and str(PRIVATE_PART) not in tests.__path__:
        tests.__path__.append(str(PRIVATE_PART))


# 3. Fixtures of a public conftest.py. Call this from
#    ``private_tests/<group>/conftest.py``:
#        globals().update(public_conftest(Path("public/packages/core/tests/conftest.py")))
def public_conftest(relative: Path) -> dict[str, object]:
    """Load a public conftest.py and return what it defines (fixtures, hooks, constants)."""
    path = WORKSPACE_ROOT / relative
    name = "_public_conftest_" + "_".join(relative.parts[:-1]).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {k: v for k, v in vars(module).items() if not k.startswith("__")}


# 4. Tests that assert on code the public side has changed since the private
#    copy was made. List their node IDs in stale_against_public.txt (one per
#    line, # for comments); they run as strict expected failures until the
#    owner updates or deletes them.
_STALE = PRIVATE_TESTS / "stale_against_public.txt"


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not _STALE.is_file():
        return
    stale = {
        line.strip()
        for line in _STALE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for item in items:
        if item.nodeid in stale:
            item.add_marker(
                pytest.mark.xfail(
                    strict=True,
                    reason="asserts code the public side changed; see stale_against_public.txt",
                )
            )
