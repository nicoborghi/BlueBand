"""Domain model for track race management.

Everything here is plain data: no streamlit, no pandas, no I/O. Objects are
JSON round-trippable through `to_dict`/`from_dict` so `core.store` can persist
them verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict, fields
from enum import Enum
from typing import Any


# ── Statuses ────────────────────────────────────────────────────────────────

class Status(str, Enum):
    """Result status of an entrant in a race."""

    OK = "OK"
    REL = "REL"  # declassato / relegato
    DNF = "DNF"
    ABD = "ABD"  # ritirato di sua volontà: scende dalla pista, non è caduto
    DNS = "DNS"
    DSQ = "DSQ"
    NP = "NP"  # non partente (declared before the race, entry-list level)

    @property
    def classified(self) -> bool:
        return self is Status.OK


# Single ordering convention for every format: classified riders first (by
# their own result), then the non-classified in this order. Replaces the three
# mutually inconsistent sentinel schemes of the old track.py.
#
# ABD comes after DNF: both left the race, and the one who came down of her own
# accord left it behind the one who could not finish it. A DSQ is last of all -
# a decision of the jury, not a way of ending a race.
STATUS_ORDER: dict[Status, int] = {
    Status.OK: 0,
    Status.REL: 1,
    Status.DNF: 2,
    Status.ABD: 3,
    Status.DNS: 4,
    Status.NP: 5,
    Status.DSQ: 6,
}

#: The two ways a rider leaves a race she started. They are ranked among
#: themselves by *when* they left it, which is the order the jury types them in
#: (see `formats.base.leaving_order`).
LEFT_RACE = (Status.DNF, Status.ABD)


def status_of(value: Any) -> Status:
    """Coerce a stored string / None into a Status (defaults to OK)."""
    if value is None or value == "":
        return Status.OK
    if isinstance(value, Status):
        return value
    return Status(str(value).strip().upper())


# ── Entry-list entities ─────────────────────────────────────────────────────

# Entry flag as written in the ISCRITTI workbook: X = starter, R = reserve.
FLAG_STARTER = "X"
FLAG_RESERVE = "R"


def pairing_letter(n: int) -> str:
    """1 -> 'A', 2 -> 'B'. Out of the alphabet the number speaks for itself."""
    return chr(ord("A") + n - 1) if 1 <= n <= 26 else str(n)


def pairing_number(s: str) -> int | None:
    """'A' -> 1, 'b' -> 2, '2' -> 2. None when it is not a pairing at all."""
    s = str(s).strip().upper()
    if len(s) == 1 and s.isalpha() and s not in (FLAG_STARTER, FLAG_RESERVE):
        return ord(s) - ord("A") + 1
    return int(s) if s.isdigit() and 1 <= int(s) <= 26 else None


@dataclass
class EventEntry:
    """A rider's entry in one event."""

    starter: bool = True         # False => reserve (`R` in the workbook)
    # which pairing within the region: madison coppia, or squadra A/B of a
    # team event. Held as a number, written and shown as a letter (1 = A).
    pair: int | None = None
    note: str = ""

    @property
    def reserve(self) -> bool:
        return not self.starter

    @property
    def flag(self) -> str:
        if self.pair is not None:
            # `AR` is the riserva of squadra A: the letter says which team,
            # the R that this one does not start
            return pairing_letter(self.pair) + ("" if self.starter
                                                else FLAG_RESERVE)
        return FLAG_STARTER if self.starter else FLAG_RESERVE


@dataclass
class Rider:
    """One licensed rider on the entry list."""

    key: str                     # stable id: UCI ID, else f"{cat}-{bib}"
    bib: int | None = None
    last_name: str = ""
    first_name: str = ""
    cat: str = ""
    uci_id: str = ""
    fci_code: str = ""
    nation: str = "ITA"
    birth_date: str = ""
    club: str = ""
    club_code: str = ""
    region: str = ""
    province: str = ""
    sex: str = ""
    note: str = ""
    reserve_entry: bool = False  # `Riserva` column of the ksport export
    certificate_date: str = ""   # date the medical certificate was issued
    # The licence check happens before the racing starts, so the jury ticks who
    # turned up (`checked_in`) and what stays unticked is the work left to do.
    # `not_starting` is the separate, explicit statement that a rider will not
    # start at all - that one removes them from startlists and results.
    checked_in: bool = False     # licence checked, rider present
    not_starting: bool = False   # "NP": not starting, whole competition
    events: dict[str, EventEntry] = field(default_factory=dict)
    source: str = ""             # which file this rider came from
    ksport_source: str = ""      # "KSPORT!12": the federal row, when there is one

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()

    def is_entered(self, event: str, include_reserves: bool = False) -> bool:
        e = self.events.get(event)
        return e is not None and (e.starter or include_reserves)

    def n_events(self, include_reserves: bool = False) -> int:
        """How many events this rider is entered in (STP limit check)."""
        return sum(1 for e in self.events.values()
                   if e.starter or include_reserves)


