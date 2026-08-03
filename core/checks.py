"""What the app checks about what the jury types, in one place.

Two kinds of check live here.

**Inline flags** - the short red mark under a field, while it is being filled
in. Three fields grew their own version of it (the sprints, the composition of
a keirin batteria, its arrival) and the three drifted apart: one said `?12` for
a bib that is not entered, another said nothing; one counted what was missing,
another did not. `bib_line` is the one implementation, so one notation holds
everywhere and `i18n.HELP["flags"]` is the one legend that explains it:

    ?N   the bib N is not among the entrants of this race / heat
    !N   the bib N is written twice
    -N   N bibs are still missing from the line
    <N   fewer than N riders were placed (a sprint scores four)
    ?    the line cannot be read at all

**Issues** - a finding with a level and a code, which is what the entry-list
validation already produced. `Issue` lives here rather than in `core.entries`
so that anything else that validates (a race, the register) reports the same
shape and the UI renders every finding the same way (`ui.notify.issues`).

Nothing here imports streamlit, and nothing here writes Italian: the wording is
in `core.i18n`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .parse import ParseError, parse_bibs

# The flag notation, in one place. Documented for the jury in HELP["flags"].
FLAG_UNKNOWN = "?"       # ?N - not one of the entrants
FLAG_TWICE = "!"         # !N - written twice
FLAG_MISSING = "-"       # -N - N still missing
FLAG_TOO_FEW = "<"       # <N - fewer than N placed
FLAG_UNREADABLE = "?"    # ?  - the line does not parse

# How many offending numbers a flag names before it gives up: past three the
# mark is longer than the field it sits under, and the point is made.
MAX_NAMED = 3


# ── levels ──────────────────────────────────────────────────────────────────

ERROR = "error"    # something the jury has to fix before the sheet goes out
WARN = "warn"      # something to look at
INFO = "info"      # something worth knowing
LEVELS = (ERROR, WARN, INFO)


@dataclass
class Issue:
    """One finding, of any kind: level, a code to group by, and the wording."""

    level: str            # ERROR | WARN | INFO
    code: str
    message: str
    rider: str = ""


# ── inline flags ────────────────────────────────────────────────────────────

@dataclass
class BibLine:
    """One line of bibs as typed, and what does not add up about it."""

    bibs: list[str]
    flag: str = ""

    @property
    def ok(self) -> bool:
        return not self.flag


def _named(values, mark: str) -> str:
    """`!47,51` - the mark and the first few numbers it applies to."""
    uniq = list(dict.fromkeys(str(v) for v in values))
    return mark + ",".join(uniq[:MAX_NAMED]) if uniq else ""


def bib_line(text: str, *, expected=(), seen: set[str] | None = None,
             need: int = 0, min_placed: int = 0,
             repeats_ok: bool = False) -> BibLine:
    """Read one line of bibs and say what is wrong with it.

    `expected`  who may legitimately appear here (the entrants of the race, or
                of this batteria). Anything else is flagged `?N`.
    `seen`      numbers already used on the lines above, updated in place: a
                rider written into two batterie is flagged `!N` on the second.
                A repeat *inside* one line is flagged whether or not it is
                passed.
    `need`      how many numbers the line should hold. What is short is flagged
                `-N` - a count and not names, because while a batteria is being
                written down the missing ones are simply not typed yet.
    `min_placed` the least number of riders a valid line places (a sprint
                scores four): fewer is flagged `<N`.
    `repeats_ok` where writing the same number twice means something. The giri
                guadagnati are the case: `3, 3` is two laps, not a mistake.

    An empty line is not a mistake: nothing has been typed yet.
    """
    try:
        bibs = [str(b) for b in parse_bibs(text)]
    except ParseError:
        return BibLine([], FLAG_UNREADABLE)
    if not bibs:
        return BibLine([], "")

    pool = {str(b) for b in expected}
    bits = []
    if pool:
        bits.append(_named([b for b in bibs if b not in pool], FLAG_UNKNOWN))
    if not repeats_ok:
        twice = [b for b in bibs if bibs.count(b) > 1
                 or (seen is not None and b in seen)]
        bits.append(_named(twice, FLAG_TWICE))
    if seen is not None:
        seen.update(bibs)
    if need:
        # counted against what belongs here: a stray number is already flagged
        # `?N` and must not also make the line look complete
        short = need - len({b for b in bibs if not pool or b in pool})
        if short > 0:
            bits.append(f"{FLAG_MISSING}{short}")
    if min_placed and len(bibs) < min_placed:
        bits.append(f"{FLAG_TOO_FEW}{min_placed}")
    return BibLine(bibs, " ".join(b for b in bits if b))
