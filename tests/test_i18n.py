"""The translation document is the only place with Italian in it.

Two guards, because the catalogue only works if both hold: every key the code
asks for has to exist (or a field comes out with no label and nobody notices),
and no module may go back to writing Italian of its own (or the catalogue stops
being the one place to edit).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from core import checks
from core import i18n as I

TRACK = Path(__file__).resolve().parent.parent
CATALOGUE = TRACK / "core" / "i18n.py"

#: The four lookups and the dictionary each one reads.
LOOKUPS = {"ui": I.UI, "msg": I.MSG, "help_text": I.HELP, "label": I.IT}

#: `notify.warn("x")` names a message, not a control.
NOTIFY = {"error", "warn", "info", "ok", "saved"}


def _sources():
    """Every module of the app except the catalogue itself."""
    for p in sorted(TRACK.rglob("*.py")):
        s = str(p.relative_to(TRACK))
        if ("__pycache__" in s or s.startswith(("tests/", "competitions/"))
                or p == CATALOGUE):
            continue
        yield p, ast.parse(p.read_text(encoding="utf-8"))


def _keys_used():
    """(file, line, which dictionary, key) for every lookup in the app."""
    for p, tree in _sources():
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if isinstance(f, ast.Name) and f.id in LOOKUPS:
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        yield p, n.lineno, f.id, a.value
            elif (isinstance(f, ast.Attribute) and f.attr in NOTIFY
                  and isinstance(f.value, ast.Name) and f.value.id == "notify"
                  and n.args and isinstance(n.args[0], ast.Constant)):
                yield p, n.lineno, "msg", n.args[0].value


def test_every_key_the_code_asks_for_is_in_the_catalogue():
    """A missing entry is a field with no label, and nothing says so at runtime."""
    missing = [(str(p.relative_to(TRACK)), line, which, key)
               for p, line, which, key in _keys_used()
               # `label` falls back to the key, on purpose: a new column shows
               # up readable. The other three raise, so they must all resolve.
               if key and which != "label" and key not in LOOKUPS[which]]
    assert not missing, missing


def test_a_label_key_is_looked_up_where_it_lives():
    """`ui(...)` and `label(...)` read different dictionaries: no key crosses.

    A control asked for with `label` (or the other way round) works right up to
    the moment the wording is edited in the dictionary the caller does not read.
    """
    crossed = [(str(p.relative_to(TRACK)), line, which, key)
               for p, line, which, key in _keys_used()
               if which == "label" and key not in I.IT
               and (key in I.UI or key in I.MSG)]
    assert not crossed, crossed


# Words that give away Italian prose. Deliberately common ones: a literal that
# matches is either a label that belongs in the catalogue or - the two real
# exceptions - a key of the programme, which is not translated at all.
_ITALIAN = re.compile(
    r"\b(?:il|lo|la|le|gli|una|delle|non|che|per|con|della|nella|sono|questo|"
    r"come|dove|ogni|tutti|già|ancora|senza|batterie|gara|giuria|dorsale|"
    r"dorsali|coppie|squadre|atleta|atleti|comunicato|comunicati|classifica|"
    r"partenti|risultati|specialità|iscritti|verifica|stampa|cartella|firma|"
    r"manifestazione|colonna|elenco|arrivo|tempi|volata|punti|recuperi|"
    r"semifinali|qualificazioni|modifiche|motivo|impostazioni|programma|"
    r"regione|società|riserva)\b", re.I)

#: The strings that are Italian and must stay in the code, because none of them
#: is anything the jury reads:
#:
#: * the keys a round is scheduled and saved under (`programme.yaml`,
#:   `races/<id>.json`) - translating one would lose a race on disk;
#: * the names of the files and of the page anchors;
#: * the field names of the JSON written before the code moved to English
#:   (`models.LEGACY_KEYS`), read for compatibility and never written;
#: * what the federation's workbook spells in a cell, matched on import.
PROGRAMME_VOCABULARY = {
    # round keys
    "Turno 1", "Quarti", "Semifinali", "Finali", "Recuperi",
    "Scratch", "Tempo Race", "Eliminazione", "Corsa a Punti",
    "qualificazioni", "final", "tempo race", "corsa a punti", "eliminazione",
    "scratch", "quarti", "semi", "batteria-",
    # document kinds, file names, anchors
    "partenti", "risultati", "classifica", "gara", "comunicati.json",
    "verifica", "stampa",
    # legacy JSON field names, and a workbook value
    "dorsale", "regione", "comunicati", "societa", "provincia",
    "specialities", "speciality", "decisione", "RISERVA",
}


def test_no_module_writes_italian_of_its_own():
    """Italian goes in the catalogue: everywhere else is English and keys."""
    stray = []
    for p, tree in _sources():
        docs = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
                d = ast.get_docstring(n, clean=False)
                if d is not None and n.body and isinstance(n.body[0], ast.Expr):
                    docs.add(id(n.body[0].value))
        for n in ast.walk(tree):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in docs and len(n.value) > 3
                    and n.value not in PROGRAMME_VOCABULARY
                    and "<style>" not in n.value and "<script>" not in n.value
                    and _ITALIAN.search(n.value)):
                stray.append((str(p.relative_to(TRACK)), n.lineno, n.value[:60]))
    assert not stray, stray


# ── the inline flags ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, kwargs, flag", [
    # nothing typed is not a mistake
    ("", {}, ""),
    ("  ", {}, ""),
    # a line that cannot be read at all
    ("1, due", {}, "?"),
    # a number that is not one of the entrants
    ("1,2,7", {"expected": ["1", "2"]}, "?7"),
    # the same number twice, inside one line
    ("1,2,1", {"expected": ["1", "2"]}, "!1"),
    # ... unless writing it twice means something (giri guadagnati: 3, 3)
    ("3,3", {"expected": ["3"], "repeats_ok": True}, ""),
    # short of what the batteria holds - a count, not names
    ("1,2", {"expected": ["1", "2", "3", "4"], "need": 4}, "-2"),
    # a sprint of a corsa a punti scores four
    ("1,2", {"expected": ["1", "2"], "min_placed": 4}, "<4"),
    # every flag a line can carry at once
    ("1,1,9", {"expected": ["1", "2", "3"], "need": 3}, "?9 !1 -2"),
])
def test_one_notation_for_every_field(text, kwargs, flag):
    assert checks.bib_line(text, **kwargs).flag == flag


def test_a_bib_written_into_two_heats_is_flagged_on_the_second():
    """`seen` is what carries across the lines of one composition."""
    seen: set[str] = set()
    first = checks.bib_line("1,2", expected=["1", "2", "3"], seen=seen)
    second = checks.bib_line("2,3", expected=["1", "2", "3"], seen=seen)
    assert first.flag == "" and second.flag == "!2"
    assert second.bibs == ["2", "3"]


def test_the_flag_legend_explains_every_mark():
    """The one tooltip behind every flag has to name all of them."""
    legend = I.help_text("flags")
    for mark in (checks.FLAG_UNKNOWN, checks.FLAG_TWICE, checks.FLAG_MISSING,
                 checks.FLAG_TOO_FEW):
        assert mark in legend


def test_an_unknown_key_is_a_bug_and_says_so():
    """`ui` and `msg` raise; `label` falls back so a new column stays readable."""
    with pytest.raises(KeyError):
        I.ui("nessuna_chiave_del_genere")
    with pytest.raises(KeyError):
        I.msg("nessuna_chiave_del_genere")
    assert I.label("some_new_column") == "Some new column"


def test_the_lookup_argument_can_never_be_shadowed():
    """A `{key}` placeholder collided with the lookup argument itself.

    `msg("key_in_two_heats", key=...)` raised *got multiple values for
    argument 'key'* - in the middle of a keirin, where that warning is raised.
    The lookup argument is positional-only now, so a template may use any name.
    """
    assert I.msg("key_in_two_heats", who="7") == "7 è presente in più batterie."
    assert I.msg("xls_duplicate_rider", cat="AL", row=9, name="ROSSI",
                 key="1002") == "[AL] atleta duplicato (riga 9): ROSSI 1002."
