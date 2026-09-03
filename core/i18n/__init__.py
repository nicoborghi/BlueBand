"""The words the app says, in the language the jury reads them in.

The code speaks UCI English (competition, event, round, bib, club, region);
what reaches a screen or a printed sheet is a *lookup*, never a literal.
**Every word lives in one catalogue per language**, keyed by an English name:
column headings, statuses, document kinds, the label of every widget, the help
text of every field, and the wording of every warning, error and confirmation
the app can produce.

Nothing under `core/`, `render/` or `ui/` writes prose of its own. Adding a
language is adding one module next to `it.py` and listing it in `CATALOGUES`;
correcting a wording is editing one entry in it.

    from core.i18n import label, ui, msg, help_text

    label("bib")                        -> "Dors."   /  "Bib"
    ui("save_pdf")                      -> "Salva PDF"
    msg("bib_not_entered", bib=17)      -> "Dorsale 17 non è tra i partenti."
    help_text("status_dns", "bibs_csv")

The dictionaries every catalogue defines, by what they name:

    FIELDS        a column of the entry list (a property of a rider)
    RACE          a column or a word of a race sheet
    DOCS          a kind of document, and the words a sheet is titled with
    STATUSES      the decisions a jury takes on an entrant, as printed
    STATUS_NAMES  the same, spelled out for the pickers
    PENALTIES     the four degrees a penalty is given in
    NOTE_KINDS    what a block printed under a table is
    CODES         what a finding of the checks is about
    UI            what a control is called: pages, buttons, fields, options
    HELP          what a field says when you hover it
    MSG           the prose shown when something needs saying

`label` never raises: an unknown key comes back capitalised, so a new column
shows up readable. `ui`, `msg` and `help_text` do raise on an unknown key - a
missing label is a bug to fix, not a word to invent - and take keyword
arguments, formatted into the template with `str.format`.

A key the language in force does not have is answered from `DEFAULT`: a
translation caught up to a new field only later shows the Italian word there,
which is a good deal better than an empty widget or a KeyError at the track.
The language is chosen per competition in Impostazioni and set once per rerun
(`ui.state.competition`); everything below `ui/` just asks for a key.
"""

from __future__ import annotations

import re
from types import ModuleType

from . import en, it

#: Every language the app can be read in: code -> catalogue module. A new one
#: is a module with the same dictionaries and one line here.
CATALOGUES: dict[str, ModuleType] = {"it": it, "en": en}

#: The language the app was written for, and what a missing key falls back to.
DEFAULT = "it"

#: code -> what that language calls itself, for the picker in Impostazioni.
LANGUAGES: dict[str, str] = {code: mod.NAME for code, mod in CATALOGUES.items()}

_lang = DEFAULT

#: The four label dictionaries of a language, merged - built once per language.
_LABELS: dict[str, dict[str, str]] = {}


# ── accents ─────────────────────────────────────────────────────────────────
#
# Not display but input: the federation types an apostrophe where an accent
# belongs - VELOCITA', NICOLO', CITTA' - because that is what an Italian
# keyboard gives in capitals. Nothing printed by this app repeats it, whatever
# language it prints in: the workbook is read through here (`entries._s`) and so
# is the programme (`config.load_competition`).

