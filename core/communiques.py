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

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime

from pathlib import Path

from .config import (DOC_CLASSIFICATION, DOC_PARTIAL, DOC_RESULTS,
                     DOC_STARTLIST, EVENT_ENTRY_LIST, ROUND_SETUP,
                     CommuniqueSpec, Competition, Sheet)
from .i18n import label
from .models import keep_known, number_text, split_heat
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
        for r, rnd in comp.rounds_on(day):
            ev = comp.event(r.event)
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


#: What a sheet the register does not plan is numbered with: **nothing**. The
#: risultati of the prove di gruppo are the case - the register carries a
#: comunicato for the risultati of each batteria and for the classifica of the
#: events, and none for the risultati of the finale - and so is every sheet
#: that rides under another one's number (`number_on_classification`). Not
#: every sheet has a number, and the one that has none says so by printing
#: nothing: in the field, in the cell of the programme, at the head of the
#: sheet and in the name it is filed under. Registers written before this said
#: `-1`, which `models.number_text` still reads back as no number.
UNNUMBERED = ""


def number_for(comp: Competition, cat: str, event: str, round_key: str,
               doc: str) -> str:
    """The planned number of a sheet: this fase, then the event.

    A comunicato is planned for a fase (`Qualificazioni Batteria 1 -
    Risultati`) or for the event as a whole (`Madison - Classifica`, no
    fase). Anything else is a sheet the register does not carry: it comes back
    empty, and the jury gives it a number. Deliberately not `find`, which falls
    back to any entry for the same event: on the risultati of a finale
    that meant printing the number of the first batteria.

    A sheet that goes out under another sheet's number comes back empty too -
    the risultati of a comunicato that also carries the classifica, which is
    where the number is printed (`_numbered_elsewhere`).
    """
    for want in (round_key, ""):
        for c in comp.communiques:
            if c.carries(cat, event, want, doc):
                return (UNNUMBERED if _numbered_elsewhere(comp, c, doc)
                        else number_text(c.label))
    return UNNUMBERED


def _numbered_elsewhere(comp: Competition, spec: CommuniqueSpec,
                        doc: str) -> bool:
    """Whether this document's number is printed on another sheet of its own.

    Risultati e classifica insieme: one comunicato, one number, and the number
    goes on the classifica - the sheet that closes the event and the one
    people look it up by. The risultati under it print none, which is what
    tells a reader of the programme that the two are one sheet and not two.

    A classifica parziale is a classifica for this: in the first prova of an
    omnium the ordine d'arrivo *is* the parziale, and the number belongs to it.
    Off (`Competition.number_on_classification`) both sheets carry it.
    """
    if doc != DOC_RESULTS or not comp.number_on_classification:
        return False
    return any(s.doc in (DOC_CLASSIFICATION, DOC_PARTIAL)
               for s in spec.sheets)


# ── numbering: what goes out, together with what, and in what order ─────────
#
# A number is not a property of a document: it is *when* the document goes out.
# So the register is a view of the running order, and while the programme is
# still being built the two are kept in step - move a race up the day and its
# comunicati move with it. That stops the moment a sheet is in somebody's
# hands: see `autonumber` for the three things that never move again.
#
# Two questions, in this order:
#
# 1. **which documents share a comunicato** (`bundles`). A fase says which
#    sheets it files (`rounds.docs_for`); which of them go out on the same
#    number is a handful of generic rules in `regulations/communiques.json` -
#    the risultati of a fase with the ordine di partenza of the next, the
#    classifica parziale of an omnium prova which *is* the ordine di partenza
#    of the prova after it, the risultati of a race that alone decides the
#    event with its classifica. They used to be expressed by leaving the
#    sheet out of the register altogether, which printed it with no number.
#
# 2. **in what order** (`_publication_key`). Not the order things are ridden:
#    the order they can be *published*. A sheet is ready when the results it
#    is made of are out, and an ordine di partenza is wanted before its fase
#    runs - so every start order that depends on nothing opens the day, and
#    each set of risultati is followed by the start orders it unblocks.


