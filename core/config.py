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

from .i18n import IT, fix_accents, label, msg

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
    note: str = ""

    def __post_init__(self):
        self.label = self.label or self.key
        if self.docs is None:
            self.docs = ([] if self.kind == ROUND_SETUP
                         else [DOC_STARTLIST, DOC_RESULTS])


@dataclass
class ProgrammeItem:
    """One (category, event) contest with its rounds, as scheduled."""

    cat: str
    event: str
    day: int = 0
    time: str = ""
    rounds: list[Round] = field(default_factory=list)
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
    signature_label: str = label("signature")
    signature_mode: str = SIG_IMAGE
    signature_name: str = ""      # printed in bold when the mode is `text`
    signature_scope: str = SIG_ALWAYS
    name_style: str = NAME_SPLIT

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
    # What a rider rides for at *this* competition, and what it is called: the
    # regione at an Italian championship, the società at an open meeting. The
    # programme states the rule; Impostazioni can override it on this machine.
    team_group: str = DEFAULT_TEAM_GROUP
    team_name: str = ""            # blank: the word from the dictionary

    def __post_init__(self):
        # headers are matched loosely: the workbook writes "Dors.", "Società"
        # and "Squadra\n(Regione)" with inconsistent spacing between exports
        self._lookup = {
            False: {_norm_header(h): f for h, f in self.columns.items()},
            True: {_norm_header(h): f for h, f in self.ksport.items()},
        }

    def field_of(self, header: str, *, ksport: bool = False) -> str:
        return self._lookup[ksport].get(_norm_header(header), "")

    def header_of(self, name: str, *, ksport: bool = False) -> str:
        """The workbook wording of a field, for the sheets we write ourselves."""
        table = self.ksport if ksport else self.columns
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
        # the dictionary word, not `label("team")`: that one already answers
        # with whatever override is in force, which is what this *sets*
        return self.entry_sheet.team_name or IT["team"]

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

    def days(self) -> list[int]:
        return sorted({r.day for r in self.programme if r.day})

    # -- derived distances / laps / sprints -----------------------------------

    def distances(self, cat: str, event: str,
                  round_key: str = "") -> tuple[float, float, int]:
        """(distance km, laps, sprints) of one round, filling in defaults."""
        r = self.round_of(cat, event, round_key)
        fmt = self.event(event).fmt
        distance = float(r.distance or 0.0)
        laps = r.laps if r.laps is not None else laps_from_distance(
            distance, self.track_len, fmt)
        sprints = r.sprints if r.sprints is not None else sprints_from_laps(
            laps, fmt)
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
        events=_mk_map(Event, raw.get("events")),
        programme=programme,
        communiques=[_communique(c) for c in raw.get("communiques", []) or []],
        entry_sheet=EntrySheet(**entries),
        branding=Branding(**(raw.get("branding") or {})),
        quotas=Quotas(**(raw.get("quotas") or {})),
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
