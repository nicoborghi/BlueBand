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

from dataclasses import dataclass, field
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

# Madison, 3.2.157: teams the track takes in the final, by track length. The
# heats are run to qualify *up to* this number, not necessarily to fill it.
MADISON_TRACK_TEAMS = {166: 12, 200: 15, 250: 18, 285.714: 18, 333.33: 20,
                       400: 20}

# 3.2.157 again: whatever the arithmetic says, a heat never eliminates fewer
# than two teams.
MIN_ELIMINATED = 2


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

    def __post_init__(self):
        self.name = self.name or self.code


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
    "time_trial": "TT", "entrylist": "",
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
    # sprint | keirin | omnium | madison | time_trial
    entry_columns: list[str] = field(default_factory=list)  # workbook column headers
    team_size: int = 0  # team competitions: riders per team
    # How many start together in a timed round - teams or riders. An
    # inseguimento starts two, one on each straight; a velocità a squadre and
    # the 200 m lanciati of a velocità start one at a time, so their
    # qualifying has no batterie at all - it has a start order, everyone in
    # it, and the sheet counts starts, not heats. Rounds ridden man against
    # man - the finals, a bracket - are batterie whatever this says.
    teams_per_start: int = 2
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
    # When it is ridden ("14:30"), as the programme sheet prints it. *Not* a
    # measured time: what a rider does over the distance is a `time` on a
    # result, and the two must not be confusable - hence `start`.
    start: str = ""
    #: The jury's own note about this fase. It is *not* printed: it stays in
    #: the programme, where a comment would not survive a save.
    note: str = ""
    #: The line this fase opens its ordine di partenza on, above what the
    #: specialità always says (`Event.note`). This one *is* printed.
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
            self.docs = ([] if self.kind == ROUND_SETUP
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
    time: str = ""
    rounds: list[Round] = field(default_factory=list)
    #: velocità: how many the 200 m qualifies ("12" | "8"), see formats.sprint
    scheme: str = ""
    #: velocità: is the final for 5th-8th place ridden
    final_5_8: bool | None = None
    #: keirin: is the second final (the one under the title) ridden
    final_b: bool | None = None
    #: How many start together in a timed round *for this categoria*. The
    #: specialità states the usual shape (`Event.teams_per_start`), and it is
    #: not always the same one: a chilometro is ridden two at a time by a
    #: categoria with thirty entered and one at a time by the eight of another,
    #: on the same afternoon. `None` = whatever the specialità says.
    teams_per_start: int | None = None
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
    # specialità and to no fase at all.
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


@dataclass
class Branding:
    """How the sheets look: the images, the signature, the way names are set.

    Everything here is a local choice rather than a fact of the competition, so
    it is normally set in Impostazioni and stored in `settings.json` (see
    `ui.state.BRANDING_SETTINGS`); the programme can still carry a default.
    """

    header_img: str = ""
    footer_img: str = ""
    color: str = "#0a5688"
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

    def __post_init__(self):
        # the width comes from settings.json, which anything may have written:
        # a bad value narrows every printed name at once, so it is clamped here
        # rather than trusted down in the renderer
        try:
            width = float(self.name_width)
        except (TypeError, ValueError):
            width = DEFAULT_NAME_WIDTH
        self.name_width = min(NAME_WIDTH_MAX, max(NAME_WIDTH_MIN, width))
        # a partial dict is the normal case - the jury recolours the squalifica
        # and leaves the rest alone - so what is missing falls back rather than
        # printing a block with no tint at all
        self.note_colors = {**NOTE_COLORS,
                            **{k: v for k, v in (self.note_colors or {}).items()
                               if k in NOTE_COLORS and str(v).strip()}}

    @property
    def signature_caption(self) -> str:
        """The line the signature block is headed with ("Per la giuria:")."""
        return self.signature_label or word("signature")

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
    # What a rider rides for at *this* competition, and what it is called: the
    # regione at an Italian championship, the società at an open meeting. The
    # programme states the rule; Impostazioni can override it on this machine.
    team_group: str = DEFAULT_TEAM_GROUP
    team_name: str = ""            # blank: the word from the dictionary
    # Two rappresentative authorised to field one squadra together (a federal
    # deroga: PIEMONTE and VALLE D'AOSTA at CITA26). `{regione: nome unico}`,
    # and it changes one thing only - how the squadre and the coppie of a team
    # event are composed and what they are called. A rider keeps their own
    # regione everywhere else: individual startlists and results, the quotas,
    # the riepilogo per squadra.
    team_merge: dict[str, str] = field(default_factory=dict)
    # Which events the deroga was granted for, by code. Empty: every team
    # event. The authorisation is per specialità, so it is written down as one.
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


@dataclass
class Quotas:
    """Entry limits from the STP comunicato. Used for warnings, never blocking."""

    max_events_per_rider: dict[str, int] = field(default_factory=dict)  # cat -> n
    # How the event-count limit is reported: "error" (blocking-looking, red),
    # "warn", or "off" to disable it altogether. The count itself follows the
    # STP wording ("massimo N specialità, indipendentemente se individuali o a
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
    track_len: float = DEFAULT_TRACK_LEN
    categories: dict[str, Category] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)
    programme: list[ProgrammeItem] = field(default_factory=list)
    communiques: list[CommuniqueSpec] = field(default_factory=list)
    entry_sheet: EntrySheet = field(default_factory=EntrySheet)
    branding: Branding = field(default_factory=Branding)
    quotas: Quotas = field(default_factory=Quotas)
    #: Whether the comunicato numbers stand as they are. Unfrozen, they are
    #: recomputed from the running order every time it changes
    #: (`communiques.autonumber`) - which is what keeps the register in step
    #: while the programme is being built, and exactly what must stop once a
    #: sheet has gone out with a number on it.
    numbering_frozen: bool = False
    path: str = ""

    @property
    def entries_source(self) -> str:
        return self.entry_sheet.source

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

    def cats_for(self, event: str) -> list[str]:
        out: list[str] = []
        for r in self.programme:
            if r.event == event and r.cat not in out:
                out.append(r.cat)
        return sorted(out, key=lambda c: self.cat_order().index(c)
                      if c in self.cat_order() else 99)

    def scheduled_any(self, event: str) -> bool:
        """Whether any categoria contests this specialità.

        What stops a specialità being un-declared from under the races that
        name it: the programme would go on scheduling an event the file no
        longer has, and every sheet of it would print under the bare code.
        """
        return any(r.event == event for r in self.programme)

    def scheduled(self, cat: str, event: str) -> ProgrammeItem | None:
        for r in self.programme:
            if r.cat == cat and r.event == event:
                return r
        return None

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
        reordered comes out exactly as it always did - and two specialità can
        be interleaved, which is what a giornata actually looks like.

        The composizione is not one of them (`ROUND_SETUP`): the coppie of a
        madison are made up before anybody rides, by the jury and not on the
        track, and a round nobody rides has no place in a running order.

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
    """The specialità of a programme, over what the catalogue already knows.

    What a specialità *is* technically - its sigla UCI, its formato, how many
    ride a squadra, how many start together, what its column is called in the
    entry file - is the same at every championship, so it lives in one place
    (`catalogue.FIELDS`, edited in Impostazioni) and not copied into every
    file. A programme that states one of them anyway still wins: a meeting that
    runs a specialità its own way has to be able to say so.

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
    for item in raw.get("programme", []) or []:
        item = dict(item)
        rounds = [Round(**r) if isinstance(r, dict) else Round(key=str(r))
                  for r in (item.pop("rounds", []) or [])]
        programme.append(ProgrammeItem(rounds=rounds, **item))

    entries = dict(raw.get("entries") or {})
    entries.setdefault("source", raw.get("entries_source", ""))

    return Competition(
        name=raw.get("name", ""),
        short=raw.get("short", ""),
        race_id=str(raw.get("id", raw.get("race_id", ""))),
        location=raw.get("location", ""),
        dates=[str(d) for d in raw.get("dates", []) or []],
        track_len=float(raw.get("track_len", DEFAULT_TRACK_LEN)),
        categories=_mk_map(Category, raw.get("categories")),
        events=_events_of(raw.get("events")),
        programme=programme,
        communiques=[_communique(c) for c in raw.get("communiques", []) or []],
        entry_sheet=EntrySheet(**entries),
        branding=Branding(**(raw.get("branding") or {})),
        quotas=Quotas(**(raw.get("quotas") or {})),
        numbering_frozen=bool(raw.get("numbering_frozen", False)),
        path=str(path),
    )


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
    """Non-fatal consistency problems, shown in the UI."""
    msgs = []
    if not comp.categories:
        msgs.append(msg("cfg_no_categories"))
    if not comp.events:
        msgs.append(msg("cfg_no_events"))
    if not comp.entry_sheet.columns:
        msgs.append(msg("cfg_no_columns"))
    if comp.track_len <= 0:
        msgs.append(msg("cfg_bad_track_len"))
    for r in comp.programme:
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