@dataclass
class Team:
    """A regional team in a team competition (pursuit / team sprint)."""

    key: str                     # f"{cat}:{event}:{region}:{letter}"
    cat: str
    event: str
    region: str
    letter: str = ""  # "" | "A" | "B" when a region fields two teams
    riders: list[str] = field(default_factory=list)  # rider keys, in order
    reserves: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.region} {self.letter}".strip()


@dataclass
class Pair:
    """A madison pair (coppia)."""

    key: str                     # f"{cat}:{region}:{number}"
    cat: str
    region: str
    number: int = 1  # pair number within the region (1, 2)
    # A region that fields two coppie tells them apart the way it tells its two
    # quartetti apart: LOMBARDIA A and LOMBARDIA B, never "LOMBARDIA 2".
    letter: str = ""  # "" | "A" | "B" when a region fields more than one
    riders: list[str] = field(default_factory=list)  # [nero, rosso]
    reserves: list[str] = field(default_factory=list)
    bib: int | None = None  # pair bib, when the jury assigns one

    @property
    def label(self) -> str:
        return f"{self.region} {self.letter}".strip()


@dataclass
class EntryList:
    """Effective entry list: riders plus the derived team/pair entities."""

    riders: dict[str, Rider] = field(default_factory=dict)
    teams: dict[str, Team] = field(default_factory=dict)
    pairs: dict[str, Pair] = field(default_factory=dict)
    source_file: str = ""
    source_hash: str = ""
    imported_at: str = ""
    warnings: list[str] = field(default_factory=list)
    # what the jury has to fix before the start: a squadra that does not field
    # the riders the event asks for is not a matter of taste
    errors: list[str] = field(default_factory=list)

    def by_cat(self, cat: str) -> list[Rider]:
        return [r for r in self.riders.values() if r.cat == cat]

    def entered(self, cat: str, event: str,
                include_reserves: bool = False) -> list[Rider]:
        return [r for r in self.by_cat(cat)
                if r.is_entered(event, include_reserves) and not r.not_starting]


# ── Race entities ───────────────────────────────────────────────────────────

@dataclass
class Heat:
    """One heat / batteria: an ordered list of entrant keys with a result."""

    number: int = 1
    entrants: list[str] = field(default_factory=list)  # startlist order
    order: list[str] = field(default_factory=list)  # finishing order
    times: dict[str, str] = field(default_factory=dict)  # entrant -> "m:ss.mmm"
    statuses: dict[str, str] = field(default_factory=dict)
    label: str = ""  # e.g. "Batteria 1"
    note: str = ""


@dataclass
class RaceState:
    """Persisted state of one race: (category, event, round_key)."""

    race_id: str
    cat: str
    event: str
    round_key: str = ""
    fmt: str = ""  # format key: group | elimination | timed | ...
    title: str = ""
    decision: str = ""
    n_laps: float | None = None
    n_sprint: int | None = None
    distance: float | None = None
    entrants: list[str] = field(default_factory=list)  # rider/team/pair keys
    heats: list[Heat] = field(default_factory=list)
    statuses: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)  # format-specific data
    communiques: dict[str, int] = field(default_factory=dict)  # doc kind -> number
    created_at: str = ""
    updated_at: str = ""

    def status(self, key: str) -> Status:
        return status_of(self.statuses.get(key))


def race_id(cat: str, event: str, round_key: str = "") -> str:
    """Canonical, filename-safe id of a race (`races/<id>.json`)."""
    parts = [cat, event, round_key]
    slug = "_".join(p for p in parts if p)
    for ch in " /'.,()":
        slug = slug.replace(ch, "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-").lower()