_ACCENTED = {"A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù",
             "a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}

# Only at the end of a word - an elision is followed by another letter
# (DELL'ORSO, D'AMICO) - and only past the third letter, which leaves the real
# truncations alone: VO', PO', VA' are written with an apostrophe and keep it.
_APOSTROPHE = re.compile(r"(?<=\w\w\w)([AEIOUaeiou])['’](?!\w)")


def fix_accents(text: str) -> str:
    """VELOCITA' -> VELOCITÀ, CITTA' -> CITTÀ, DELL'ORSO unchanged."""
    return _APOSTROPHE.sub(lambda m: _ACCENTED[m.group(1)], text)


# ── which language is in force ──────────────────────────────────────────────

def set_language(code: str | None) -> str:
    """Set the language for what follows; returns the one actually in force.

    An unknown code - a settings file written by hand, a language dropped from
    the app - falls back to `DEFAULT` rather than leaving the jury with a page
    of KeyErrors.
    """
    global _lang
    _lang = code if code in CATALOGUES else DEFAULT
    return _lang


def language() -> str:
    """The code of the language in force ('it')."""
    return _lang


def language_name(code: str | None = None) -> str:
    """What a language calls itself ('it' -> 'Italiano')."""
    return LANGUAGES.get(code or _lang, code or _lang)


def catalogue(code: str | None = None) -> ModuleType:
    """The module a language's words are read from."""
    return CATALOGUES.get(code or _lang, CATALOGUES[DEFAULT])


def labels(code: str | None = None) -> dict[str, str]:
    """The merged label dictionary of a language (fields, race, docs, statuses)."""
    code = code if code in CATALOGUES else (code or _lang)
    if code not in _LABELS:
        mod = catalogue(code)
        _LABELS[code] = {**mod.FIELDS, **mod.RACE, **mod.DOCS, **mod.STATUSES}
    return _LABELS[code]


def _entry(name: str, key: str) -> str:
    """One entry of one dictionary, from the language in force or the fallback.

    Raises `KeyError` when neither has it, which is what tells a missing label
    from a translated one - see the module docstring.

    A line the jury has rewritten wins over both (`set_texts`): the catalogue
    is what the app ships, not what this installation says. Only `MSG` - the
    prose that reaches a sheet. A label or a help text is what the app calls
    its own controls, and renaming those is a translation, not a decision.
    """
    edited = _TEXTS.get(_lang, {}).get(key) if name == "MSG" else None
    if edited is not None:
        return edited
    table = getattr(catalogue(), name)
    if key in table:
        return table[key]
    return getattr(catalogue(DEFAULT), name)[key]


# ── the lines this installation words its own way ───────────────────────────
#
# Not a translation and not a competition's own word (`set_overrides`): the
# sentences a jury writes on its sheets - what a batteria qualifies for, where
# a squadra lines up - are the same at every meeting and belong to the
# federation, not to the file. They are shipped in the catalogues, edited in
# Impostazioni and kept in `regulations/notes.json` (`core.notes`), which is
# what this layer reads.
#
# Set once per run, before anything is drawn or printed.

_TEXTS: dict[str, dict[str, str]] = {}


def set_texts(texts: dict[str, dict[str, str]]) -> None:
    """Replace the lines this installation words its own way ({} clears them).

    `{language: {key: text}}`, keyed exactly as the catalogues are: a key that
    is not in them is simply never asked for, and one that is comes back
    rewritten in that language and in no other.
    """
    _TEXTS.clear()
    _TEXTS.update({lang: {k: v for k, v in (entries or {}).items() if v}
                   for lang, entries in (texts or {}).items()})


def texts() -> dict[str, dict[str, str]]:
    """What `set_texts` is holding, as it was given."""
    return {lang: dict(entries) for lang, entries in _TEXTS.items()}


# ── words this competition spells its own way ───────────────────────────────
#
# One word is not the same at every meeting: what a rider rides for is a
# *squadra* at a championship, a *rappresentativa* in some regions, a *team* on
# an international sheet. It is a name the jury chooses in Impostazioni, so it
# cannot be frozen in the catalogues - and it is still one word in one place,
# because everything asks for it by the same key.
#
# Set once per run, from the competition being loaded (`ui.state.competition`).

_OVERRIDES: dict[str, str] = {}


def set_overrides(values: dict[str, str]) -> None:
    """Replace the words this competition spells its own way ({} clears them)."""
    _OVERRIDES.clear()
    _OVERRIDES.update({k: v for k, v in (values or {}).items() if v})


# ── lookups ─────────────────────────────────────────────────────────────────

def label(key: str, default: str | None = None) -> str:
    """The label of a domain key ('bib' -> 'Dors.')."""
    if key in _OVERRIDES:
        return _OVERRIDES[key]
    table = labels()
    if key in table:
        return table[key]
    fallback = labels(DEFAULT)
    if key in fallback:
        return fallback[key]
    return default if default is not None else str(key).replace("_", " ").capitalize()


def word(key: str) -> str:
    """The catalogue word for a key, ignoring what this competition renamed.

    What `label` answers *before* the overrides - which is what a page setting
    one of them has to start from, or it would only ever read back its own.
    """
    return labels().get(key) or labels(DEFAULT)[key]


def ui(key: str, /, **kwargs) -> str:
    """What a control is called ('save_pdf' -> 'Salva PDF').

    Raises on an unknown key: a control with no name is a bug in the code, not
    a word to make up on the spot.
    """
    if key in _OVERRIDES and not kwargs:
        return _OVERRIDES[key]
    text = _entry("UI", key)
    return text.format(**kwargs) if kwargs else text


def msg(key: str, /, **kwargs) -> str:
    """One message, with its values filled in ('bib_not_entered', bib=17)."""
    text = _entry("MSG", key)
    return text.format(**kwargs) if kwargs else text


def help_text(*keys: str, **kwargs) -> str:
    """The tooltip for a field, one or more entries of HELP joined by a space.

    Raises on an unknown key, like `ui` and `msg`: a tooltip that silently came
    back empty is how a field ends up with no help at all and nobody notices.
    An empty key is skipped, which is what makes a conditional part readable:
    `help_text("n_events", reserves="")`.
    """
    parts = [_entry("HELP", k) for k in keys if k]
    return " ".join(p.format(**kwargs) if kwargs else p for p in parts)


def code_name(code: str) -> str:
    """What a finding is about, as the jury reads it ('bib_dup' -> 'Dorsale doppio')."""
    try:
        return _entry("CODES", code)
    except KeyError:
        return str(code).replace("_", " ").capitalize()


def status_name(code: str) -> str:
    """Spelled-out status, for the pickers ('DNF' -> 'Ritirato')."""
    try:
        return _entry("STATUS_NAMES", str(code).upper())
    except KeyError:
        return str(code)


def penalty_name(code: str) -> str:
    """Spelled-out degree of a penalty ('C' -> 'Retrocessione')."""
    try:
        return _entry("PENALTIES", str(code).upper())
    except KeyError:
        return str(code)


def round_short(name: str) -> str:
    """A prova as a column heading calls it ('Eliminazione' -> 'Elim.').

    Only the ones that do not fit are abbreviated (`ROUNDS_SHORT`); everything
    else is the name the programme schedules the fase under, unchanged.
    """
    try:
        return _entry("ROUNDS_SHORT", str(name))
    except KeyError:
        return str(name)


def note_kind_name(kind: str) -> str:
    """What a block on a sheet is ('relegation' -> 'Retrocessione')."""
    try:
        return _entry("NOTE_KINDS", str(kind))
    except KeyError:
        return str(kind)


def ordinal(n: int | str) -> str:
    """The place as the sheets write it (1 -> '1°' / '1st').

    Every rank column, every final named after what it rides for. A language
    that has no rule for it falls back to the number, which is still readable.
    """
    try:
        return catalogue().ordinal(int(n))
    except (AttributeError, TypeError, ValueError):
        return str(n)


def plural(n: int, one: str, many: str) -> str:
    """Pick the form that agrees with `n` ('passa' / 'passano')."""
    return one if n == 1 else many


def gendered(female: bool, key_m: str, key_f: str, **kwargs) -> str:
    """The form written about the riders in front of the jury.

    A sheet is written about who rides it: *la vincitrice* of a batteria in a
    categoria femminile, *il vincitore* in a maschile. `Competition.female`
    decides, and this picks the wording. A language that does not inflect for
    it - English - carries the same sentence under both keys.
    """
    return msg(key_f if female else key_m, **kwargs)