@dataclass
class Bundle:
    """One comunicato as the programme proposes it: the sheets it carries.

    The first names it - it is what the title and the file name come from -
    and the rest ride under it. One sheet is the ordinary case.
    """

    sheets: list[Sheet] = field(default_factory=list)
    day: int = 0
    #: When it can go out, as something to sort on (`_publication_key`). Not
    #: printed and not written anywhere: it is how the register is ordered.
    rank: tuple = ()

    @property
    def key(self) -> tuple:
        return self.sheets[0].key


def merge_rules(comp: Competition, fmt: str) -> set[str]:
    """The rules in force for that format: the table, then what the file says.

    The table (`regulations/communiques.json`) says what a format does
    normally; the competition overrides any of them by name, which is how one
    meeting merges the omnium sheets and the next one does not.
    """
    table = _rules_table().get("formats") or {}
    out = set(table.get("*") or []) | set(table.get(fmt) or [])
    for name, on in (comp.merge or {}).items():
        out.add(name) if on else out.discard(name)
    return out


def rule_names() -> dict[str, dict]:
    """Every rule the table knows, for the page that switches them on and off."""
    return dict(_rules_table().get("rules") or {})


def rule_name(code: str) -> str:
    """What a rule is called, in the language the competition is run in."""
    from .i18n import DEFAULT, language

    names = (rule_names().get(code) or {}).get("name") or {}
    if not isinstance(names, dict):
        return str(names or code)
    return str(names.get(language()) or names.get(DEFAULT) or code)


def rule_on(code: str) -> bool:
    """Whether the table puts that rule in force for any format at all.

    What the switch on the page opens on: a competition states only where it
    *differs* from the table (`Competition.merge`), so the box has to know what
    it would be doing if the competition said nothing.
    """
    table = _rules_table().get("formats") or {}
    return any(code in (names or []) for names in table.values())


def _rules_table() -> dict:
    import json

    path = Path(__file__).resolve().parent.parent / "regulations" / \
        "communiques.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def bundles(comp: Competition) -> list[Bundle]:
    """Every comunicato the programme produces, in the order it goes out."""
    out: list[Bundle] = []
    # the elenchi iscritti are not races and sit in no running order, but they
    # are what the competition opens with - one per categoria, before anybody
    # rides, and before every fase of the first giornata
    first = min(comp.days(), default=1)
    for i, cat in enumerate(comp.cat_order()):
        out.append(_ranked(Bundle(day=first, sheets=[Sheet(
            cat=cat, event=EVENT_ENTRY_LIST, round_key="",
            doc=DOC_STARTLIST)]), (first, -2, 0, i, 0)))
    for day in comp.days():
        out += _day_bundles(comp, day)
    out.sort(key=lambda b: b.rank)
    return out


def _ranked(bundle: Bundle, rank: tuple) -> Bundle:
    return replace(bundle, rank=rank)


def _day_bundles(comp: Competition, day: int) -> list[Bundle]:
    """The comunicati of one giornata: what they carry, and when they can go."""
    plan = comp.rounds_on(day)
    place = {(id(item), id(rnd)): i for i, (item, rnd) in enumerate(plan)}
    ready = _ready_after(comp, plan, place)

    # every document of the day, as a sheet, with the fase that produces it
    loose: list[tuple[tuple, Sheet]] = []
    for i, (item, rnd) in enumerate(plan):
        for order, doc in enumerate(rnd.docs or []):
            sheet = Sheet(cat=item.cat, event=item.event,
                          round_key=sheet_round(doc, rnd.key), doc=doc)
            loose.append((_publication_key(day, i, order, doc, ready, sheet),
                          sheet))
    return _merged(comp, plan, place, ready, loose, day)


