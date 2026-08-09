"""The communiqué register: plan the numbers, then hand them out.

The register is authored in `programme.yaml` (for CITA 26 it is the 140-entry
list transcribed from *Lista Comunicati*, verified against the number printed
on every jury workbook). At print time a document takes its planned number; a
document that was not planned gets the next free one and is recorded, so the
register always reflects what was actually issued.

Numbers run continuously across the whole competition and are never reused; an
annulled document keeps its number and is marked `RET`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .config import (DOC_STARTLIST, EVENT_ENTRY_LIST, CommuniqueSpec,
                     Competition)
from .i18n import label
from .models import keep_known
from .parse import duplicates as _duplicates

REGISTER_FILE = "comunicati.json"


@dataclass
class Issued:
    """A communiqué as actually produced."""

    n: int
    title: str = ""
    cat: str = ""
    event: str = ""
    round_key: str = ""
    doc: str = ""
    ret: bool = False
    issued_at: str = ""
    file: str = ""

    @property
    def label(self) -> str:
        return f"{self.n} RET" if self.ret else str(self.n)


# ── planning ────────────────────────────────────────────────────────────────

def planned(comp: Competition) -> list[CommuniqueSpec]:
    return sorted(comp.communiques, key=lambda c: c.n)


def plan_from_programme(comp: Competition) -> list[CommuniqueSpec]:
    """Propose a register from the running order, when none is authored.

    Documents are numbered day by day: first the entry lists, then for each
    event in programme order its startlist / results / classification.
    """
    out: list[CommuniqueSpec] = []
    n = 0
    for cat in comp.cat_order():
        n += 1
        out.append(CommuniqueSpec(n=n, day=1, cat=cat, event=EVENT_ENTRY_LIST,
                                  doc=DOC_STARTLIST,
                                  title=f"{label('entered').capitalize()} {cat}"))
    for day in comp.days():
        for r in [r for r in comp.programme if r.day == day]:
            ev = comp.event(r.event)
            for rnd in r.rounds:
                for doc in rnd.docs:
                    n += 1
                    bits = [r.cat, ev.short, rnd.label, "-", label(doc)]
                    out.append(CommuniqueSpec(
                        n=n, day=day, cat=r.cat, event=r.event,
                        round_key=rnd.key, doc=doc,
                        title=" ".join(b for b in bits if b)))
    return out


def find(comp: Competition, cat: str, event: str, round_key: str, doc: str, *,
         exact: bool = False) -> CommuniqueSpec | None:
    """The planned entry for a document.

    By default a round_key that is not in the register falls back to any planned
    entry for the same (category, event, document) - good enough to
    pre-fill the field in the UI, where the jury sees and can correct it.
    `exact=True` disables that: issuing a number must never silently reuse the
    one planned for a different round_key.
    """
    pools = [[c for c in comp.communiques
              if c.carries(cat, event, round_key, doc)]]
    if not exact:
        pools.append([c for c in comp.communiques
                      for s in c.sheets
                      if s.cat == cat and s.event == event and s.doc == doc])
    for pool in pools:
        if pool:
            return sorted(pool, key=lambda c: c.n)[0]
    return None


#: What a sheet the register does not plan is numbered with. The risultati of
#: the prove di gruppo are the case: the register carries a comunicato for the
#: risultati of each batteria and for the classifica of the specialità, and none
#: for the risultati of the finale; an omnium files the risultati of a prova
#: unnumbered, because the sheet that goes out is the classifica parziale after
#: it. `-1` says so - it is visible in the field, it sorts before every real
#: number in the out folder, and it is not a number belonging to another sheet.
UNNUMBERED = "-1"


def number_for(comp: Competition, cat: str, event: str, round_key: str,
               doc: str) -> str:
    """The planned number of a sheet: this fase, then the specialità.

    A comunicato is planned for a fase (`Qualificazioni Batteria 1 -
    Risultati`) or for the specialità as a whole (`Madison - Classifica`, no
    fase). Anything else is a sheet the register does not carry: it opens on
    `-1`, and the jury gives it a number. Deliberately not `find`, which falls
    back to any entry for the same specialità: on the risultati of a finale that
    meant printing the number of the first batteria.
    """
    for want in (round_key, ""):
        for c in comp.communiques:
            if c.carries(cat, event, want, doc):
                return c.label
    return UNNUMBERED


# ── register of what was issued ─────────────────────────────────────────────

def load(store) -> list[Issued]:
    """Read the register, including files written before the English rename."""
    return [Issued(**keep_known(Issued, d))
            for d in store.read_json(REGISTER_FILE, [])]


def save(store, register: list[Issued], action: str = "register") -> None:
    store.write_json(REGISTER_FILE, [asdict(i) for i in register], action=action)


def next_free(comp: Competition, register: list[Issued]) -> int:
    used = {i.n for i in register} | {c.n for c in comp.communiques}
    n = 1
    while n in used:
        n += 1
    return n


def issue(store, comp: Competition, *, cat: str, event: str, round_key: str,
          doc: str, number: int | str = "", title: str = "",
          file: str = "") -> Issued:
    """Record a comunicato as issued, reusing its planned number when there is one."""
    register = load(store)
    if not number:
        planned_event = find(comp, cat, event, round_key, doc, exact=True)
        number = planned_event.n if planned_event else next_free(comp, register)
        title = title or (planned_event.title if planned_event else "")

    txt = str(number).strip().upper()
    ret = txt.endswith("RET")
    n = int("".join(ch for ch in txt if ch.isdigit()) or 0)

    entry = Issued(n=n, title=title, cat=cat, event=event, round_key=round_key, doc=doc,
                   ret=ret, issued_at=datetime.now().isoformat(timespec="seconds"),
                   file=file)
    register = [i for i in register if i.n != n] + [entry]
    register.sort(key=lambda i: i.n)
    save(store, register, action="issue_comunicato")
    return entry


def duplicates(register: list[Issued]) -> list[int]:
    """Numbers handed out more than once (see `parse.duplicates`)."""
    return _duplicates([i.n for i in register])


def status(comp: Competition, register: list[Issued]) -> list[dict]:
    """Register view: every planned document plus anything issued off-plan."""
    issued = {i.n: i for i in register}
    rows = []
    for c in planned(comp):
        i = issued.pop(c.n, None)
        rows.append({"n": c.n, "label": i.label if i else c.label,
                     "day": c.day, "cat": c.cat, "event": c.event,
                     "round_key": c.round_key, "doc": c.doc, "title": c.title,
                     # every document the number carries, the first included:
                     # a register that named only the first would not say what
                     # is actually on the sheet
                     "docs": [s.doc for s in c.sheets], "sheets": c.sheets,
                     "issued": bool(i), "issued_at": i.issued_at if i else "",
                     "file": i.file if i else ""})
    for i in sorted(issued.values(), key=lambda i: i.n):
        rows.append({"n": i.n, "label": i.label, "day": 0, "cat": i.cat,
                     "event": i.event, "round_key": i.round_key, "doc": i.doc,
                     "docs": [i.doc], "sheets": [],
                     "title": f"{i.title} ({label('off_plan')})", "issued": True,
                     "issued_at": i.issued_at, "file": i.file})
    return sorted(rows, key=lambda r: r["n"])
