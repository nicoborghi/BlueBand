import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _patch_apptest_button_group() -> None:
    """Make AppTest able to re-run a single-select segmented control.

    Streamlit 1.45 keeps a single selection in the session as the value itself
    and `ButtonGroup.indices` iterates it as if it were still a list: a value
    of "12" is read back as the two options "1" and "2", and the *next* run
    raises `ValueError: ... is not in list`. The velocità is entered on those
    controls (`ui.pages.races._pick_one`), so without this the whole event
    could not be driven headless - and an input this app cannot test is an
    input it does not keep (see the handoff on `st.data_editor`).

    Test harness only: nothing in the app depends on it. Drop it when the
    upstream property handles a scalar.
    """
    from streamlit.testing.v1.element_tree import ButtonGroup

    def indices(self):
        value = self.value
        values = (value if isinstance(value, (list, tuple))
                  else [] if value is None else [value])
        return [self.options.index(self.format_func(v)) for v in values]

    ButtonGroup.indices = property(indices)


_patch_apptest_button_group()

GIURIA = Path("/mnt/g/My Drive/Public/Campionati Italiani Pista Giovanili 2026/Giuria")
ISCRITTI = GIURIA / "Iscritti_26_generale.xlsx"
KSPORT = GIURIA / "Iscritti_182447.xls"

# The data folder is named after the championship being run and is not the same
# on every machine: the repo ships `CITA26_test`, a live console has `CITA26`.
# The tests read whichever programme is there - they only care that it is the
# real one, not a fixture written for them.
COMPETITIONS = ROOT / "competitions"
CANDIDATES = ("CITA26", "CITA26_test")


def programme_path() -> Path:
    for name in CANDIDATES:
        p = COMPETITIONS / name / "programme.yaml"
        if p.exists():
            return p
    pytest.skip(f"no programme in {COMPETITIONS}: tried {', '.join(CANDIDATES)}")


@pytest.fixture(scope="session")
def comp():
    from core.config import load_competition
    return load_competition(programme_path())


@pytest.fixture
def store(tmp_path):
    from core.store import Store
    return Store(tmp_path / "evt")


def _available(path: Path) -> bool:
    """Whether a fixture file can be read at all.

    Not just "does it exist": these live on a mounted Drive folder, and a mount
    that has gone away makes `exists()` *raise* (`OSError: No such device`)
    rather than answer False - which turned every test that wants the workbook
    into an error instead of a skip.
    """
    try:
        return path.exists()
    except OSError:
        return False


@pytest.fixture(scope="session")
def iscritti_path():
    if not _available(ISCRITTI):
        pytest.skip(f"entry workbook not available: {ISCRITTI}")
    return ISCRITTI


@pytest.fixture(scope="session")
def ksport_path():
    """The flat federal export: one sheet, one row per rider, no specialità."""
    if not _available(KSPORT):
        pytest.skip(f"ksport export not available: {KSPORT}")
    return KSPORT
