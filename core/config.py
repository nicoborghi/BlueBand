"""Competition configuration: the YAML programme and its derived defaults.

Vocabulary is the UCI one: a *competition* is the meeting, an *event* is what a
title is awarded in (Sprint, Keirin, Omnium, Madison), a *round* is one stage of
an event (qualifying, repechages, final). Italian is display only - see
`core.i18n`.

One file per competition (`<competition>/programme.yaml`) defines the track, the
categories, the events contested by each, the rounds of every event with their
distance / laps / sprints, the day-by-day running order, the layout of the entry
workbook and the communiqué register. Anything omitted falls back to values
derived from the track length, so a generic race with no programme still works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from math import ceil
from pathlib import Path
from typing import Any

import yaml

from .formats.omnium import TEMPO as _TEMPO_ROUND
from .i18n import fix_accents, msg, word

#: The name the tempo race is scheduled under inside an omnium, lowercased:
#: which prova a round is, is its name (see `race.round_format`).
TEMPO_RACE = _TEMPO_ROUND.lower()

# How a round names itself in the programme. Two words carry meaning for the
# code - a *qualifying* round is ridden against the clock, a *finals* round
# rides for places instead of qualifying for them - and both are matched on the
# first letters, so "Finale", "Finali", "Qualificazioni Batteria 1" all read.
# They live here, with the rest of the programme's vocabulary, because more
# than the service layer reads them: so does the table of regulation distances
# (`core.distances`), which is asked for "the qualifying distance" and must
# answer without knowing what a race is.
PREFIX_QUALIFYING = "qualificazioni"
PREFIX_FINALS = "final"

DEFAULT_TRACK_LEN = 0.3333  # km


# ── Documents produced for a race ───────────────────────────────────────────

# The values are the vocabulary of programme.yaml (and of the transcribed
# register), so they stay Italian; the names, and everything the code says
# about them, are English.
DOC_STARTLIST = "partenti"
DOC_RESULTS = "risultati"
DOC_CLASSIFICATION = "classifica"
DOC_KINDS = (DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION)

# A velocità files two results sheets on one round, because two races are
# ridden there: the recuperi belong to the first round and the 5°-8° final to
# the finals. They are documents, not rounds - the comunicato that carries
# them is the one of the round they are ridden in.
DOC_RESULTS_REP = "risultati_recuperi"
DOC_RESULTS_58 = "risultati_5-8"

# A keirin rides its recuperi inside the round that sends riders to them too,
# but publishes their ordine di partenza as a comunicato of its own (the
# batterie are composed from a table, not read off the results above them), and
# its finals round rides a second final for the places under the title - 7°-12°
# with twelve riders, 7°-10° with ten. Which places exactly is not in the name:
# it is computed from how many ride it (`formats.keirin.final_labels`).
DOC_STARTLIST_REP = "partenti_recuperi"
DOC_RESULTS_B = "risultati_finale_b"

# An omnium files two sheets more on its prove. Each of the first three closes
# on a *classifica parziale*: the standings after that prova, which are also the
# ordine di partenza of the one that follows - so that is the sheet the register
# carries a number for, and the risultati of the prova itself go out unnumbered.
# The tempo race splits its result in two: the *gara*, with a column per volata,
# which is the jury's own sheet, and the *risultati*, which publish the order
# and the omnium points it is worth.
DOC_PARTIAL = "classifica_parziale"
DOC_RACE = "gara"

#: The two sheets of the recuperi: a velocità and a keirin file them, and
#: they are the pair a programme turns on or off together.
DOC_REPECHAGE_KINDS = (DOC_STARTLIST_REP, DOC_RESULTS_REP)

DOC_ALL_KINDS = (DOC_STARTLIST, DOC_STARTLIST_REP, DOC_RACE, DOC_RESULTS,
                 DOC_RESULTS_REP, DOC_RESULTS_58, DOC_RESULTS_B,
                 DOC_PARTIAL, DOC_CLASSIFICATION)

# The sheets that carry a result - what "solo in risultati e classifiche"
# means when the signature is set to be offered on those alone.
DOC_RESULT_KINDS = (DOC_RACE, DOC_RESULTS, DOC_RESULTS_REP, DOC_RESULTS_58,
                    DOC_RESULTS_B, DOC_PARTIAL, DOC_CLASSIFICATION)

# The entry list is not a real event: it is the pseudo-event the four opening
# communiqués (one per category) hang off in the register.
EVENT_ENTRY_LIST = "entry_list"

# What "squadra" means at a given competition: the rider field the app groups
# by. A rappresentativa regionale enters the riders at an Italian championship,
# a società at an open meeting, and a nation at an international one - so it is
# read from the programme (`entries.team_group`), never assumed.
TEAM_GROUPS = ("region", "club", "province", "nation")
DEFAULT_TEAM_GROUP = "region"

# A round that is composed instead of ridden (`kind: setup` in the programme):
# the madison pairing, where every coppia gets its number and its batteria.
ROUND_SETUP = "setup"

# A pause is not a race either: it is time the giornata spends not racing - the
# premiazioni, the intervallo, the pista bagnata - and the timetable has to be
# able to say so, because an hour that is not accounted for is an hour every
# orario under it is wrong by. It is written as a programme item on the
# pseudo-event `pause` carrying one round of `kind: pause`: that way it sits in
# the running order like everything else (`rounds_on`), is moved and re-timed by
# the same page, and files no document - so no comunicato hangs off it.
EVENT_PAUSE = "pause"
ROUND_PAUSE = "pause"

# Madison, 3.2.157: teams the track takes in the final, by track length. The
# heats are run to qualify *up to* this number, not necessarily to fill it.
MADISON_TRACK_TEAMS = {166: 12, 200: 15, 250: 18, 285.714: 18, 333.33: 20,
                       400: 20}

# 3.2.157 again: whatever the arithmetic says, a heat never eliminates fewer
# than two teams.
MIN_ELIMINATED = 2


def is_pause(item) -> bool:
    """Whether this programme item is a pause and not a race.

    Asked wherever the programme is read as a list of *gare* - the checks, the
    printed sheets, the pages that pick a categoria and an event - because
    a pause has neither and would come out as a race with two empty fields.
    """
    return getattr(item, "event", "") == EVENT_PAUSE


def madison_track_teams(track_len_km: float) -> int:
    """Teams the track takes in a madison final (0 when the length is unknown)."""
    metres = round((track_len_km or 0) * 1000, 2)
    for length, teams in MADISON_TRACK_TEAMS.items():
        if abs(metres - length) < 1:
            return teams
    return 0


# ── Schema ──────────────────────────────────────────────────────────────────

@dataclass
class Category:
    code: str
    name: str = ""  # "UOMINI ALLIEVI"
    sex: str = ""
    order: int = 0
    #: Which licence categories this one takes in, for a categoria that is not
    #: one: an *open* is ridden by riders licensed EL, UN and master, and the
    #: entry list arrives with those sigle in it, not with the open's own. Each
    #: entry is a sigla, or a prefix with a `*` after it - `M*` is every master
    #: category there is, whatever number the federation gives it this year.
    #: Empty is the ordinary case: a categoria takes in itself.
    accepts: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.name = self.name or self.code

    def takes(self, cat: str) -> bool:
        """Whether a rider licensed `cat` rides in this categoria."""
        code = str(cat or "").strip().upper()
        if not code:
            return False
        if code == self.code.upper():
            return True
        return any(code.startswith(rule[:-1].upper()) if rule.endswith("*")
                   else code == rule.strip().upper()
                   for rule in self.accepts or [])


# Two-letter UCI codes, for the places where a column header has to fit in a
# few millimetres: the entry-list matrix and the check-in grid. `abbr:` in the
# programme wins; failing that the event code decides, then the format, then
# the initials of the short name.
ABBR_BY_CODE = {
    "vel_squadre": "TS", "ins_squadre": "TP", "ins_individuale": "IP",
    "velocita": "SP", "keirin": "KE", "madison": "MD", "omnium": "OM",
    "corsa_punti": "PR", "eliminazione": "EL", "scratch": "SC",
    "chilometro": "TT", "500": "TT", "entry_list": "",
}
ABBR_BY_FMT = {
    "timed_team": "TP", "timed": "IP", "sprint": "SP", "keirin": "KE",
    "madison": "MD", "omnium": "OM", "group": "PR", "elimination": "EL",
    "time_trial": "TT", "derny": "DE", "entrylist": "",
}


def initials(name: str) -> str:
    """'Ins. Squadre' -> 'IS', 'Omnium' -> 'OM'. Last-resort abbreviation."""
    words = [w for w in str(name).replace(".", " ").split() if w]
    if len(words) > 1:
        return "".join(w[0] for w in words[:3]).upper()
    return (words[0][:2].upper() if words else "")


@dataclass
class Event:
    code: str
    name: str = ""  # "Inseguimento a Squadre"
    short: str = ""
    abbr: str = ""  # "TP" - UCI code for narrow column headers
    fmt: str = "group"  # group | elimination | timed | timed_team |
    # sprint | keirin | omnium | madison | time_trial | derny
    entry_columns: list[str] = field(default_factory=list)  # workbook column headers
    team_size: int = 0  # team competitions: riders per team
    # How many start together in a timed round - teams or riders. An
    # inseguimento starts two, one on each straight; a velocità a squadre and
    # the 200 m lanciati of a velocità start one at a time, so their
    # qualifying has no batterie at all - it has a start order, everyone in
    # it, and the sheet counts starts, not heats. Rounds ridden man against
    # man - the finals, a bracket - are batterie whatever this says.
    teams_per_start: int = 2
    #: How long one fase of this event takes, in minutes - what the
    #: timetable is built out of when a fase says nothing (`Round.duration`).
    #: The same at every championship, so it is a column of the catalogue
    #: (`regulations/events.json`) and not seven numbers typed into every
    #: programme. `0` = unknown, and a giornata of unknowns has no orari.
    minutes: int = 0
    startlist_note: str = ""  # default note of every start order
    # part of that default on the qualifying rounds only: on the finals it
    # would announce a qualification that has already happened. It is also
    # what the risultati of a qualifying round open on - the sheet that says
    # who went through is where the jury writes how many do
    qualifying_note: str = ""
    # and on the finals instead: where the squadre line up when they are two
    finals_note: str = ""
    # The same three lines written about the riders in front of the jury: "La
    # prima atleta parte sul rettilineo d'arrivo" on a categoria femminile. A
    # line that reads the same either way - a squadra is feminine in Italian
    # whoever rides it - needs no second form and falls back to the one above.
    startlist_note_f: str = ""
    qualifying_note_f: str = ""
    finals_note_f: str = ""
    order: int = 0

    def note(self, *, finals: bool = False, female: bool = False) -> str:
        """Text a start order's `Decisione / note` starts from.

        It is only a default: what prints is whatever stands in that field.
        The line that belongs to the round comes first - where the squadre
        start - then what holds all day, then what this round qualifies for.
        """
        def line(name: str) -> str:
            return ((getattr(self, f"{name}_f") if female else "")
                    or getattr(self, name))

        return "\n".join(p for p in (
            line("finals_note") if finals else "",
            line("startlist_note"),
            "" if finals else line("qualifying_note")) if p)

    def __post_init__(self):
        self.name = self.name or self.code
        self.short = self.short or self.name
        if not self.abbr:
            self.abbr = ABBR_BY_CODE.get(
                self.code, ABBR_BY_FMT.get(self.fmt, initials(self.short)))


@dataclass
class Round:
    """One round of an event (qualifying, first round, repechages, final)."""

    key: str
    label: str = ""
    distance: float | None = None  # km
    laps: float | None = None
    sprints: int | None = None
    # None: the usual two sheets, or none at all on a round that is not ridden
    docs: list[str] | None = None
    heat_size: int | None = None  # sprint/keirin: riders per heat
    qualify: int | None = None  # how many advance from each heat
    # A round that is not ridden: `kind: setup` is where the jury composes the
    # event before it starts (madison: the number of every coppia and the
    # batteria it rides in). It issues no comunicato of its own.
    kind: str = ""
    # Madison qualifying heats (3.2.157): teams eliminated from *each* heat,
    # never fewer than 2, counted among those who started.
    eliminate: int | None = None
    #: How long this fase takes, in minutes. It is what the jury actually
    #: knows - a finale is ten minutes, a corsa a punti of thirty giri is
    #: half an hour - and every orario of the giornata follows from it and
    #: from the running order (`Competition.schedule`).
    #:
    #: `None` is not zero: it means *whatever this event usually takes*
    #: (`Event.minutes`), the same way an empty distance means whatever follows
    #: from the track. A programme therefore has a timetable before anybody has
    #: typed a single duration into it.
    #:
    #: There is no orario field. An hour typed on a fase was an anchor that no
    #: duration could move, which is the opposite of a timetable: the clock
    #: starts once, at the start of the giornata, and the durate carry it.
    duration: int | None = None
    #: The jury's own note about this fase. It is *not* printed: it stays in
    #: the programme, where a comment would not survive a save.
    note: str = ""
    #: The line this fase opens its ordine di partenza on, above what the
    #: event always says (`Event.note`). This one *is* printed.
    #:
    #: It is the programme's, and the programme is where it is decided: the
    #: regulation says what a fase announces - who it qualifies, where the
    #: first squadra lines up - and `core.notes` resolves that onto the fase
    #: when the race is added. Typed over, it stays typed over.
    sheet_note: str = ""
    #: The same for the risultati of this fase: the sheet that says who went
    #: through is the one that has to say how many do. Two fields and not a
    #: mapping per document, because those are the two sheets a fase files that
    #: open on a decision (`core.notes` writes both).
    results_note: str = ""
    #: The giornata this fase is ridden on, when it is not the one of the race
    #: it belongs to. A velocità qualifies on the Saturday and rides its finali
    #: on the Sunday, and it is one race either way: the fasi carry the day, the
    #: race stays one `ProgrammeItem` (which is what every lookup reads).
    #: `0` = the day of the race, which is what a file that splits nothing says.
    day: int = 0
    #: Where this fase runs in its giornata: 1, 2, 3 … as the jury numbers the
    #: scaletta. `0` = wherever the programme order puts it, which is what every
    #: file that has never been reordered says. It is the running order, so the
    #: register follows it (`communiques.sheet_order`).
    seq: int = 0

    def __post_init__(self):
        self.label = self.label or self.key
        if self.docs is None:
            self.docs = ([] if self.kind in (ROUND_SETUP, ROUND_PAUSE)
                         else [DOC_STARTLIST, DOC_RESULTS])


@dataclass
class ProgrammeItem:
    """One (category, event) contest with its rounds, as scheduled.

    The three optional fields under the rounds are what the *format* runs, as
    opposed to what the rounds are: whether a velocità qualifies twelve or
    eight, whether it rides the 5°-8° final, whether a keirin rides its second
    one. They used to be nowhere - inferred from the round list and from the
    documents a round files, and re-decided inside the race on the day. Stated
    here they are a decision the programme carries, and `None` still means "not
    stated", so a file written before this existed reads exactly as it did.
    """

    cat: str
    event: str
    day: int = 0
    rounds: list[Round] = field(default_factory=list)
    #: velocità: how many the 200 m qualifies ("12" | "8"), see formats.sprint
    scheme: str = ""
    #: velocità: is the final for 5th-8th place ridden
    final_5_8: bool | None = None
    #: keirin: is the second final (the one under the title) ridden
    final_b: bool | None = None
    #: How many start together in a timed round *for this categoria*. The
    #: event states the usual shape (`Event.teams_per_start`), and it is
    #: not always the same one: a chilometro is ridden two at a time by a
    #: categoria with thirty entered and one at a time by the eight of another,
    #: on the same afternoon. `None` = whatever the event says.
    teams_per_start: int | None = None
    #: How many atleti a squadra fields *in this race*. The regulation states
    #: the usual number per event (`Event.team_size`: four in an
    #: inseguimento a squadre, three in a velocità a squadre) and that is what
    #: a programme saying nothing rides; a categoria that has been authorised
    #: to ride it with one fewer says so here, and the check-in, the composizione
    #: and the sheets all read the same number. `None` = whatever the
    #: event says.
    team_size: int | None = None
    note: str = ""


@dataclass
class Sheet:
    """One document carried by a comunicato: which race, and which of its sheets.

    A comunicato is a *number on paper*, and more than one document can be
    printed under it - which is what the velocità and the keirin have always
    done: the risultati of a round and the ordine di partenza of the round they
    compose go out together. `Sheet` is one of those documents.
    """

    cat: str = ""
    event: str = ""
    # None means "the same fase as the sheet above": a recuperi start order is
    # published inside the round that sends the riders to them. An explicit ""
    # is the other answer, and a real one - a classifica belongs to the
    # event and to no round at all.
    round_key: str | None = None
    doc: str = ""

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.cat, self.event, self.round_key or "", self.doc)


@dataclass
class CommuniqueSpec:
    """One planned entry of the communiqué register.

    The fields name the *first* document, which is what the sheet is: it gives
    the title and the file name. `extra` are the further documents printed
    under it, each inheriting whatever it does not say (a recuperi start order
    is the same cat and event as the results above it, and often the same
    round). Left empty - which is every entry of a register transcribed before
    this existed - the comunicato carries the one document, as it always did.
    """

    n: int
    day: int = 0
    cat: str = ""
    event: str = ""
    round_key: str = ""           # YAML says `round`, see load_competition
    doc: str = ""
    title: str = ""
    ret: bool = False             # annullato (printed as "NN RET")
    #: Typed by hand rather than handed out by the numbering
    #: (`communiques.autonumber`), which then never moves it again. A number
    #: the jury chose is a number somebody is expecting on paper.
    pinned: bool = False
    extra: list[Sheet] = field(default_factory=list)   # YAML says `with`

    @property
    def label(self) -> str:
        return f"{self.n} RET" if self.ret else str(self.n)

    @property
    def sheets(self) -> list[Sheet]:
        """Every document this comunicato carries, in the order they print.

        The first is the comunicato's own; each of the others fills in from it
        what it does not say for itself.
        """
        first = Sheet(cat=self.cat, event=self.event,
                      round_key=self.round_key or "", doc=self.doc)
        return [first] + [
            Sheet(cat=s.cat or first.cat, event=s.event or first.event,
                  round_key=(first.round_key if s.round_key is None
                             else s.round_key),
                  doc=s.doc or first.doc)
            for s in self.extra]

    def carries(self, cat: str, event: str, round_key: str, doc: str) -> bool:
        """Whether this comunicato is the one that publishes that sheet."""
        return (cat, event, round_key, doc) in [s.key for s in self.sheets]


# What kind of meeting the programme is for. It settles one thing: whether the
# winner of an event is a champion. `CAMPIONE D'ITALIA` under a name is a
# title assigned, and a trofeo assigns none - the band simply does not print.
# Championship is the default: it is what the app was written for, and every
# programme made before the choice existed is one.
KIND_CHAMPIONSHIP = "championship"
KIND_ORDINARY = "ordinary"
# A Trofeo delle Regioni is an ordinary meeting as far as a single race is
# concerned - no title is assigned on it, so no band is printed - and one thing
# more: the meeting as a whole is scored, prova by prova, into a classifica per
# regione (`core.trofeo`, art. 8 and 9 of the regolamento). The winner of that
# classifica is the champion, and it is the only place the band belongs.
KIND_TROFEO_REGIONI = "trofeo_regioni"
COMPETITION_KINDS = (KIND_CHAMPIONSHIP, KIND_ORDINARY, KIND_TROFEO_REGIONI)

# How the "Per la giuria" block is signed, and where it is offered by default.
SIG_IMAGE = "image"      # the scanned signature, as it has always been
SIG_TEXT = "text"        # the secretary's name, typed in bold
SIG_MODES = (SIG_IMAGE, SIG_TEXT)

SIG_ALWAYS = "always"    # every sheet opens with the tick on
SIG_RESULTS = "results"  # only risultati and classifiche
SIG_NEVER = "never"      # never on by default - the jury ticks it by hand
SIG_SCOPES = (SIG_ALWAYS, SIG_RESULTS, SIG_NEVER)

# How a rider is named on a printed sheet.
NAME_SPLIT = "split"     # two columns: Cognome, Nome
NAME_FULL = "full"       # one column: "ROSSI Mario Luigi"
NAME_STYLES = (NAME_SPLIT, NAME_FULL)

#: How wide the merged «Nome» column is, as a fraction of the two columns it
#: replaces. "ROSSI Mario Luigi" is one string on one line: it does not need
#: the width of two columns each sized to hold a long name by itself, and what
#: it gives up goes to the columns the sheet is actually read for - the volate,
#: i punti, la società. Set in Impostazioni → Nome; the bounds are what keeps
#: a name readable at one end and the sheet readable at the other.
DEFAULT_NAME_WIDTH = 0.62
NAME_WIDTH_MIN = 0.40
NAME_WIDTH_MAX = 1.00

# How the two images that frame a sheet are laid on the paper.
FIT_PAGE = "page"        # edge to edge, the way a letterhead is drawn
FIT_SIZE = "size"        # a width of its own, placed left / centre / right
IMAGE_FITS = (FIT_PAGE, FIT_SIZE)

ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT = "left", "center", "right"
ALIGNS = (ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)

#: A logo that is not the width of the paper is given one, as a percentage of
#: it. Below the floor it prints as a smudge nobody can read and above the
#: ceiling it is the page again, so the two ends are held here rather than in
#: the widget: settings.json is written by anything.
DEFAULT_IMAGE_WIDTH = 60.0
IMAGE_WIDTH_MIN = 5.0
IMAGE_WIDTH_MAX = 100.0

#: What can be printed on a line of its own above the table (under the testata)
#: or under it (over the piè di pagina). Three slots per line - a sinistra, al
#: centro, a destra - and each of them holds one of these, or nothing.
#:
#: Until now the two were fixed: «Comunicato n.» sat in the head with a side of
#: its own and «Emesso il …» was pinned bottom right, and a letterhead that
#: already carries something in one of those corners had nowhere to move them
#: to. One list, six slots, and a sheet is laid out rather than argued with.
#:
#: An empty slot is `"none"` and not `""`: it is a choice - the jury cleared
#: that corner - and settings.json drops an empty value as "never set"
#: (`store.set_setting`), which would hand the default straight back.
SLOT_NONE = "none"
SLOT_COMMUNIQUE = "communique"
SLOT_PRINTED_AT = "printed_at"
SLOT_ITEMS = (SLOT_NONE, SLOT_COMMUNIQUE, SLOT_PRINTED_AT)

#: The three slots of a line, in the order they print.
SLOT_SIDES = (ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT)

#: How much air can be asked for between a line of slots and the edge it sits
#: against - the top of the paper or the testata above it, the foot of the
#: paper or the piè below it - in millimetres. The ceiling is what still leaves
#: a sheet worth printing between the two.
SLOT_GAP_MAX = 60.0

#: How far the image is held off its edge of the paper, in millimetres: the
#: testata from the top, the piè from the bottom. Zero is what a letterhead
#: wants - it bleeds to the edge - and the ceiling is what still leaves a
#: sheet worth printing under it.
IMAGE_OFFSET_MAX = 50.0

#: The tint of each kind of block printed under a table, keyed by
#: `core.decisions.NOTE_KINDS`. A comunicato is read across a table by people
#: who are not going to read it twice, so what a block *is* has to arrive
#: before the sentence does: the ramp of the provvedimenti runs yellow (an
#: ammonizione, which costs nothing yet) to red (a squalifica, which ends the
#: race), the ammenda sits off that ramp because a fine is not a step on it,
#: and the plain note keeps the grey it has always had - it sanctions nobody.
#: Every one of them is overridable in Impostazioni: some federations print in
#: their own colours, and a tint nobody can change is a tint that gets argued
#: about instead of read.
NOTE_COLORS = {
    "disqualification": "#fecaca",
    "relegation": "#fed7aa",
    "fine": "#ddd6fe",
    "warning": "#fef08a",
    "note": "#f4f6f8",
}


#: The characters a sheet is set in, element by element. One entry per thing a
#: comunicato prints - the titolo, the sottotitolo, the riquadro «Comunicato
#: n.», the blocks under the table - keyed the way `print.css` names it: every
#: key here is the custom property `--font-<key>` on the wrapper of the page
#: (`render.font_css_vars`), and the stylesheet states the shape of an element
#: and takes its character from there. So a federation that prints in its own
#: typeface, or a jury that wants the titolo two points larger, sets it in
#: Impostazioni instead of editing a stylesheet nobody ships a copy of.
#:
#: `family` is the typeface of the whole sheet and is a font stack; everything
#: else is a size, in whatever CSS length the jury writes it (`pt` on paper).
#: The defaults are what every sheet printed until this could be changed.
FONT_FAMILY = "family"
FONTS = {
    FONT_FAMILY: '"Helvetica Neue", Helvetica, Arial, sans-serif',
    "title": "15pt",
    "subtitle": "12pt",
    "table_title": "12pt",
    "info": "9pt",
    "legend": "7.5pt",
    "communique": "10pt",
    "printed_at": "8pt",
    "decision": "9.5pt",
    "decision_tag": "8pt",
    "signature_label": "9pt",
    "signature": "10pt",
    "body": "10pt",
    "footline": "8pt",
}

#: A size as it may be written: a number and a CSS unit, nothing else. The
#: value goes into the `style` of the page, so what is not a length is not
#: written at all - a stray `}` in a settings file is a sheet that stops
#: looking like a comunicato halfway down.
FONT_SIZE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:pt|px|mm|cm|in|em|rem|%)\Z")

#: And a typeface: names, quotes, commas and spaces. Same reason.
FONT_FAMILY_RE = re.compile(r"[\w \-,'\"]+\Z")


def font_value(key: str, value) -> str:
    """`value` as it may be printed for `key`, or "" when it may not be.

    Called on the way in - what a settings file offers is not what a stylesheet
    has to accept - so a value that does not read as a font falls back to the
    default rather than reaching the page.
    """
    text = str(value or "").strip()
    if not text or key not in FONTS:
        return ""
    pattern = FONT_FAMILY_RE if key == FONT_FAMILY else FONT_SIZE_RE
    return text if pattern.match(text) else ""


#: What colour each of those elements is printed in. Same keys as `FONTS` -
#: one picker in Impostazioni sets the character and the colour of the same
#: element - and the same custom-property trick: `--color-<key>` on the wrapper
#: of the page (`render.color_css_vars`).
#:
#: `COLOR_HEADER` is the value of the two that follow the letterhead: the
#: titolo and the riquadro «Comunicato n.» are printed in the colour of the
#: competition (`Branding.color`), which a programme may set and a jury may
#: change, so they are written down as "the letterhead colour" and not as the
#: hex it happens to be today. `family` is the colour of the sheet's own text -
#: everything that says nothing else.
#:
#: Only what is *different* from these is stored (`Branding.text_colors`): a
#: titolo saved as the hex of the letterhead would stop following it the day
#: the letterhead changes.
COLOR_HEADER = "header"

#: The colour of a competition that has not chosen one - the blue every sheet
#: has been printed in - and what `COLOR_HEADER` resolves to without one.
DEFAULT_COLOR = "#0a5688"

TEXT_COLORS = {
    FONT_FAMILY: "#111111",
    "title": COLOR_HEADER,
    "subtitle": "#111111",
    "table_title": "#111111",
    "info": "#444444",
    "legend": "#555555",
    "communique": COLOR_HEADER,
    "printed_at": "#777777",
    "decision": "#111111",
    "decision_tag": "#111111",
    "signature_label": "#111111",
    "signature": "#111111",
    "body": "#111111",
    "footline": "#777777",
}

#: A colour as the sheet may print it: `#rrggbb`, which is what the picker in
#: Impostazioni writes and the only thing that goes into the style of a page.
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\Z")


def text_color(key: str, value) -> str:
    """`value` as it may be printed for `key`, or "" when it may not be."""
    text = str(value or "").strip()
    if not text or key not in TEXT_COLORS:
        return ""
    return text if COLOR_RE.match(text) else ""


def default_text_color(key: str, header: str = "") -> str:
    """The colour `key` is printed in when nobody has changed it.

    `header` is the colour of the competition, for the two elements that follow
    it - the picker has to open on the colour the sheet is really printing, not
    on the word "header".
    """
    value = TEXT_COLORS.get(key, "")
    if value == COLOR_HEADER:
        header = str(header or "").strip()
        return header if COLOR_RE.match(header) else DEFAULT_COLOR
    return value


@dataclass
class Branding:
    """How the sheets look: the images, the signature, the way names are set.

    Everything here is a local choice rather than a fact of the competition, so
    it is normally set in Impostazioni and stored in `settings.json` (see
    `ui.state.BRANDING_SETTINGS`); the programme can still carry a default.
    """

    header_img: str = ""
    footer_img: str = ""
    #: How each of the two is laid on the paper: `FIT_PAGE` - the default -
    #: prints it edge to edge the way a letterhead is drawn, `FIT_SIZE` gives
    #: it a width of its own (percent of the sheet) and a side to sit on. A
    #: federation logo is not a letterhead: it has its own proportions, and
    #: stretching it across A4 is the one thing that must not happen to it.
    header_fit: str = FIT_PAGE
    header_width: float = DEFAULT_IMAGE_WIDTH   # % of the sheet, when sized
    header_align: str = ALIGN_CENTER
    header_top: float = 0.0                     # mm off the top of the paper
    footer_fit: str = FIT_PAGE
    footer_width: float = DEFAULT_IMAGE_WIDTH
    footer_align: str = ALIGN_CENTER
    footer_bottom: float = 0.0                  # mm off the bottom of the paper
    #: Which side of the sheet the «Comunicato n.» box sits on. Kept for the
    #: settings.json written before the slots below existed: it is read once,
    #: to place the comunicato in the head, and nothing else asks for it.
    communique_align: str = ALIGN_RIGHT
    #: The three slots of the line under the testata and the three of the line
    #: over the piè, each holding one of `SLOT_ITEMS` or nothing. `None` is
    #: "never set": the head is then filled from `communique_align` and the
    #: foot keeps «Emesso il …» bottom right, which is what every sheet printed
    #: until now looks like. An empty string is a slot the jury has cleared.
    head_left: str | None = None
    head_center: str | None = None
    head_right: str | None = None
    #: Millimetres of air under the top of the paper (or under the testata)
    #: before the line of head slots, and over the bottom of the paper (or over
    #: the piè) after the line of foot slots.
    head_gap: float = 0.0
    foot_left: str | None = None
    foot_center: str | None = None
    foot_right: str | None = None
    foot_gap: float = 0.0
    color: str = DEFAULT_COLOR
    signature: str = ""  # image of the handwritten signature
    #: What the block is headed with. Empty - which is the normal case - is the
    #: catalogue word for the language in force, read through
    #: `signature_caption`: a default evaluated here would freeze the Italian
    #: wording into every programme loaded before the language was chosen.
    signature_label: str = ""
    signature_mode: str = SIG_IMAGE
    signature_name: str = ""      # printed in bold when the mode is `text`
    signature_scope: str = SIG_ALWAYS
    name_style: str = NAME_SPLIT
    name_width: float = DEFAULT_NAME_WIDTH
    #: Whether the block of a decision opens with the compact UCI code it was
    #: taken under (`A1`, `C3`). Off: the sentence is what goes out to the
    #: teams, and the article is in the register the jury keeps. A panel that
    #: quotes the code on paper turns it on in Impostazioni.
    decision_codes: bool = False
    #: kind -> hex tint, filled in from `NOTE_COLORS` for anything not set
    note_colors: dict[str, str] = field(default_factory=dict)
    #: element -> the character it is set in, filled in from `FONTS` for
    #: anything not set. Same shape and same reason as `note_colors`: what the
    #: jury changed is written down, the rest follows the app.
    fonts: dict[str, str] = field(default_factory=dict)
    #: element -> the colour it is printed in, and *only* where that is not
    #: the default (`TEXT_COLORS`): unlike the characters this one is stored
    #: sparse, because two of the defaults are «the colour of the letterhead»
    #: and writing today's hex into them is how a titolo stops following it.
    text_colors: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # the width comes from settings.json, which anything may have written:
        # a bad value narrows every printed name at once, so it is clamped here
        # rather than trusted down in the renderer
        try:
            width = float(self.name_width)
        except (TypeError, ValueError):
            width = DEFAULT_NAME_WIDTH
        self.name_width = min(NAME_WIDTH_MAX, max(NAME_WIDTH_MIN, width))
        # same for the two images: an unreadable fit or a width off the paper
        # would come out on every sheet of the meeting
        for which in ("header", "footer"):
            if getattr(self, f"{which}_fit") not in IMAGE_FITS:
                setattr(self, f"{which}_fit", FIT_PAGE)
            if getattr(self, f"{which}_align") not in ALIGNS:
                setattr(self, f"{which}_align", ALIGN_CENTER)
            try:
                w = float(getattr(self, f"{which}_width"))
            except (TypeError, ValueError):
                w = DEFAULT_IMAGE_WIDTH
            setattr(self, f"{which}_width",
                    min(IMAGE_WIDTH_MAX, max(IMAGE_WIDTH_MIN, w)))
            edge = "header_top" if which == "header" else "footer_bottom"
            try:
                off = float(getattr(self, edge))
            except (TypeError, ValueError):
                off = 0.0
            setattr(self, edge, min(IMAGE_OFFSET_MAX, max(0.0, off)))
        if self.communique_align not in ALIGNS:
            self.communique_align = ALIGN_RIGHT
        self._settle_slots()
        # a partial dict is the normal case - the jury recolours the squalifica
        # and leaves the rest alone - so what is missing falls back rather than
        # printing a block with no tint at all
        self.note_colors = {**NOTE_COLORS,
                            **{k: v for k, v in (self.note_colors or {}).items()
                               if k in NOTE_COLORS and str(v).strip()}}
        # and the characters: a value that does not read as a font is dropped
        # here rather than written into the style of every sheet
        self.fonts = {**FONTS,
                      **{k: font_value(k, v)
                         for k, v in (self.fonts or {}).items()
                         if font_value(k, v)}}
        # the colours the same way, and what says nothing - a hex equal to the
        # default, an element that is not one - is not a colour of its own
        self.text_colors = {
            k: text_color(k, v)
            for k, v in (self.text_colors or {}).items()
            if text_color(k, v)
            and text_color(k, v) != default_text_color(k, self.color)}

    def _settle_slots(self) -> None:
        """Fill the six slots in, migrate the old settings, drop the doubles.

        A competition set up before the slots existed has `None` in all six:
        its head carries the comunicato on the side `communique_align` names
        and its foot the «Emesso il …» bottom right, which is the sheet it has
        been printing all along. One that has been laid out here carries what
        was chosen, empty slots included.

        The same item twice on a sheet is a bug wherever it came from - a hand
        edit of settings.json, a slot moved without the old one being cleared -
        so the first slot that asks for it keeps it and the others go empty.
        """
        for line in ("head", "foot"):
            slots = [getattr(self, f"{line}_{s}") for s in SLOT_SIDES]
            if all(v is None for v in slots):
                slots = [SLOT_NONE] * 3
                item = SLOT_COMMUNIQUE if line == "head" else SLOT_PRINTED_AT
                side = (self.communique_align if line == "head"
                        else ALIGN_RIGHT)
                slots[SLOT_SIDES.index(side)] = item
            seen: set[str] = set()
            for i, value in enumerate(slots):
                value = value if value in SLOT_ITEMS else SLOT_NONE
                slots[i] = SLOT_NONE if value in seen else value
                seen.add(value)
            for side, value in zip(SLOT_SIDES, slots):
                setattr(self, f"{line}_{side}", value)
            gap = f"{line}_gap"
            try:
                mm = float(getattr(self, gap))
            except (TypeError, ValueError):
                mm = 0.0
            setattr(self, gap, min(SLOT_GAP_MAX, max(0.0, mm)))

    def slots(self, line: str) -> list[str]:
        """What the three slots of `head` / `foot` hold, left to right."""
        return [getattr(self, f"{line}_{side}") for side in SLOT_SIDES]

    def slot_side(self, line: str, item: str) -> str:
        """Which side of `line` prints `item`, '' when the line does not."""
        for side in SLOT_SIDES:
            if getattr(self, f"{line}_{side}") == item:
                return side
        return ""

    @property
    def signature_caption(self) -> str:
        """The line the signature block is headed with ("Per la giuria:")."""
        return self.signature_label or word("signature")

    def image_box(self, which: str) -> tuple[float, str]:
        """(width as a fraction of the sheet, side it sits on) for one image.

        The one place the two settings are read together, so the renderer, the
        page margin the footer strip reserves and the preview in Impostazioni
        cannot disagree about how big the logo is.
        """
        if getattr(self, f"{which}_fit") != FIT_SIZE:
            return 1.0, ALIGN_CENTER
        return (getattr(self, f"{which}_width") / 100.0,
                getattr(self, f"{which}_align"))

    def image_offset(self, which: str) -> float:
        """Millimetres between one image and its edge of the paper."""
        return getattr(self, "header_top" if which == "header"
                       else "footer_bottom")

    def signs(self, doc_kind: str) -> bool:
        """Whether a sheet of this kind opens with the signature ticked.

        It sets the tick, it does not force it: what prints is whatever the
        jury leaves ticked on the page when it presses Salva PDF.
        """
        if self.signature_scope == SIG_NEVER:
            return False
        if self.signature_scope == SIG_RESULTS:
            return doc_kind in DOC_RESULT_KINDS
        return True


@dataclass
class EntrySheet:
    """Where the entry workbook is and what its columns are called.

    The workbook is written by the federation in Italian; the code works in
    English. The mapping lives here so a differently-worded file is a config
    change, never a code change.
    """

    source: str = ""
    header_row: int = 6            # category sheets: header row (1-based)
    first_data_row: int = 7
    columns: dict[str, str] = field(default_factory=dict)   # header -> field
    ksport: dict[str, str] = field(default_factory=dict)    # header -> field
    # The licence check (verificato / NP) is not part of the federation's
    # layout: it is columns the giuria adds to the file by hand. Declared apart
    # from `columns` so they are read and written where they exist without
    # entering the fixed-column layout the elenco iscritti is exported in.
    check_in: dict[str, str] = field(default_factory=dict)  # header -> field
    #: Whether the mapping above is **this competition's own** - stated in its
    #: programme, typed into the mapping dialog - rather than the one the table
    #: of formats supplies to a competition that has said nothing
    #: (`entry_formats.applied`, which is the only thing that sets it).
    #:
    #: It is not written to the file and is not a setting: it is the difference
    #: between "nobody has looked at this file yet" and "the giuria has said
    #: which column is which", and the import needs it to know which of its
    #: findings are still worth reporting.
    mapped: bool = False
    # What a rider rides for at *this* competition, and what it is called: the
    # regione at an Italian championship, the società at an open meeting. The
    # programme states the rule; Impostazioni can override it on this machine.
    team_group: str = DEFAULT_TEAM_GROUP
    team_name: str = ""            # blank: the word from the dictionary
    # Two rappresentative authorised to field one squadra together (a federal
    # deroga: PIEMONTE and VALLE D'AOSTA at CITA26). `{regione: nome unico}`,
    # and it changes one thing only - how the squadre and the coppie of a team
    # events are composed and what they are called. A rider keeps their own
    # regione everywhere else: individual startlists and results, the quotas,
    # the riepilogo per squadra.
    team_merge: dict[str, str] = field(default_factory=dict)
    # Which events the deroga was granted for, by code. Empty: every team
    # event. The authorisation is per event, so it is written down as one.
    team_merge_events: list[str] = field(default_factory=list)

    def __post_init__(self):
        # headers are matched loosely: the workbook writes "Dors.", "Società"
        # and "Squadra\n(Regione)" with inconsistent spacing between exports
        # the check-in columns are read on both shapes of the file: they are
        # the same two headers wherever the giuria put them
        extra = {_norm_header(h): f for h, f in self.check_in.items()}
        self._lookup = {
            False: {**extra,
                    **{_norm_header(h): f for h, f in self.columns.items()}},
            True: {**extra,
                   **{_norm_header(h): f for h, f in self.ksport.items()}},
        }

    def field_of(self, header: str, *, ksport: bool = False) -> str:
        return self._lookup[ksport].get(_norm_header(header), "")

    def header_of(self, name: str, *, ksport: bool = False) -> str:
        """The workbook wording of a field, for the sheets we write ourselves."""
        table = {**self.check_in, **(self.ksport if ksport else self.columns)}
        for header, fname in table.items():
            if fname == name:
                return header
        return name

    @property
    def fields(self) -> list[str]:
        """Field names of the fixed columns, in workbook order."""
        return list(dict.fromkeys(self.columns.values()))


def _norm_header(text: Any) -> str:
    """Compare workbook headers ignoring case, dots, spaces and line breaks."""
    return "".join(str(text or "").upper().split()).replace(".", "")


# ── the checks a regulation states ──────────────────────────────────────────
#
# What Art. 4 of a regolamento says is always the same sentence: *so many of
# this, per that*. "Omnium massimo 2 corridori per regione", "Madison 1 Team
# per regione", "massimo 4 events per atleta". Three words decide it - what
# is counted (`unit`), what it is counted for (`per`), and how many there may
# be (`max`) - and the two before them say who the sentence is about (`cat`,
# `event`).
#
# It used to be five fields on `Quotas`, one per shape somebody had needed, and
# each of them keyed by event alone. That is what a regolamento does not
# fit: at the Trofeo delle Regioni 2026 the Km da fermo is one atleta per
# regione for the JU and two for the DJ, and a table with one key per
# event cannot hold both. So the categoria is part of the rule, `*` means
# *every one*, and a new regulation is rows in a table rather than a field in a
# dataclass.
#
# The old fields are still read (`Competition.entry_checks`): a programme
# written before this says the same thing in the older words.

#: `cat: "*"` / `event: "*"` - the rule is about all of them.
ANY = "*"

#: What a check counts.
UNIT_RIDERS = "riders"    # atleti entered in the event
UNIT_TEAMS = "teams"      # squadre (inseguimento / velocità a squadre)
UNIT_PAIRS = "pairs"      # coppie (madison)
UNIT_EVENTS = "events"    # event - the one thing counted per atleta
CHECK_UNITS = (UNIT_RIDERS, UNIT_TEAMS, UNIT_PAIRS, UNIT_EVENTS)

#: What it is counted for. A squadra is whatever this competition groups by
#: (`team_group`); `region` and `club` name the two fields outright, because a
#: rule about società inside a rappresentativa is about both at once.
PER_REGION = "region"                  # per rappresentativa
PER_CLUB = "club"                      # per società, over the whole categoria
PER_CLUB_IN_REGION = "club_in_region"  # per società *inside* one rappresentativa
PER_CAT = "cat"                        # per categoria, ungrouped
PER_RIDER = "rider"                    # per atleta - only `units: events`
CHECK_SCOPES = (PER_REGION, PER_CLUB, PER_CLUB_IN_REGION, PER_CAT, PER_RIDER)

#: How a broken rule is reported. Never blocking, whatever it says: `error`
#: colours it red and counts it in the summary, and it is still the giuria that
#: decides - a deroga must not need the file reopening.
CHECK_LEVELS = ("error", "warn", "off")


@dataclass
class Check:
    """One line of a regolamento: *max N `unit` per `per`*.

    `cat` and `event` say who it is about, `ANY` meaning every one of them.
    `note` is where it comes from - "Art. 4 reg. TR 2026" - and is printed
    after the finding, so a jury reading the warning knows which article to
    look up before granting a deroga.
    """

    cat: str = ANY
    event: str = ANY
    unit: str = UNIT_RIDERS
    per: str = PER_REGION
    max: int = 0
    level: str = "warn"
    #: Whether a riserva counts towards the limit. The STP wording counts
    #: starters only ("massimo N events, indipendentemente se individuali o
    #: a squadre"), so it is off unless a regulation says otherwise.
    count_reserves: bool = False
    note: str = ""

    def __post_init__(self):
        self.cat = str(self.cat or ANY).strip() or ANY
        self.event = str(self.event or ANY).strip() or ANY
        self.unit = (str(self.unit or "").strip().lower()
                     if str(self.unit or "").strip().lower() in CHECK_UNITS
                     else UNIT_RIDERS)
        self.per = (str(self.per or "").strip().lower()
                    if str(self.per or "").strip().lower() in CHECK_SCOPES
                    else PER_REGION)
        self.level = (str(self.level or "").strip().lower()
                      if str(self.level or "").strip().lower() in CHECK_LEVELS
                      else "warn")
        self.max = int(self.max or 0)
        # a count of events is a count *per atleta* and nothing else: the
        # scope is not a second choice, and a file that says otherwise is read
        # as meaning what the unit already decided
        if self.unit == UNIT_EVENTS:
            self.per = PER_RIDER
        elif self.per == PER_RIDER:
            self.per = PER_REGION

    @property
    def on(self) -> bool:
        """Whether the rule says anything: a max of 0 is not a limit of zero."""
        return self.level != "off" and self.max > 0

    @property
    def slot(self) -> tuple[str, str, str, str]:
        """What this rule occupies, so an older wording of it is not read twice.

        Squadre and coppie are one slot: they are the same sentence - *one team
        per regione* - and which of the two an event has is decided by its
        formato, not by the word the regulation happened to use.
        """
        unit = UNIT_TEAMS if self.unit in (UNIT_TEAMS, UNIT_PAIRS) else self.unit
        return (self.cat, self.event, unit, self.per)

    def applies(self, cat: str, event: str) -> bool:
        return ((self.cat in (ANY, cat)) and (self.event in (ANY, event)))


def _check(raw: Any) -> Check:
    """One rule as the file writes it, ignoring what it does not know.

    Tolerant on purpose: the table is edited by hand as often as by the page,
    and a stray key must not stop a competition from opening.
    """
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    known = {f.name for f in fields(Check)}
    return Check(**{k: v for k, v in data.items() if k in known})


@dataclass
class Quotas:
    """Entry limits from the STP comunicato. Used for warnings, never blocking.

    Superseded by `checks:` (`Check`), and still read: every field here is
    translated into the rules it always meant (`Competition.entry_checks`).
    """

    max_events_per_rider: dict[str, int] = field(default_factory=dict)  # cat -> n
    # How the event-count limit is reported: "error" (blocking-looking, red),
    # "warn", or "off" to disable it altogether. The count itself follows the
    # STP wording ("massimo N events, indipendentemente se individuali o a
    # squadre"): reserve entries are excluded unless `max_events_count_reserves`.
    max_events_level: str = "warn"  # error|warn|off
    max_events_count_reserves: bool = False
    max_per_region: dict[str, int] = field(default_factory=dict)  # event -> n
    max_same_club: dict[str, int] = field(default_factory=dict)  # event -> n
    # "Ogni Rappresentativa può avere massimo N atleti della stessa società di
    # appartenenza" (STP com. 016, Omnium): a club limit counted *inside* each
    # squadra, not over the whole categoria - which is a different rule from
    # `max_same_club` and has to be counted per (region, club).
    max_same_club_per_region: dict[str, int] = field(default_factory=dict)
    max_teams_per_region: dict[str, int] = field(default_factory=dict)
    exemptions: list[str] = field(default_factory=list)  # free text


@dataclass
class Competition:
    name: str = ""
    short: str = ""
    race_id: str = ""
    location: str = ""
    dates: list[str] = field(default_factory=list)
    #: When each giornata starts: `{1: "14:30"}`, the giornata numbered as the
    #: dates are. It is the one hour of the day anybody decides; every other
    #: orario on the programme is this plus the durate of what runs before
    #: (`schedule`). A giornata not in here has no clock at all, and its fasi
    #: print no orario rather than a made-up one.
    day_start: dict[int, str] = field(default_factory=dict)
    track_len: float = DEFAULT_TRACK_LEN
    categories: dict[str, Category] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)
    programme: list[ProgrammeItem] = field(default_factory=list)
    communiques: list[CommuniqueSpec] = field(default_factory=list)
    entry_sheet: EntrySheet = field(default_factory=EntrySheet)
    branding: Branding = field(default_factory=Branding)
    quotas: Quotas = field(default_factory=Quotas)
    #: What the regolamento of this competition limits: one row per sentence
    #: of its article on the iscrizioni (`Check`). Read together with the
    #: older `quotas:` fields, which say the same thing in fewer words.
    checks: list[Check] = field(default_factory=list)
    #: Which documents share a comunicato, over what the table says
    #: (`regulations/communiques.json`): `{rule: on}`, and a rule not named
    #: here is whatever that table decides for the format. It is the one thing
    #: about the register a competition really states - *this* meeting merges
    #: the omnium sheets, that one does not - and it is written in the
    #: programme, under `merge:`, because it changes what goes on paper.
    merge: dict[str, bool] = field(default_factory=dict)
    #: Where the number goes when the risultati and the classifica of a
    #: events go out on the same comunicato: on the classifica alone. It
    #: is the sheet the number belongs to - the one that closes the event
    #: and the one everybody looks the number up for - and printing it twice,
    #: once under each column of the programme, reads as two comunicati. Off,
    #: both sheets print it. Not every sheet has a number, and one that has
    #: none prints nothing at all (`models.number_text`).
    number_on_classification: bool = True
    # There was a `numbering_frozen` here, and a switch in the sidebar for it:
    # the register used to renumber itself on every rerun, so it needed a way
    # to be told to stop. It does not renumber itself any more - the numbers
    # move when somebody asks for them to (`communiques.autonumber`, behind
    # *Ricalcola i numeri*), and what must never move is said on the entry
    # itself: `pinned`, `ret`, or a number already issued. A file that still
    # carries the old key is read and the key is dropped on the next save.
    #: What kind of meeting this is. A title is only assigned at a
    #: championship: `SQUADRA CAMPIONE D'ITALIA` under the winning quartetto,
    #: `CAMPIONE / CAMPIONESSA D'ITALIA` under the rider who wins the event.
    #: At an ordinary meeting there is a winner and no champion, so the band is
    #: not printed at all (`ui.pages.races`). Set in Programma → Gara.
    kind: str = KIND_CHAMPIONSHIP
    path: str = ""

    @property
    def entries_source(self) -> str:
        return self.entry_sheet.source

    @property
    def assigns_titles(self) -> bool:
        """Whether the winner of an event is a champion, and printed as one."""
        return self.kind == KIND_CHAMPIONSHIP

    @property
    def scores_teams(self) -> bool:
        """Whether the meeting as a whole is scored into a team classifica.

        A Trofeo delle Regioni is: every prova gives points to the squadra of
        whoever rides it, and the meeting has a winner of its own on top of the
        winners of its events (`core.trofeo`). Nothing else does, so the
        Statistiche page shows the medagliere alone.
        """
        return self.kind == KIND_TROFEO_REGIONI

    @property
    def team_group(self) -> str:
        """The rider field a squadra is: `region`, `club`, `province`, `nation`."""
        group = self.entry_sheet.team_group
        return group if group in TEAM_GROUPS else DEFAULT_TEAM_GROUP

    @property
    def team_name(self) -> str:
        """What that squadra is *called* on a printed sheet ("Squadra")."""
        # the catalogue word, not `label("team")`: that one already answers
        # with whatever override is in force, which is what this *sets*
        return self.entry_sheet.team_name or word("team")

    def team_merge(self, event: str = "") -> dict[str, str]:
        """`{regione: nome della squadra unica}` for this event, if any.

        The regioni are matched the way they are read off the entry file
        (upper case, spaces squashed - see `entries.norm_region`), so the
        programme can spell them the way the comunicato does.
        """
        merge = self.entry_sheet.team_merge
        events = self.entry_sheet.team_merge_events
        if not merge or (event and events and event not in events):
            return {}
        return {" ".join(str(k).upper().split()): str(v).strip()
                for k, v in merge.items() if str(v).strip()}

    # -- lookups -------------------------------------------------------------

    def cat(self, code: str) -> Category:
        return self.categories.get(code, Category(code=code))

    def category_of(self, cat: str, sex: str = "") -> str:
        """Which categoria of *this* programme a rider licensed `cat` rides in.

        Itself, nearly always. An **open** is the exception: it is ridden by
        riders whose licences say EL, UN or master, and the entry list arrives
        with those sigle in it (`Category.accepts`). `sex` decides between two
        opens that take the same licences - the master categories are one
        family for both - and where it is not stated the first one declared
        wins, which is the order the programme is written in.

        A categoria the programme does not run comes back unchanged: the rider
        is on no sheet, and that is said out loud where the file is read
        (`entries.import_ksport_export`).
        """
        code = str(cat or "").strip().upper()
        if not code or code in self.categories:
            return code
        female = str(sex or "").strip().upper().startswith("F")
        takers = [c for c in sorted(self.categories.values(),
                                    key=lambda c: (c.order, c.code))
                  if c.takes(code)]
        if not takers:
            return code
        by_sex = [c for c in takers
                  if (c.sex or "").upper().startswith("F") == female]
        return (by_sex or takers)[0].code

    def female(self, code: str) -> bool:
        """Whether this categoria is ridden by women.

        The sheets are written about the riders in front of the jury, not about
        a generic masculine: the champion is a CAMPIONESSA, it is *la
        vincitrice* of a batteria who goes through, and *la prima atleta* who
        starts on the finishing straight.
        """
        return (self.cat(code).sex or "").upper().startswith("F")

    def event(self, code: str) -> Event:
        return self.events.get(code, Event(code=code))

    def cat_order(self) -> list[str]:
        return [c.code for c in sorted(self.categories.values(),
                                       key=lambda c: (c.order, c.code))]

    def event_order(self) -> list[str]:
        return [s.code for s in sorted(self.events.values(),
                                       key=lambda s: (s.order, s.code))]

    def event_headers(self, codes: list[str],
                      abbr: bool = False) -> dict[str, str]:
        """Column header per event code, guaranteed unique.

        A grid needs distinct column names: if two events abbreviate the same
        way, both keep their short name rather than silently merging.
        """
        heads = {c: (self.event(c).abbr or self.event(c).short) if abbr
                 else self.event(c).short for c in codes}
        if abbr:
            clash = {h for h in heads.values()
                     if list(heads.values()).count(h) > 1}
            heads = {c: (self.event(c).short if h in clash else h)
                     for c, h in heads.items()}
        return heads

    def events_for(self, cat: str) -> list[str]:
        """Events contested by a category, in programme order."""
        seen = [r.event for r in self.programme if r.cat == cat]
        out: list[str] = []
        for s in seen:
            if s not in out:
                out.append(s)
        return out

    # ── what the regolamento limits ─────────────────────────────────────────

    def entry_checks(self) -> list[Check]:
        """Every rule that holds over this elenco: the new table, then the old.

        A programme states its limits in `checks:`. One written before that
        block existed states them in `quotas:`, in five fields keyed by
        events, and those are read as the rules they always were - but only
        where the table has not already said something about the same slot
        (`Check.slot`). A file that has been edited on the Controlli tab has
        both blocks in it, the second left over from the year before, and the
        old wording must not report the same regione twice.
        """
        out = list(self.checks)
        taken = {c.slot for c in out}
        return out + [c for c in self.legacy_checks() if c.slot not in taken]

    def legacy_checks(self) -> list[Check]:
        """The `quotas:` block said in the words of `checks:`."""
        q = self.quotas
        out = [Check(cat=cat, unit=UNIT_EVENTS, max=n,
                     level=q.max_events_level,
                     count_reserves=q.max_events_count_reserves)
               for cat, n in q.max_events_per_rider.items()]
        for table, unit, per in (
                (q.max_per_region, UNIT_RIDERS, PER_REGION),
                (q.max_same_club, UNIT_RIDERS, PER_CLUB),
                (q.max_same_club_per_region, UNIT_RIDERS, PER_CLUB_IN_REGION),
                (q.max_teams_per_region, UNIT_TEAMS, PER_REGION)):
            out += [Check(event=event, unit=unit, per=per, max=n)
                    for event, n in table.items()]
        return out

    def max_events(self, cat: str) -> Check | None:
        """The rule on how many events one atleta of `cat` may ride.

        The one check a page other than Verifica asks about by itself: the
        check-in grid prints the limit beside the count, and needs the number
        and whether riserve are in it.
        """
        for c in self.entry_checks():
            if c.unit == UNIT_EVENTS and c.on and c.cat in (ANY, cat):
                return c
        return None

    def cats_for(self, event: str) -> list[str]:
        out: list[str] = []
        for r in self.programme:
            if r.event == event and r.cat not in out:
                out.append(r.cat)
        return sorted(out, key=lambda c: self.cat_order().index(c)
                      if c in self.cat_order() else 99)

    def scheduled_any(self, event: str) -> bool:
        """Whether any categoria contests this event.

        What stops an event being un-declared from under the races that
        name it: the programme would go on scheduling an event the file no
        longer has, and every sheet of it would print under the bare code.
        """
        return any(r.event == event for r in self.programme)

    def scheduled(self, cat: str, event: str) -> ProgrammeItem | None:
        for r in self.programme:
            if r.cat == cat and r.event == event:
                return r
        return None

    def team_size(self, cat: str, event: str) -> int:
        """How many atleti a squadra fields in this race.

        What the programme says about *this* categoria first, then what the
        regulation says about the event (`Event.team_size`). One place,
        because everything downstream has to agree: the squadre are built to
        this number at the check-in (`entries.build_teams_and_pairs`) and the
        jury is warned at the track when a side does not field it.
        """
        item = self.scheduled(cat, event)
        stated = getattr(item, "team_size", None) if item else None
        return int(stated or self.event(event).team_size or 0)

    def round_of(self, cat: str, event: str, key: str) -> Round:
        item = self.scheduled(cat, event)
        for r in (item.rounds if item else []):
            if key in (r.key, r.label):
                return r
        return Round(key=key)

    def rounds(self, cat: str, event: str) -> list[Round]:
        item = self.scheduled(cat, event)
        return list(item.rounds) if item else []

    def day_of(self, item: ProgrammeItem, rnd: Round) -> int:
        """The giornata a fase is ridden on - its own, or the race's.

        The one place the rule is written. A fase says nothing about the day
        unless it is somewhere else than the rest of its race (`Round.day`).
        """
        return rnd.day or item.day

    def days(self) -> list[int]:
        """Every giornata something is ridden on, fasi that moved included."""
        return sorted({self.day_of(i, r) for i in self.programme
                       for r in i.rounds if self.day_of(i, r)}
                      | {i.day for i in self.programme if i.day})

    def rounds_on(self, day: int) -> list[tuple[ProgrammeItem, Round]]:
        """The fasi ridden on one giornata, in the order they are ridden.

        The order is the running order, and the jury states it by numbering the
        scaletta (`Round.seq`): 1, 2, 3 … A fase with no number of its own
        keeps the place the programme puts it in, so a file nobody has
        reordered comes out exactly as it always did - and two event can
        be interleaved, which is what a giornata actually looks like.

        The composizione is not one of them (`ROUND_SETUP`): the coppie of a
        madison are made up before anybody rides, by the jury and not on the
        track, and a round nobody rides has no place in a running order.

        A pause is (`ROUND_PAUSE`): nobody rides it either, but it takes time
        off the clock, and a running order that leaves it out is a running
        order whose every orario below it is wrong.

        It is what the register is numbered from (`communiques.sheet_order`)
        and what the giornata is edited as.
        """
        pairs = [(item, r) for item in self.programme for r in item.rounds
                 if r.kind != ROUND_SETUP and self.day_of(item, r) == day]
        # by position and not by identity: two fasi of two races can be equal
        # dataclasses, and `list.index` would find the first of them
        order = sorted(range(len(pairs)),
                       key=lambda i: (pairs[i][1].seq or i + 1, i))
        return [pairs[i] for i in order]

    # -- derived orari --------------------------------------------------------

    def duration_of(self, item: ProgrammeItem, rnd: Round) -> int:
        """How long this fase takes, in minutes - stated or usual.

        The fase wins over the event, which wins over nothing: a `0` here
        is a fase that costs the clock nothing, and that is a statement neither
        of them has made rather than a race of no length.
        """
        if rnd.duration is not None:
            return max(0, int(rnd.duration))
        return max(0, int(self.event(item.event).minutes or 0))

    def schedule(self, day: int) -> list[tuple[ProgrammeItem, Round, str]]:
        """The giornata with an orario against every fase.

        **One clock, one origin.** It starts at `day_start[day]` and moves on
        by the durata of each fase in the running order - so a fase moved up
        the scaletta or a durata corrected re-times everything below it, which
        is the only behaviour a timetable can have. There is no fase that
        overrides the hour: an anchor typed on a fase was a second origin, and
        a second origin is what makes durations look broken.

        A giornata with no start time has no orari at all: an hour invented
        from midnight would be worse than a blank column.
        """
        out = []
        clock = _minutes(self.day_start.get(day, ""))
        for item, rnd in self.rounds_on(day):
            out.append((item, rnd, _hhmm(clock)))
            if clock is not None:
                clock += self.duration_of(item, rnd)
        return out

    def day_end(self, day: int) -> str:
        """When the giornata is over: the last fase plus how long it takes.

        "" when the giornata has no clock, like every other orario - the answer
        to *a che ora si finisce* is either computed or absent, never guessed.
        """
        plan = self.schedule(day)
        if not plan:
            return ""
        item, rnd, at = plan[-1]
        minutes = _minutes(at)
        if minutes is None:
            return ""
        return _hhmm(minutes + self.duration_of(item, rnd))

    def time_of(self, day: int, item: ProgrammeItem, rnd: Round) -> str:
        """The orario of one fase, or "" when the giornata has no clock."""
        for i, r, at in self.schedule(day):
            if i is item and r is rnd:
                return at
        return ""

    # -- derived distances / laps / sprints -----------------------------------

    def distances(self, cat: str, event: str,
                  round_key: str = "") -> tuple[float, float, int]:
        """(distance km, laps, sprints) of one round, filling in defaults."""
        r = self.round_of(cat, event, round_key)
        fmt = self.event(event).fmt
        # an omnium is four prove under one event, and which one this round is
        # is in its name: the tempo race counts its sprints by its own rule,
        # whether it is ridden inside an omnium or as an event of its own
        tempo = fmt == "tempo" or (fmt == "omnium" and (round_key or "")
                                   .strip().lower().startswith(TEMPO_RACE))
        distance = float(r.distance or 0.0)
        laps = r.laps if r.laps is not None else laps_from_distance(
            distance, self.track_len, fmt)
        # A tempo race sprints on every lap from the fifth: the count is the
        # laps less the four neutralised ones and nothing else. It is derived
        # and not read from the programme even when the programme writes it -
        # the two would otherwise disagree on the sheet, and the sprint columns
        # of the risultati are the ones the jury fills in lap by lap.
        sprints = (sprints_from_laps(laps, "tempo") if tempo
                   else r.sprints if r.sprints is not None
                   else sprints_from_laps(laps, fmt))
        return distance, float(laps), int(sprints)


# ── Default lap / sprint derivation (port of EVENTS_DICT["DLS"]) ────────────

def laps_from_distance(distance: float, track_len: float, fmt: str = "group") -> float:
    """Laps for a distance in km. Timed competitions keep half-lap resolution.

    Snaps to the nearest half lap when the distance is an exact multiple of it:
    a nominal track length such as 0.33333 makes 3 km come out at 9.00009 laps,
    which a bare ceil() would round up to 9.5(the bug in the old track.py).
    """
    if not distance or not track_len:
        return 0.0
    if fmt not in ("timed", "timed_team", "time_trial"):
        return round(distance / track_len)
    halves = distance / track_len * 2
    nearest = round(halves)
    if nearest and abs(halves - nearest) < 0.01 * nearest:
        return nearest / 2
    return ceil(halves) / 2


def sprints_from_laps(laps: float, fmt: str = "group") -> int:
    """Sprint count implied by the lap count, per format."""
    if fmt == "points":
        return int(laps // 6)
    if fmt == "tempo":
        return int(max(laps - 4, 0))
    if fmt in ("scratch", "group"):
        return 1
    return 0


# ── YAML load / save ────────────────────────────────────────────────────────

def _mk_map(cls, raw: Any, key_name: str = "code") -> dict:
    """Build {code: obj} from either a mapping or a list of dicts."""
    out: dict[str, Any] = {}
    if not raw:
        return out
    items = (raw.items() if isinstance(raw, dict)
             else [(d.get(key_name), d) for d in raw])
    for i, (code, d) in enumerate(items):
        d = dict(d or {})
        d.pop(key_name, None)
        d.setdefault("order", i)
        out[code] = cls(**{key_name: code}, **d)
    return out


def _events_of(raw: Any) -> dict[str, Event]:
    """The event of a programme, over what the catalogue already knows.

    What an event *is* technically - its sigla UCI, its formato, how many
    ride a squadra, how many start together, what its column is called in the
    entry file - is the same at every championship, so it lives in one place
    (`catalogue.FIELDS`, edited in Impostazioni) and not copied into every
    file. A programme that states one of them anyway still wins: a meeting that
    runs an event its own way has to be able to say so.

    The **name is not one of them**. It is printed on every sheet and it is the
    meeting's: a programme written in Italian goes on printing Italian names
    whoever opens it, which is the whole reason it is written down.
    """
    from . import catalogue as CAT
    out: dict[str, Event] = {}
    items = (raw.items() if isinstance(raw, dict)
             else [(d.get("code"), d) for d in (raw or [])])
    for i, (code, d) in enumerate(items):
        d = dict(d or {})
        d.pop("code", None)
        d.setdefault("order", i)
        out[code] = Event(code=code, **{**CAT.event_fields(code), **d})
    return out


def load_competition(path: str | Path) -> Competition:
    """Read a programme.yaml into a Competition (raises on malformed YAML)."""
    path = Path(path)
    # a programme written VELOCITA' prints VELOCITÀ: the accent is restored on
    # the way in, once, rather than in every place that shows a name
    raw = yaml.safe_load(fix_accents(path.read_text(encoding="utf-8"))) or {}

    programme = []
    # the orari a file written before the durate carries, set aside while it is
    # read and turned into durate once the running order is known (`_retime`)
    legacy: dict[tuple[str, str, str], str] = {}
    for item in raw.get("programme", []) or []:
        item = dict(item)
        at = str(item.pop("time", "") or "")
        rounds = []
        for r in (item.pop("rounds", []) or []):
            if not isinstance(r, dict):
                rounds.append(Round(key=str(r)))
                continue
            r = dict(r)
            was = str(r.pop("start", "") or "") or at
            rounds.append(Round(**r))
            if was:
                legacy[(item.get("cat", ""), item.get("event", ""),
                        rounds[-1].key)] = was
            at = ""            # a race-wide time belongs to its first fase
        programme.append(ProgrammeItem(rounds=rounds, **item))

    entries = dict(raw.get("entries") or {})
    entries.setdefault("source", raw.get("entries_source", ""))

    comp = Competition(
        name=raw.get("name", ""),
        short=raw.get("short", ""),
        race_id=str(raw.get("id", raw.get("race_id", ""))),
        location=raw.get("location", ""),
        dates=[str(d) for d in raw.get("dates", []) or []],
        day_start={int(k): str(v).strip()
                   for k, v in (raw.get("day_start") or {}).items()
                   if str(v).strip()},
        track_len=float(raw.get("track_len", DEFAULT_TRACK_LEN)),
        categories=_mk_map(Category, raw.get("categories")),
        events=_events_of(raw.get("events")),
        programme=programme,
        communiques=[_communique(c) for c in raw.get("communiques", []) or []],
        entry_sheet=EntrySheet(**entries),
        branding=Branding(**(raw.get("branding") or {})),
        quotas=Quotas(**(raw.get("quotas") or {})),
        checks=[_check(c) for c in raw.get("checks", []) or []],
        merge={str(k): bool(v)
               for k, v in (raw.get("merge") or {}).items()},
        number_on_classification=bool(
            raw.get("number_on_classification", True)),
        # a file written before the choice existed is a championship: that is
        # what every programme this app has run so far was
        kind=(str(raw.get("kind", "")).strip().lower()
              if str(raw.get("kind", "")).strip().lower() in COMPETITION_KINDS
              else KIND_CHAMPIONSHIP),
        path=str(path),
    )
    _retime(comp, legacy)
    return comp


def _retime(comp: Competition, legacy: dict[tuple[str, str, str], str]) -> None:
    """Turn the orari of an older file into the durate that replace them.

    Every fase used to carry the hour it was ridden at. That is not a timetable
    - it is a timetable's *output* written down - and a programme full of them
    could not be re-timed at all: correcting one duration moved nothing,
    because the hour below it was already stated.

    So they are read once and converted: the first orario of a giornata becomes
    when the giornata starts, and the gap to the next one becomes how long the
    fase takes. The last fase of the day has no gap after it and takes the
    middle of the ones before. What comes out prints the same hours as what
    went in, and this time moving a fase moves them.

    It runs only on a file that has said nothing modern: one duration or one
    `day_start` anywhere and the file is already past this, so nothing is
    touched.
    """
    if not legacy:
        return
    if comp.day_start or any(r.duration is not None for i in comp.programme
                             for r in i.rounds):
        return

    for day in comp.days():
        plan = [(item, rnd, _minutes(legacy.get((item.cat, item.event,
                                                 rnd.key), "")))
                for item, rnd in comp.rounds_on(day)]
        known = [(i, at) for i, (_it, _r, at) in enumerate(plan)
                 if at is not None]
        if not known:
            continue
        comp.day_start[day] = _hhmm(known[0][1])
        gaps = []
        for (i, at), (j, then) in zip(known, known[1:]):
            gap = then - at
            # a gap that is not a duration - the clock going backwards, or a
            # fase four hours after the one before it - says the two are not
            # consecutive, and guessing from it would be worse than nothing
            if 0 < gap <= MAX_ROUND_MINUTES and j == i + 1:
                plan[i][1].duration = gap
                gaps.append(gap)
        if gaps:
            # the last one, which has nothing after it to be measured against
            last = plan[known[-1][0]][1]
            if last.duration is None:
                last.duration = sorted(gaps)[len(gaps) // 2]


#: The longest gap between two fasi that can still be read as one lasting that
#: long. Past it the two are not consecutive - a lunch break, a giornata split
#: in two - and the earlier fase is left saying nothing.
MAX_ROUND_MINUTES = 180


def _communique(raw: dict) -> CommuniqueSpec:
    d = dict(raw)
    if "round" in d:
        d["round_key"] = d.pop("round")
    d["extra"] = [_sheet(s) for s in (d.pop("with", None) or [])]
    return CommuniqueSpec(**d)


def _sheet(raw: dict | str) -> Sheet:
    """One entry of a comunicato's `with:` list.

    A bare string is the common case written short: the same race, another of
    its sheets (`with: [partenti_recuperi]`).
    """
    if isinstance(raw, str):
        return Sheet(doc=raw)
    d = dict(raw)
    if "round" in d:
        d["round_key"] = d.pop("round")
    return Sheet(**d)


def validate(comp: Competition) -> list[str]:
    """Non-fatal consistency problems, shown in the UI.

    What a programme does *not* say is not one of them. The columns of the
    entry file used to be checked here and were reported missing on every
    competition being set up - since `entry_formats` supplies them to anybody
    who states none, saying nothing is the normal case and not a finding.
    """
    msgs = []
    if not comp.categories:
        msgs.append(msg("cfg_no_categories"))
    if not comp.events:
        msgs.append(msg("cfg_no_events"))
    if comp.track_len <= 0:
        msgs.append(msg("cfg_bad_track_len"))
    for r in comp.programme:
        if is_pause(r):
            continue        # not a race: no categoria, no event (see below)
        if r.cat not in comp.categories:
            msgs.append(msg("cfg_unknown_cat", cat=r.cat))
        if r.event not in comp.events:
            msgs.append(msg("cfg_unknown_event", event=r.event))
        if not r.rounds:
            msgs.append(msg("cfg_no_rounds", cat=r.cat, event=r.event))
    seen: dict[int, str] = {}
    for c in comp.communiques:
        if c.n in seen:
            msgs.append(msg("cfg_duplicate_communique", n=c.n, a=seen[c.n],
                            b=c.title))
        seen[c.n] = c.title
    return msgs


def _minutes(hhmm: str) -> int | None:
    """"14:30" -> 870. Anything that is not an hour of a day is no hour at all."""
    parts = str(hhmm or "").replace(".", ":").split(":")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        return None
    h, m = int(parts[0]), int(parts[1])
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def _hhmm(minutes: int | None) -> str:
    """870 -> "14:30". Past midnight it keeps counting, it does not wrap."""
    if minutes is None:
        return ""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