def _publication_key(day: int, place: int, order: int, doc: str,
                     ready: dict, sheet: Sheet) -> tuple:
    """When this document can go out, as something to sort on.

    Four things: the giornata; **what it waits for** - the fase whose results
    fill it, `-1` for a sheet that waits for nothing; **what kind** it is, so
    that at the same moment the risultati go out before the start orders they
    unblock; and then the running order, which is the tie-break inside a wave.
    """
    waits = ready.get(sheet.key, place if doc != DOC_STARTLIST else -1)
    kind = 2 if doc == DOC_STARTLIST else (1 if doc in (DOC_CLASSIFICATION,
                                                        DOC_PARTIAL) else 0)
    return (day, waits, kind, place, order)


def _ready_after(comp: Competition, plan: list, place: dict) -> dict:
    """For each start order, the fase whose results it waits for.

    A fase is composed out of the *stage* before it in its own race - the
    finali out of the qualificazioni, the semifinali out of the quarti, the
    finale of a madison out of its batterie - so its ordine di partenza cannot
    be published until those results are. A fase that opens its race waits for
    nothing and goes out with the rest of the morning.

    **Batterie are one stage, not a chain.** Two batterie di qualificazione are
    ridden by different riders and neither composes the other: their start
    orders are both ready at the start of the day, and treating the second as
    waiting on the first would hold half a giornata's sheets back a wave.
    """
    out: dict[tuple, int] = {}
    for item, rnd in plan:
        stages = _stages(item)
        mine = next((i for i, group in enumerate(stages) if rnd in group), 0)
        if mine == 0:
            continue
        earlier = [place.get((id(item), id(r)), -1)
                   for r in stages[mine - 1]]
        earlier = [p for p in earlier if p >= 0]
        if earlier:
            out[Sheet(cat=item.cat, event=item.event, round_key=rnd.key,
                      doc=DOC_STARTLIST).key] = max(earlier)
    return out


def _stages(item) -> list[list]:
    """The ridden fasi grouped into stages: batterie of one fase go together."""
    out: list[list] = []
    last = None
    for rnd in item.rounds:
        if rnd.kind == ROUND_SETUP:
            continue
        base, heat = split_heat(rnd.key)
        if heat and last == base and out:
            out[-1].append(rnd)
        else:
            out.append([rnd])
        last = base if heat else None
    return out


def _merged(comp: Competition, plan: list, place: dict, ready: dict,
            loose: list, day: int) -> list[Bundle]:
    """Group the day's documents into comunicati, by the rules in force."""
    by_key = {sheet.key: (rank, sheet) for rank, sheet in loose}
    taken: set[tuple] = set()
    out: list[Bundle] = []
    for rank, sheet in sorted(loose, key=lambda p: p[0]):
        if sheet.key in taken:
            continue
        rides = _rides_with(comp, plan, place, sheet, by_key, taken)
        taken.add(sheet.key)
        taken |= {s.key for s in rides}
        out.append(_ranked(Bundle(day=day, sheets=[sheet] + rides), rank))
    return out


def _rides_with(comp: Competition, plan: list, place: dict, sheet: Sheet,
                by_key: dict, taken: set) -> list[Sheet]:
    """Every sheet that goes out under this one, the rules applied to the end.

    Transitively, because the rules chain: in the first prova of an omnium the
    risultati carry the classifica parziale, and that parziale is the ordine di
    partenza of the prova after it - three documents, one number. Applying the
    rules only to the sheet that names the comunicato would publish the first
    two together and leave the third to find a number of its own.
    """
    out: list[Sheet] = []
    seen = set(taken) | {sheet.key}
    queue = [sheet]
    while queue:
        for found in _rides_directly(comp, queue.pop(0), by_key, seen):
            if found.key in seen:
                continue
            seen.add(found.key)
            out.append(found)
            queue.append(found)
    return out