def race_slug(cat: str, event: str, round_key: str = "") -> str:
    """`CAT_specialita_fase_batteria` - how a printed comunicato is filed.

    The category stays uppercase (`ES` is how the jury writes it) and the heat
    becomes a field of its own, so the parts of the name line up across
    documents. The id of the state file stays lowercase and unsplit: nothing
    on disk moves.
    """
    phase, heat = split_heat(round_key)
    rest = "_".join(p for p in (race_id("", event), race_id("", phase), heat)
                    if p)
    return f"{cat}_{rest}" if cat and rest else (cat or rest)


def split_heat(round_key: str) -> tuple[str, str]:
    """'Qualificazioni Batteria 1' -> ('Qualificazioni', 'batteria-1')."""
    m = re.search(r"\s*batteria\s*(\d+)\s*$", round_key or "", re.I)
    return (round_key[:m.start()], f"batteria-{m.group(1)}") if m \
        else (round_key or "", "")


#: **Programme vocabulary, not a label** (see `formats.omnium`): the word a
#: numbered batteria is scheduled under. It is the one `split_heat` reads back,
#: which is why the two live side by side - a programme that writes them apart
#: is a race the app cannot find on disk.
HEAT_WORD = "Batteria"


def heat_key(phase: str, n: int) -> str:
    """('Qualificazioni', 1) -> 'Qualificazioni Batteria 1'.

    What `split_heat` parses, written the other way round: the builder
    schedules batterie with it, so a proposed programme names them exactly as
    a hand-written one does.
    """
    return " ".join(p for p in (str(phase).strip(), f"{HEAT_WORD} {int(n)}") if p)


# ── (de)serialisation ───────────────────────────────────────────────────────

_NESTED = {
    "events": ("dict", lambda d: EventEntry(**keep_known(EventEntry, d))),
    "riders": ("dict", lambda d: Rider.from_dict(d)),
    "teams": ("dict", lambda d: Team(**keep_known(Team, d))),
    "pairs": ("dict", lambda d: Pair(**keep_known(Pair, d))),
    "heats": ("list", lambda d: Heat(**keep_known(Heat, d))),
}


# Files written before the code moved to the UCI English vocabulary. Reading
# them keeps a championship that is already under way from losing its data;
# nothing is ever written back under these names.
LEGACY_KEYS = {
    "dorsale": "bib", "cognome": "last_name", "nome": "first_name",
    "naz": "nation", "societa": "club", "cod_soc": "club_code",
    "regione": "region", "provincia": "province", "sesso": "sex",
    "data_nascita": "birth_date", "codice_fci": "fci_code",
    "scad_certificato": "certificate_date", "riserva_gara": "reserve_entry",
    "np": "not_starting", "verificato": "checked_in", "titolare": "starter",
    "specialities": "events", "speciality": "event", "spec": "event",
    "phase": "round_key",
    "decisione": "decision", "comunicati": "communiques",
}


def keep_known(cls, d: dict) -> dict:
    """Drop keys the dataclass does not know about (forward compatibility)."""
    names = {f.name for f in fields(cls)}
    out = {}
    for k, v in d.items():
        k = k if k in names else LEGACY_KEYS.get(k, k)
        if k in names:
            out[k] = v
    return out


def _rebuild(cls, d: dict):
    out = {}
    for k, v in keep_known(cls, d).items():
        rule = _NESTED.get(k)
        if rule and v:
            kind, make = rule
            if kind == "dict" and isinstance(v, dict):
                v = {kk: (vv if not isinstance(vv, dict) else make(vv))
                     for kk, vv in v.items()}
            elif kind == "list" and isinstance(v, list):
                v = [make(vv) if isinstance(vv, dict) else vv for vv in v]
        out[k] = v
    return cls(**out)


def to_dict(obj) -> dict:
    """Dataclass -> plain JSON-safe dict."""
    return asdict(obj)


for _cls in (Rider, Team, Pair, Heat, RaceState, EntryList, EventEntry):
    _cls.from_dict = classmethod(lambda cls, d: _rebuild(
        cls, d))  # type: ignore[attr-defined]
    _cls.to_dict = to_dict  # type: ignore[attr-defined]