def _rides_directly(comp: Competition, sheet: Sheet, by_key: dict,
                    taken: set) -> list[Sheet]:
    """The sheets one rule away from this one, by the rules of its format."""
    fmt = comp.event(sheet.event).fmt
    rules = merge_rules(comp, fmt)
    item = comp.scheduled(sheet.cat, sheet.event)
    if item is None:
        return []
    ridden = [r for r in item.rounds if r.kind != ROUND_SETUP]
    keys = [r.key for r in ridden]
    here = keys.index(sheet.round_key) if sheet.round_key in keys else -1
    after = keys[here + 1] if 0 <= here < len(keys) - 1 else ""

    def free(round_key: str, doc: str) -> Sheet | None:
        want = Sheet(cat=sheet.cat, event=sheet.event, round_key=round_key,
                     doc=doc).key
        found = by_key.get(want)
        return found[1] if found and want not in taken else None

    rides: list[Sheet] = []
    if sheet.doc == DOC_RESULTS:
        # the risultati of the race that alone decides the event *are* its
        # classifica: one table, printed once, one number. The other rule is
        # not that - two tables, one sheet, because the second comes out of the
        # first with nothing in between (an omnium and its corsa a punti)
        closing = here == len(ridden) - 1
        if (("results_are_classification" in rules and _decided_alone(item, here))
                or ("last_results_with_classification" in rules and closing)):
            rides += [s for s in [free("", DOC_CLASSIFICATION)] if s]
        if "results_with_next_startlist" in rules and after:
            rides += [s for s in [free(after, DOC_STARTLIST)] if s]
        if "partial_is_results_of_first" in rules and here == _first_prova(
                comp, item):
            rides += [s for s in [free(sheet.round_key, DOC_PARTIAL)] if s]
    elif sheet.doc == DOC_PARTIAL and "partial_is_next_startlist" in rules \
            and after:
        # the standings after a prova are the ordine di partenza of the next
        rides += [s for s in [free(after, DOC_STARTLIST)] if s]
    return rides


def _decided_alone(item, here: int) -> bool:
    """Whether one race alone decides this event.

    A madison is one finale, and its classifica *is* that finale's order of
    arrival: one table, one sheet, one number. A velocità a squadre rides two
    finals and a pursuit rides a qualification before them, so their classifica
    is a third table and goes out on its own.

    The batterie di qualificazione are not counted - nobody reads a classifica
    off them - but a `Qualificazioni` that is a fase in its own right is.
    """
    ridden = [r for r in item.rounds if r.kind != ROUND_SETUP]
    alone = [r for r in ridden if not split_heat(r.key)[1]]
    return here == len(ridden) - 1 and len(alone) == 1


def _first_prova(comp: Competition, item) -> int:
    """Where the first prova of an omnium sits among its ridden fasi.

    Not the first fase: an omnium can open on batterie di qualificazione, which
    are not prove and score nothing.
    """
    ridden = [r for r in item.rounds if r.kind != ROUND_SETUP]
    for i, r in enumerate(ridden):
        if not split_heat(r.key)[1]:
            return i
    return -1


def sheet_order(comp: Competition) -> list[Sheet]:
    """Every document the programme produces, in the order it is issued.

    The flat reading of `bundles`: the sheets of every comunicato, in the order
    they print, one after another. What is numbered is the comunicato, so this
    is what a caller wants only when it is asking about *sheets*.
    """
    return [sheet for bundle in bundles(comp) for sheet in bundle.sheets]


def fixed_numbers(comp: Competition, register: list[Issued] | None = None
                  ) -> dict[tuple, int]:
    """The sheets whose number must not move, and the number each one has.

    Three reasons a number is fixed, and they are the same reason three times:
    somebody is expecting it. A comunicato the jury numbered by hand
    (`pinned`); one that has already been *issued* - printed, signed, handed to
    the teams; and an annullato (`ret`), which is a tombstone - the sheet is
    gone and the number stays spent, on the row that says so.

    The second is the error `programme.issues` raises after the fact; here it
    is prevented instead.
    """
    out: dict[tuple, int] = {}
    for c in comp.communiques:
        if c.pinned or c.ret:
            out[c.sheets[0].key] = c.n
    for i in register or []:
        out[Sheet(cat=i.cat, event=i.event, round_key=i.round_key,
                  doc=i.doc).key] = i.n
    return out


def autonumber(comp: Competition, register: list[Issued] | None = None,
               *, start: int = 1, add_missing: bool = True,
               rebuild: bool = False) -> list[CommuniqueSpec]:
    """The register, renumbered - and re-grouped - from the running order.

    What the jury gets back is what it had: the same comunicati, keeping their
    own titles, with the numbers redealt in the order things can be published
    (`bundles`) and flowing around the ones that are fixed (`fixed_numbers`).
    A comunicato the programme produces and the register does not carry yet is
    added, unless `add_missing` says otherwise.

    `rebuild` is the other half of it, and the one to reach for when a register
    has stopped meaning anything: the accorpamenti are re-read from the rules
    as well, so a comunicato that used to carry one sheet comes back carrying
    the two it should. Without it the sheets of an entry the jury already has
    are left exactly as they are.

    **Nothing is ever thrown away**, unless that is the request. An entry whose
    sheet the programme does not produce keeps its number and stays where it
    is: it is either a fase spelled differently in the two places (`Finali -`
    against `Finali`) or a document nobody declares any more, and
    `programme.issues` reports both. A rebuild *does* drop them - it is what
    rebuilding means - except the ones on paper: issued, pinned by hand, or
    annulled.

    Nothing here writes: it returns a list, and the page puts it on the draft
    once somebody has seen what it would do (`changes`). The register does not
    renumber itself behind anybody: it used to, on every rerun, and the switch
    that stopped it was the only thing standing between an inherited register
    and being rewritten uninvited.
    """
    fixed = fixed_numbers(comp, register)
    by_key = {c.sheets[0].key: c for c in comp.communiques}
    plan = bundles(comp)
    produced = {s.key for b in plan for s in b.sheets}
    # Numbers that cannot be handed out again: the fixed ones, the annullati
    # (the sheet is gone but the number stays spent), and the entries the
    # programme does not produce, which are staying where they are.
    orphans = [c for c in comp.communiques
               if not any(s.key in produced for s in c.sheets)]
    if rebuild:
        # rebuilding *is* the request to drop what the programme no longer
        # produces - a fase renamed under a comunicato, a race taken out of the
        # meeting. What is on paper is not dropped by anything: an issued or
        # pinned number is somebody's expectation, and an annullato is a
        # tombstone that has to keep saying so.
        keep = {i.n for i in register or []}
        orphans = [c for c in orphans if c.pinned or c.ret or c.n in keep]
    taken = (set(fixed.values()) | {c.n for c in comp.communiques if c.ret}
             | {c.n for c in orphans})

    out: list[CommuniqueSpec] = []
    seen: set[tuple] = set()
    n = start - 1
    for bundle in [b for whole in plan for b in _split(whole, by_key, rebuild)]:
        spec = next((by_key[s.key] for s in bundle.sheets if s.key in by_key),
                    None)
        if spec is not None and spec.sheets[0].key in seen:
            continue                      # a second document of the same sheet
        if spec is None and not add_missing:
            continue                      # a sheet the jury numbers no comunicato for
        if spec is not None:
            seen.add(spec.sheets[0].key)
        want = fixed.get(bundle.key)
        if want is None and spec is not None:
            want = fixed.get(spec.sheets[0].key)
        if want is not None:
            out.append(_renumbered(comp, spec, bundle, want, rebuild))
            continue
        n += 1
        while n in taken:
            n += 1
        out.append(_renumbered(comp, spec, bundle, n, rebuild))
    return sorted(out + orphans, key=lambda c: c.n)


def _split(bundle: Bundle, by_key: dict, rebuild: bool) -> list[Bundle]:
    """The comunicati this bundle actually becomes, given what is already there.

    The rules say three sheets go out together; the register may already carry
    two of them on numbers of their own, and those numbers are the jury's
    record. So without `rebuild` the bundle is **cut** wherever an entry
    already exists: what the jury numbered stays numbered, and only the sheets
    nobody had a comunicato for join the one above them.

    Rebuilding is the request to stop doing that and take the rules' answer.
    """
    if rebuild or len(bundle.sheets) < 2:
        return [bundle]
    out: list[Bundle] = []
    for sheet in bundle.sheets:
        if out and sheet.key not in by_key:
            out[-1].sheets.append(sheet)
        else:
            out.append(replace(bundle, sheets=[sheet]))
    return out


def _carried(by_key: dict[tuple, CommuniqueSpec]) -> set[tuple]:
    """Every sheet that rides on a comunicato numbered for another document."""
    return {s.key for c in by_key.values() for s in c.sheets[1:]}


def _renumbered(comp: Competition, spec: CommuniqueSpec | None,
                bundle: Bundle, n: int, rebuild: bool) -> CommuniqueSpec:
    """One entry at its new number, keeping everything the jury wrote on it.

    A comunicato the register already carries keeps its title and its sheets -
    what it publishes is the jury's statement, not the rules' - unless the
    caller is rebuilding, which is exactly the request to take the rules'
    answer instead.
    """
    if spec is not None and not rebuild:
        return replace(spec, n=n)
    first, *rest = bundle.sheets
    return CommuniqueSpec(
        n=n, day=bundle.day or _day_of(comp, first), cat=first.cat,
        event=first.event, round_key=first.round_key, doc=first.doc,
        # rebuilding is the request to take the rules' answer, titles
        # included: a comunicato that now carries two documents and is still
        # called after one of them is why nobody could find the second
        title=title_of(comp, bundle),
        pinned=spec.pinned if spec is not None else False,
        ret=spec.ret if spec is not None else False,
        extra=[Sheet(cat=s.cat, event=s.event, round_key=s.round_key,
                     doc=s.doc) for s in rest])


def title_of(comp: Competition, bundle: Bundle) -> str:
    """What a comunicato is called: its documents, joined and said once.

    *ES Omnium Scratch - Risultati e Classifica Parziale, Tempo Race - Ordine
    di Partenza*. The category and the event are the same for every sheet
    of a comunicato, so they open the title and are not repeated; a fase is
    named once and its documents listed after it. One sheet reads exactly as it
    always did.

    A comunicato that publishes two things and is named after one of them is
    the reason nobody could find the ordine di partenza of the semifinali in
    the register - it was there, under the risultati of the quarti, unnamed.
    """
    from .i18n import label as _label
    from .i18n import ui as _ui

    first = bundle.sheets[0]
    head = " ".join(b for b in (first.cat, _short(comp, first.event)) if b)
    groups: list[tuple[str, list[str]]] = []
    for sheet in bundle.sheets:
        rnd = comp.round_of(sheet.cat, sheet.event, sheet.round_key)
        where = "" if sheet.doc == DOC_CLASSIFICATION else rnd.label
        if groups and groups[-1][0] == where:
            groups[-1][1].append(_label(sheet.doc))
        else:
            groups.append((where, [_label(sheet.doc)]))
    said = [" - ".join(b for b in (where, _ui("title_join").join(docs)) if b)
            for where, docs in groups]
    body = ", ".join(said)
    if not head:
        return body
    # the rule between the head and the first document, unless a fase is named
    # first - `ES Velocità Quarti - Risultati` against `ES Iscritti - Partenti`
    return head + (" " if groups[0][0] else " - ") + body


def _short(comp: Competition, code: str) -> str:
    """What an event is called in a title, even where the file omits it.

    A programme need not declare the elenco iscritti to publish one, and a
    title reading `ES entry_list` is the code leaking onto paper.
    """
    ev = comp.event(code)
    if ev.short != code:
        return ev.short
    if code == EVENT_ENTRY_LIST:
        from .i18n import ui as _ui
        return _ui("entry_list_title")
    return code


def _day_of(comp: Competition, sheet: Sheet) -> int:
    item = comp.scheduled(sheet.cat, sheet.event)
    return item.day if item else 0


# ── register of what was issued ─────────────────────────────────────────────

def load(store) -> list[Issued]:
    """Read the register, including files written before the English rename."""
    return [Issued(**keep_known(Issued, d))
            for d in store.read_json(REGISTER_FILE, [])]


def save(store, register: list[Issued], action: str = "register") -> None:
    store.write_json(REGISTER_FILE, [asdict(i) for i in register], action=action)


def sheet_round(doc: str, round_key: str) -> str:
    """The fase a sheet is filed against - none, when it is a classifica.

    The classifica closes the event and belongs to no fase (`config.Sheet`),
    which is how the plan states it (`_day_bundles`). A register that filed it
    against the fase it happened to be printed from would not match the sheet
    the plan carries, and the check would report as moved a comunicato nobody
    has moved (`programme.issues`).
    """
    return "" if doc == DOC_CLASSIFICATION else round_key


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
    round_key = sheet_round(doc, round_key)
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


# ── what a recount would do, before it does it ──────────────────────────────

#: Why a number does not move: it is on paper, or somebody typed it.
HELD_ISSUED = "issued"
HELD_PINNED = "pinned"
HELD_RET = "ret"


@dataclass
class Change:
    """One line of the register, as a recount would leave it.

    `kind` is what happens to it - `moved`, `added`, `dropped`, or `held` for
    an entry that does not move because it may not. `why` names the reason on
    the ones that are held, which is the half of the answer nobody could see:
    a register that renumbered itself never said what it had flowed around.
    """

    kind: str
    n: int = 0          # the number it would carry; 0 for a dropped entry
    was: int = 0        # the number it carries now; 0 for a new one
    title: str = ""
    why: str = ""


def changes(comp: Competition, register: list[Issued] | None = None, *,
            rebuild: bool = False) -> list[Change]:
    """What `autonumber` would do to this register, line by line.

    The register is not renumbered behind anybody: the page asks for this
    first, shows it, and only writes if the answer is wanted. So the diff is
    part of the numbering and not a nicety - it is what makes an action that
    rewrites a hundred and forty lines something a jury can agree to.

    An entry is matched to its old self by the sheet it is named after, which
    is what survives a rebuild: the title and the sheets riding under it are
    exactly what a rebuild is allowed to change.
    """
    issued = {i.n for i in register or []}
    want = autonumber(comp, register, rebuild=rebuild)
    was = {c.sheets[0].key: c for c in comp.communiques}
    out: list[Change] = []
    for c in want:
        old = was.pop(c.sheets[0].key, None)
        why = (HELD_ISSUED if c.n in issued else
               HELD_RET if c.ret else HELD_PINNED if c.pinned else "")
        if old is None:
            out.append(Change("added", c.n, 0, c.title, why))
        elif old.n != c.n:
            out.append(Change("moved", c.n, old.n, c.title, why))
        elif why:
            out.append(Change("held", c.n, old.n, c.title, why))
    for c in was.values():
        # only a rebuild drops anything, and never what is on paper
        out.append(Change("dropped", 0, c.n, c.title,
                          HELD_ISSUED if c.n in issued else
                          HELD_RET if c.ret else
                          HELD_PINNED if c.pinned else ""))
    return sorted(out, key=lambda c: (c.n or c.was, c.was))


def counted(rows: list[Change]) -> dict[str, int]:
    """How many of each kind, for the line that says it in one sentence."""
    out = {"moved": 0, "added": 0, "dropped": 0, "held": 0}
    for row in rows:
        out[row.kind] = out.get(row.kind, 0) + 1
    return out
