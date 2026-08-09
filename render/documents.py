"""Builders that turn entry lists and race states into printable Documents."""

from __future__ import annotations

from dataclasses import replace

from core import medals as M
from core import race as R
from core import recap as RC
from core.config import (DOC_CLASSIFICATION, DOC_RESULTS, DOC_STARTLIST,
                         Competition, EVENT_ENTRY_LIST)
from core.formats import timed as T
from core.formats.base import Result
from core.models import EntryList, RaceState, Rider, Status, race_slug
from core.i18n import label, msg, plural, ui
from core.parse import format_time

from .render import (COL_INDEX, COLS_RIDER, COLS_RIDER_MIN, W_GROUP, W_LANE,
                     W_LAPS, W_POINTS, W_RANK, W_SPRINT, W_TIME, W_TOTAL,
                     Column, Document, Note, Table, group_start, numbered,
                     position_label, rider_row, side_start, slugify, zebra)


def _sorted(riders: list[Rider]) -> list[Rider]:
    return sorted(riders, key=lambda r: (r.bib is None, r.bib or 0,
                                         r.last_name, r.first_name))


def decision_notes(decisions=(), *, codes: bool = False) -> list[Note]:
    """The decisions of a race as the blocks that print under its table.

    With `codes` the block opens with the compact code it was taken under -
    `A1`, `C3` - as its tag: the sentence says what was decided and the code
    says under which article, which is the pair a team reads before deciding
    whether to appeal. It is off unless the competition asks for it
    (`Branding.decision_codes`): most panels publish the sentence, which is
    already written in full, and keep the article in their own register.

    A decision the jury never wrote text for prints nothing: a coloured box
    with a code and no sentence is a sanction nobody can answer.
    """
    return [Note(text=d.text.strip(), kind=d.kind,
                 title=d.code if codes else "")
            for d in decisions if (d.text or "").strip()]


def entry_list(el: EntryList, comp: Competition, cat: str, *,
               matrix: bool = False, index: bool = True,
               include_np: bool = False,
               only_verified: bool = False, minimal: bool = False,
               communique: str = "", font_size: int = 9,
               decision: str = "") -> Document:
    """The entry list of one category, optionally with the event matrix.

    With the NP printed it is the ELENCO ISCRITTI - everyone entered, and the
    count says how many of them actually start. Without them the same sheet is
    the ELENCO PARTENTI: it lists only who takes the start.
    """
    riders = _sorted([r for r in el.by_cat(cat)
                      if (include_np or not r.not_starting)
                      and (not only_verified or r.checked_in)])
    # event columns in the workbook's order, not the running order
    contested = set(comp.events_for(cat))
    events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST and s in contested]

    cols = ([COL_INDEX] if index else []) + \
        list(COLS_RIDER_MIN if minimal else COLS_RIDER)
    legend = ""
    if matrix and events:
        # full event names never fit across the matrix: the columns carry the
        # UCI sigle and the key is printed under the table, for every category
        heads = comp.event_headers(events, abbr=True)
        for code in events:
            cols.append(Column(f"ev_{code}", heads[code], "c", 5))
        legend = msg("event_key", list="  ·  ".join(
            f"{heads[c]} = {comp.event(c).short}" for c in events))

    rows = []
    for r in riders:
        extra = {f"ev_{c}": (r.events[c].flag if c in r.events else "")
                 for c in events} if matrix else {}
        rows.append(rider_row(r, **extra))
    if index:
        numbered(rows)

    starters = sum(1 for r in riders if not r.not_starting)
    return Document(
        title=f"{comp.cat(cat).name} - "
              + (label("entry_list") if include_np
                 else label("startlist").upper()),
        info=(msg("count_entered_starters", entered=len(riders),
                  starters=starters) if include_np
              else msg("count_starters", n=starters)),
        legend=legend,
        communique=communique,
        tables=[Table(columns=cols, rows=zebra(rows), font_size=font_size)],
        decision=decision,
        slug=f"{cat}_{label('entry_list_slug' if include_np
                             else 'startlist_slug')}",
    )


def event_entry_list(el: EntryList, comp: Competition, cat: str,
                     event: str, *, communique: str = "",
                     include_reserves: bool = True,
                     only_verified: bool = False, font_size: int = 9,
                     decision: str = "") -> Document:
    """Riders entered in one event, grouped by team / pair / region."""
    ev = comp.event(event)
    riders = _sorted([r for r in el.entered(cat, event,
                                            include_reserves=include_reserves)
                      if not only_verified or r.checked_in])

    grouped = ev.fmt in ("timed_team", "madison")
    head = (label("pair") if ev.fmt == "madison"
            else label("team") if grouped else label("region"))
    cols = [Column("group", head, "l", W_GROUP)]
    cols += [c for c in COLS_RIDER_MIN if c.key != "region"]
    cols.append(Column("club", label("club"), "l", 26))

    rows: list[dict] = []
    groups = _group(el, comp, cat, event, riders)
    for name, members in groups:
        for i, r in enumerate(members):
            e = r.events.get(event)
            mark = "" if not e or e.starter else " (R)"
            row = rider_row(r, group=(name + mark) if i == 0 else "")
            rows.append(group_start(row) if i == 0 and rows else row)

    # entry lists carry the distance of the first round_key in the programme
    rounds = comp.rounds(cat, event)
    d, laps, sprints = comp.distances(cat, event, rounds[0].key if rounds else "")

    return Document(
        title=f"{comp.cat(cat).name} - {ev.name}",
        subtitle=label("startlist"),
        # a team event starts teams, not riders: counting heads here would
        # say 12 where the jury needs to read 3
        info=distance_line(len(groups) if grouped else len(riders),
                            d, laps, sprints,
                            unit=_count_unit(R.MADISON if ev.fmt == "madison"
                                             else R.TIMED_TEAM if grouped
                                             else R.SCRATCH)),
        communique=communique,
        tables=[Table(columns=cols, rows=rows, font_size=font_size)],
        decision=decision,
        slug=race_slug(cat, event),
    )


# Column weights of a classification that also carries the societies: the sheet
# has two columns more to place. Who rode is what the sheet is read for, so the
# names keep their width and the society name - the one value that still reads
# when it is cut short - gives it up.
CLUB_SHEET_W = {"rank": 6, "bib": 6, "last_name": 23, "first_name": 17,
                "uci_id": 16, "club": 22, "group": 19, "time": 13,
                "lane": 8}


def _sheet_note(state: RaceState, doc_kind: str) -> str:
    """The note the jury wrote on this particular sheet, if any."""
    return ((state.payload or {}).get("notes") or {}).get(doc_kind, "")


def _count_unit(kind: str) -> str:
    """What the head count counts: riders, or the teams they ride for."""
    return (label("pairs") if kind == R.MADISON
            else label("teams") if R.is_team_format(kind)
            else label("starters"))


def distance_line(n: int = 0, d: float = 0, laps: float = 0, sprints: int = 0,
                  unit: str = "", heats: int = 0) -> str:
    """The line under the title: how long the race is, and how many ride it.

    Under the kilometre the distance is called in metres, the way it is
    announced - the velocità is the 200 m, not the 0,2 km. Half a lap is not
    printed at all: "0,5 giri" is arithmetic, not information, and the 200 m
    lanciati are the only race it ever applied to.
    """
    return "  ·  ".join(x for x in [
        msg("heats_count", n=heats) if heats > 1
        else msg("heat_one") if heats else "",
        f"{n} {unit or label('starters')}" if n else "",
        (f"{d * 1000:g} m" if 0 < d < 1 else f"{d:g} km") if d else "",
        f"{laps:g} {label('laps').lower()}" if laps and laps >= 1 else "",
        f"{sprints} {label('sprint').lower()}" if sprints else "",
    ] if x)


def _group(el: EntryList, comp: Competition, cat: str, event: str,
           riders: list[Rider]) -> list[tuple[str, list[Rider]]]:
    """Group riders into teams / pairs / regions for the printed sheet."""
    fmt = comp.event(event).fmt
    by_key = {r.key: r for r in riders}
    out: list[tuple[str, list[Rider]]] = []
    used: set[str] = set()

    if fmt == "timed_team":
        for t in sorted(el.teams.values(), key=lambda t: (t.region, t.letter)):
            if t.cat != cat or t.event != event:
                continue
            members = [by_key[k] for k in t.riders + t.reserves if k in by_key]
            if members:
                out.append((t.label, members))
                used.update(m.key for m in members)
    elif fmt == "madison":
        for p in sorted(el.pairs.values(), key=lambda p: (p.region, p.number)):
            if p.cat != cat:
                continue
            members = [by_key[k] for k in p.riders + p.reserves if k in by_key]
            if members:
                # once the coppie are numbered they are called by their number;
                # before that - this sheet is printed to compose them - by the
                # A/B letter that tells the two coppie of a region apart
                out.append((str(p.bib) if p.bib else p.label, members))
                used.update(m.key for m in members)
    else:
        regions: dict[str, list[Rider]] = {}
        for r in riders:
            regions.setdefault(r.region, []).append(r)
        return [(reg, regions[reg]) for reg in sorted(regions)]

    leftover = [r for r in riders if r.key not in used]
    if leftover:
        out.append(("-", leftover))
    return out


# ── race documents ──────────────────────────────────────────────────────────

def _race_titles(comp: Competition, state: RaceState) -> tuple[str, str]:
    ev = comp.event(state.event)
    title = f"{comp.cat(state.cat).name} - {ev.name}"
    return title, state.round_key


W_PAIR_NO = 7      # Coppia, when it holds a number instead of a region name


def mark_warned(rows: list[dict], warned) -> list[dict]:
    """Write the W of an ammonizione onto the dorsale it belongs to: '1 W'.

    On the number and not in a column of its own: the W is read as part of the
    dorsale - it is what the jury writes next to it on the workbook - and a
    column for it would take width off every line of every sheet for a mark
    that is usually not there at all.
    """
    for row in rows:
        bib = row.get("bib")
        if isinstance(bib, int) and bib in warned:
            row["bib"] = f"{bib} {label('W')}"
    return rows


def _pair_number(key: str, el: EntryList) -> str:
    """The number a madison coppia wears, '' before the jury assigns one."""
    pair = el.pairs.get(key)
    return str(pair.bib) if pair is not None and pair.bib else ""


def _pair_cells(row: dict, key: str, el: EntryList, index: int) -> dict:
    """The coppia number on one rider's line: black for the first of the two,
    red for the second - the colours of the numbers they wear on the track.

    Both riders carry it, and it stays bold: on a madison sheet the coppia is
    what is ranked, and the number is what the jury shouts and writes down.
    The dorsale, where the sheet carries it, follows the same two colours: it
    is the same rider, and on the track it is the same number.
    """
    row["group"] = _pair_number(key, el)
    row["_bold"] = list(row.get("_bold", [])) + ["group", "bib"]
    if index == 1:
        row["_red"] = list(row.get("_red", [])) + ["group", "bib"]
    return row


def _entrant_rows(keys, el: EntryList, cat: str = "") -> list[dict]:
    """One line per rider, numbered by entrant, with a rule above each group.

    `cat` is what a bare dorsale is resolved against: the same number is worn
    in every category (see `race.entrant_riders`).
    """
    rows: list[dict] = []
    grouped = any(k in el.teams or k in el.pairs for k in keys)
    for n, key in enumerate(keys, start=1):
        riders = R.entrant_riders(key, el, cat)
        name = R.entrant_label(key, el)
        pair = key in el.pairs
        cell = (_pair_number(key, el) or str(n)) if pair else str(n) if grouped else ""
        if not riders:
            row = {"group": cell, "team": name}
            rows.append(group_start(row) if rows else row)
            continue
        for i, r in enumerate(riders):
            row = rider_row(r, group=cell if i == 0 else "",
                            team=name if grouped else r.region)
            if pair:
                _pair_cells(row, key, el, i)
            rows.append(group_start(row) if (i == 0 and rows and grouped) else row)
    return rows


def _side_team(side: list[int], entrants, el: EntryList, cat: str = "") -> str:
    """Which team a side of a heat is, matched on bibs.

    Matched, not looked up: a reserve riding in place of a starter changes one
    number and must not cost the team its name on the sheet.
    """
    best, score = "", 0
    for k in entrants:
        n = len({r.bib for r in R.entrant_riders(k, el, cat)} & set(side))
        if n > score:
            best, score = k, n
    # an individual entrant *is* a dorsale: labelled, it prints the number
    # again in the Team column, where the rider's own region belongs
    if best not in el.teams and best not in el.pairs:
        return ""
    return R.entrant_label(best, el)


def final_heat_labels(state: RaceState) -> list[str]:
    """'3/4', '1/2' - what the heats of a finals round are called."""
    p = state.payload or {}
    ranking = p.get("qual_ranking") or []
    return [T.final_label(T.final_place(h, ranking))
            for h in p.get("final_heats") or []]


def _heat_rows(heats: list[list[list[int]]], el: EntryList,
               entrants=(), labels: list[str] = (), cat: str = "") -> list[dict]:
    """One block per heat, ruled the way the results of the same round are.

    The heat number is printed once per heat, against its first team: the
    second team is in the same batteria, and the number repeated next to it
    only read as a second heat. In a finals round the number is the final:
    the 3/4, then the 1/2.

    Where a side is one rider - a velocità - a batteria is two lines that
    belong together: a hairline opens it and nothing at all comes between the
    two, exactly as on the risultati. The rules a team sheet needs (a heavy one
    between batterie, a light one between the two quartetti of a batteria) are
    for four lines against four, where without them the block cannot be read.
    """
    # inside the category that is racing: a dorsale belongs to a category, and
    # looked up across the whole competition it printed the ES rider, or the DA
    # one, on an AL sheet (see `race.entrant_riders`)
    by_bib = R.riders_by_bib(el, cat)
    rows: list[dict] = []
    for h, heat in enumerate(heats):
        # one rider a side: a batteria of individuals, ruled like its results
        solo = all(len(side) == 1 for side in heat)
        for s_i, side in enumerate(heat):
            team = _side_team(side, entrants, el, cat)
            for i, bib in enumerate(side):
                r = by_bib.get(str(bib))
                name = labels[h] if h < len(labels) else str(h + 1)
                cell = name if (s_i == 0 and i == 0) else ""
                row = (rider_row(r, group=cell, team=team or r.region) if r
                       else {"group": cell, "bib": bib, "team": team})
                if rows and i == 0:
                    # only the first side opens a block: the batteria is one
                    # unit and must not be split over two sheets
                    if s_i == 0:
                        row = group_start(row, strong=not solo)
                    elif not solo:
                        row = side_start(row)
                rows.append(row)
    return rows


def composition_rows(heats: list[list[str]], el: EntryList, cat: str = "",
                     labels: list[str] = ()) -> list[dict]:
    """One line per rider of a composed batteria, the number against the first.

    The velocità composes the next round on the sheet of the one just ridden:
    these are the rows of that block - the same shape as a start order, because
    that is what it is.
    """
    by_bib = R.riders_by_bib(el, cat)
    rows: list[dict] = []
    for h, heat in enumerate(heats):
        name = labels[h] if h < len(labels) else str(h + 1)
        for i, key in enumerate(heat):
            r = by_bib.get(str(key))
            cell = name if i == 0 else ""
            row = (rider_row(r, group=cell, team=r.region) if r
                   else {"group": cell, "bib": key})
            if rows and i == 0:
                # a hairline opens each batteria and nothing comes between the
                # riders of one: the same rules as the start order this block
                # is, and as the results above it (see `_heat_rows`)
                row = group_start(row)
            rows.append(row)
    return rows


def composition_tables(blocks, el: EntryList, cat: str = "", *,
                       font_size: int = 9, heat_label: str = "") -> list[Table]:
    """The batterie a results sheet composes, one table per block.

    A table of its own with a heading of its own - «Turno 1 - Recuperi»,
    «Semifinali» - instead of a band inside the results: the sheet carries two
    races and they are two tables, which is how the workbook has always had it.

    `blocks` are (title, heats) or (title, heats, labels), where the labels
    name the batterie when a number would say nothing (the finals).
    """
    # the same columns as the ordine di partenza it is, UCI ID included: after
    # the qualifying rounds this block *is* the published start order of the
    # velocità - the Partenti of that round goes out at comunicato -1
    cols = [Column("group", heat_label or label("heat_no"), "c",
                   8 if heat_label else 5),
            Column("bib", label("number"), "c", 7),
            Column("last_name", label("last_name"), "l", 20),
            Column("first_name", label("first_name"), "l", 15),
            Column("uci_id", label("uci_id"), "c", 20),
            Column("team", label("team_en"), "l", 17)]
    tables = []
    for block in blocks:
        title, heats = block[0], block[1]
        # a block of one batteria is named by its heading: numbering it "1" as
        # well says there is a second one somewhere
        labels = list(block[2]) if len(block) > 2 else ([""] if len(heats) == 1
                                                        else [])
        tables.append(Table(columns=list(cols),
                            rows=composition_rows(heats, el, cat, labels),
                            font_size=font_size, title=title))
    return tables


def race_startlist(state: RaceState, el: EntryList, comp: Competition, *,
                   heats: list[list[list[int]]] | None = None,
                   communique: str = "", font_size: int = 9,
                   decision: str | None = None,
                   show_bib: bool | None = None,
                   show_uci: bool | None = None,
                   heat_labels: list[str] = (),
                   subtitle: str = "", slug: str = "",
                   warned=(), decisions=(),
                   extra_tables: list[Table] = ()) -> Document:
    """Ordine di partenza / elenco partenti for one round_key of a race.

    `show_bib` keeps the dorsale column; left to None it is on everywhere but
    on a madison, which is read by coppia number - there the dorsale is a
    second number for the same rider, printed only when the jury asks for it.

    `show_uci` keeps the UCI ID. Left to None it follows the sheets of a race
    against the clock, which have always carried it - the squadre and the
    inseguimento individuale alike; the velocità asks for it too (see
    `ui.pages.races`).

    `subtitle` and `slug` are for the rounds that publish more than one start
    order: a keirin round files its own and that of its recuperi, and left to
    themselves the two would carry the same heading and overwrite each other in
    the comunicati folder.

    `warned` are the dorsali that carry an ammonizione into this fase
    (`race.warnings_carried`): they line up with a W next to their number.

    `decisions` are the ones the jury filed in this race: they print under the
    table, one tinted block each, above the sheet's own note.
    """
    title, round_key = _race_titles(comp, state)
    kind = state.fmt or R.round_format(comp, state.cat, state.event,
                                       state.round_key)
    grouped = R.is_team_format(kind)
    pairs = kind == R.MADISON
    show_bib = not pairs if show_bib is None else show_bib
    # the start order is read aloud at the track: batteria (or team) number,
    # dorsale, name, team. The team is the entrant - "EMILIA ROMAGNA A", not
    # the region the rider is registered in; the UCI ID only where the team
    # sheet needs it.
    finals = list(heat_labels) or final_heat_labels(state)
    # who starts alone is not a batteria: the column counts the starts, in the
    # order they are ridden. Only a timed round can be that - a bracket and a
    # finals round are ridden man against man whatever the qualifying did -
    # and the jury may have chosen it on the race itself (`race.solo_starts`)
    solo = R.solo_starts(comp, state)
    # an inseguimento individuale is ridden by riders, not by squadre: the
    # number on its start order is the atleta's own dorsale, called by that
    # name, and the sheet carries the UCI ID like every other sheet of a race
    # against the clock
    rider_timed = kind == R.TIMED and not grouped
    cols = []
    if heats:
        # on a finals round the column is not a batteria number: it is which
        # final that line rides. It says so even when the heats carry no label
        # of their own - a keirin final, a velocità printed from Stampa.
        final = bool(finals) or R.is_finals(state.round_key)
        cols.append(Column("group",
                           label("final") if final
                           else label("start_no") if solo
                           else label("heat_no"),
                           "c", 8 if final else 5))
    elif pairs:
        # the coppia number is the entrant: bold, and read before anything else
        cols.append(Column("group", label("pair"), "c", W_PAIR_NO, bold=True))
    elif grouped:
        cols.append(Column("group", "", "c", 5))
    if show_bib or not pairs:
        cols.append(Column("bib", label("bib") if pairs or rider_timed
                           else label("number"), "c", 7))
    cols += [Column("last_name", label("last_name"), "l", 20),
             Column("first_name", label("first_name"), "l", 15)]
    # a batteria di qualificazione carries it too, whatever it is ridden in:
    # that sheet is where the riders are admitted to the specialità, and it is
    # read against the licences like every other qualification.
    # So does every prova of an omnium: the elenco partenti of the scratch is
    # where the event is entered, and the classifiche parziali that start the
    # three prove after it carry the UCI ID as well - one sheet of the four
    # cannot be the one that drops it.
    omnium = comp.event(state.event).fmt == "omnium"
    default_uci = (grouped or rider_timed or omnium
                   or R.is_qualifying(state.round_key))
    if default_uci if show_uci is None else show_uci:
        cols.append(Column("uci_id", label("uci_id"), "c", 20))
    cols.append(Column("team", label("team_en"), "l", 17))

    rows = (_heat_rows(heats, el, state.entrants, finals, state.cat) if heats
            else _entrant_rows(state.entrants, el, state.cat))
    mark_warned(rows, warned)

    return Document(
        title=title,
        subtitle=subtitle or (f"{round_key} - {label('start_order')}" if round_key
                              else label("startlist")),
        # A finals sheet counts nothing: "2 finali · 4 squadre" is what the
        # table underneath already says, line by line. The distance stays.
        info=distance_line(0 if finals else len(state.entrants),
                            state.distance or 0,
                            state.n_laps or 0, state.n_sprint or 0,
                            unit=_count_unit(kind),
                            # "8 batterie" where every squadra starts by
                            # itself would be eight ways of saying "8 squadre"
                            heats=0 if finals or solo else len(heats or [])),
        communique=communique,
        tables=([Table(columns=cols, rows=rows, font_size=font_size)]
                + list(extra_tables)),
        # whatever stands in the race's Decisione / note field for this sheet -
        # the jury starts it from `Event.note()` and edits it there. An empty
        # string is an answer ("nothing on this sheet"); only None asks for
        # what the race carries.
        decision=state.decision if decision is None else decision,
        notes=decision_notes(decisions,
                             codes=comp.branding.decision_codes),
        slug=slug or f"{race_slug(state.cat, state.event, state.round_key)}"
                     f"_{DOC_STARTLIST}",
    )


def race_classification(state: RaceState, result: Result, el: EntryList,
                        comp: Competition, *, communique: str = "",
                        subtitle: str = "", font_size: int = 9,
                        decision: str | None = None, show_sprints: bool = True,
                        by_final: bool = False, champion: bool = False,
                        doc_kind: str = DOC_CLASSIFICATION,
                        show_club: bool = False,
                        show_time: bool = True,
                        show_bib: bool | None = None,
                        champion_label: str = "",
                        extra_tables: list[Table] = (),
                        slug: str = "",
                        qualify: int = 0,
                        show_count: bool = True,
                        show_rank: bool = True,
                        show_uci: bool = True,
                        show_club_code: bool = True,
                        show_laps: bool = True,
                        show_carried: bool = False,
                        lane_col: bool = False,
                        warned=(), decisions=(),
                        hide_dns: bool | None = None,
                        points_cols: list[tuple[str, str]] = ()) -> Document:
    """Risultati / classifica for one round_key, with the format's own columns.

    `by_final` prints the results of a finals round as the two finals were
    ridden - a band per final, 1° and 2° inside it - instead of as one ranking;
    `champion` names the winner of the event under the first line.

    `show_time` keeps the time column; a final classification is often filed
    without it, the times belonging to the risultati of each fase.

    `show_club` adds the rider's own club and its FCI code - the sheet says
    which region a team rode for, not which society each of them races with,
    and the jury needs both when it files the champions; `show_club_code` drops
    the code again where the sheet only wants the name.

    The last four are what an omnium asks for. `show_rank` drops the *Ris.*
    column from a sheet that is read as an ordine di partenza and not as a
    result; `lane_col` adds the untitled column that sends the riders to the
    balaustra and to the corda in turn; `show_carried` prints, in front of the
    volate, the points each rider took into the corsa a punti; `points_cols` are
    (data key, heading) pairs printed at the end - the points of each prova and
    their total.

    `warned` are the dorsali carrying an ammonizione: a W next to the number,
    as on the ordine di partenza (`race_startlist`).

    `hide_dns` drops the riders who never took the start from the table and
    names their numbers in a line under it instead: a classifica ranks who
    rode, and a column of DNS down its foot is a list of absences, not a
    result. Left to None it is what a prova di gruppo does - the standings of
    an omnium keep them, where the sigla is what says the rider is out of the
    event.

    `doc_kind` is what the sheet is filed as. A *risultati* belongs to the fase
    that was ridden and is named after it, like the ordine di partenza it
    answers (`AL_ins_squadre_qualificazioni_risultati`); a *classifica* covers
    the whole specialità and carries no fase.
    """
    title, round_key = _race_titles(comp, state)
    kind = state.fmt or R.round_format(comp, state.cat, state.event,
                                       state.round_key)
    if hide_dns is None:
        hide_dns = kind in R.BUNCH
    absent = [p.key for p in result.placings
              if hide_dns and p.status is Status.DNS]
    if absent:
        result = replace(result, placings=[p for p in result.placings
                                           if p.status is not Status.DNS])
    grouped = R.is_team_format(kind)
    # a team time trial is read like its own start order - number, rider, team -
    # with the result in front and the time at the end
    team_sheet = kind == R.TIMED_TEAM
    # a madison ranks coppie, and a coppia is its number: the column holds the
    # number both its riders wear, and the region moves to a column of its own
    pairs = kind == R.MADISON
    show_bib = not pairs if show_bib is None else show_bib

    cols = [Column("rank", label("rank"), "c", W_RANK)] if show_rank else []
    if lane_col:
        # no heading: it is not a result, it is where each of them lines up for
        # the prova that follows. Grey, and never bold - the sheet is read for
        # the names next to it.
        cols.append(Column("lane", "", "c", W_LANE, muted=True))
    if pairs:
        cols.append(Column("group", label("pair"), "c", W_PAIR_NO, bold=True))
    elif grouped and not team_sheet:
        cols.append(Column("group", label("team"), "l", W_GROUP))
    for c in COLS_RIDER_MIN:
        if c.key == "region":
            continue
        # the corsa a punti of an omnium wants the width for the volate: the
        # UCI ID is on the ordine di partenza, which is where it is read from
        if c.key == "uci_id" and not show_uci:
            continue
        # the dorsale is a second number for the same rider: on a madison sheet
        # it is printed only when the jury asks for it
        if c.key == "bib" and pairs and not show_bib:
            continue
        # the bib is read aloud as a number, as on the start order
        if team_sheet and c.key == "bib":
            c = Column("bib", label("number"), "c", 7)
        cols.append(c)
    if show_club:
        # the code must never be truncated - it is what the federation files
        # the result under
        if not any(c.key == "club" for c in cols):
            cols.append(Column("club", label("club"), "l", 30))
        if show_club_code:
            cols.append(Column("club_code", label("club_code"), "c", 13))
    if team_sheet:
        # region names run long ("FRIULI VENEZIA GIULIA"): give the team the
        # width of a group column, not that of a club
        cols.append(Column("group", label("team_en"), "l", W_GROUP))
    else:
        if pairs:
            # the coppia rides for a region, and the number alone does not say
            # which: it goes where the team goes on every other team sheet.
            # Nothing follows it - the society of each of the two riders is not
            # what a madison is read by, and on a sheet that also carries a
            # dozen sprint columns it is width taken from the names. The
            # classifica can still ask for it (`show_club`), which is the sheet
            # the societies are filed from.
            cols.append(Column("team", label("team"), "l", W_GROUP))
        else:
            tail = "club" if grouped else "region"
            if not any(c.key == tail for c in cols):
                cols.append(Column(tail, label(tail), "l", 24))
    # the batteria comes first and the placing inside it second: the sheet is
    # read one batteria at a time, and the number is printed once per batteria
    # (see below) - repeated on every line it read as a column of results
    if "heat_no" in result.columns:
        # a finals sheet has no batteria to number: each block carries what it
        # rides for - "5°-8°", "1°-2° posto" - so the column is named after it
        named = any(not str(p.data.get("heat_no", "")).strip().isdigit()
                    and str(p.data.get("heat_no", "")).strip()
                    for p in result.placings)
        cols.insert(0, Column("heat_no",
                              label("final") if named else label("heat_no"),
                              "c", 8 if named else 6))
    # a velocità is ridden twice and sometimes three times: one column per
    # prova, with the mark of whoever took it. The bella is printed as
    # *eventuale* because more often than not it is not ridden at all.
    for key in [c for c in result.columns if c.startswith("run_")]:
        cols.append(Column(key, label(key), "c", 9))

    n_sprint = int(state.n_sprint or 0)
    sprint_cols = show_sprints and kind in (R.POINTS, R.MADISON, R.TEMPO)
    if show_carried:
        # the corsa a punti of an omnium is not scored from zero: the volate are
        # added to what each rider brought into it, so that column comes first
        cols.append(Column("carried", label("points"), "c", W_TOTAL))
    if sprint_cols:
        cols += [Column(f"s{i}", str(i + 1), "c", W_SPRINT, tight=True)
                 for i in range(n_sprint)]
    if show_time and "time" in result.columns:
        # on a velocità the 200 m is the qualifying mark itself - the sheet is
        # read for the time, not for anything beside it, so it prints bold
        sprint_qual = (kind == R.TIMED
                       and comp.event(state.event).fmt in ("sprint", "keirin"))
        cols.append(Column("time", label("time"), "r", W_TIME,
                           bold=sprint_qual))
    if "total" in result.columns and not points_cols:
        if show_laps:
            cols.append(Column("laps", label("laps"), "c", W_LAPS))
        cols.append(Column("total", label("total"), "c", W_TOTAL, bold=True))
    # an omnium closes every prova on what it scored: one column per prova and,
    # once there is more than one of them, their total
    for key, head in points_cols:
        cols.append(Column(key, head, "c", W_POINTS, bold=key == "total"))
    if show_club:
        # two columns more on the same paper: everything that can give width
        # up does, so that the UCI ID and the society code - both fixed-length
        # and both useless truncated - print whole
        cols = [replace(c, w=CLUB_SHEET_W.get(c.key, c.w)) for c in cols]

    bib_of = R.pair_bib_map(state, el) if kind == R.MADISON else {}
    key_of = {v: k for k, v in bib_of.items()}

    # a qualifying round says on paper who goes through: the qualifiers carry
    # team and time in bold, and the cut is a heavier rule under the last of
    # them - the same line the jury draws by hand on the workbook
    # once the finals are ridden the sheet ranks the finals, not the qualifying
    # order: there is nothing left to qualify for and the cut comes off
    # an inseguimento individuale qualifies exactly as the one a squadre does:
    # four times go through, and the sheet that says so is the one that rules
    # the line under the fourth
    qualified = (R.is_pursuit(comp, state.event, kind)
                 and not (state.payload or {}).get("final_heats"))
    # a caller that knows the cut wins: the 200 m of a velocità qualifies as
    # many as the scheme says, which is not written in the round
    qualify = qualify or (
        comp.round_of(state.cat, state.event, state.round_key).qualify
        if qualified else None) or 0
    if doc_kind == DOC_RESULTS and R.heat_number(state.round_key) \
            and (state.payload or {}).get(R.ELIMINATE):
        # a batteria of an event the jury composed - a madison, an omnium: how
        # many go through is what the composition round decided, less whoever
        # did not start (3.2.157)
        qualify = R.qualify_count(state, (state.payload or {})[R.ELIMINATE])

    def cells(p) -> dict:
        return _result_cells(p, n_sprint, sprint_cols, result,
                             show_carried=show_carried, points_cols=points_cols)

    # the lane alternates down the classified, and only down them: whoever is
    # not in the standings does not line up for the next prova
    lanes = {}
    if lane_col:
        for i, p in enumerate(p for p in result.placings
                              if p.status in (Status.OK, Status.REL)):
            lanes[p.key] = label("lane_balustrade" if i % 2 == 0
                                 else "lane_rail")

    if team_sheet:
        rows = _team_rows(state, result, el, cells, qualify=qualify,
                          by_final=by_final, champion=champion)
        shown = [p for p in result.placings if not by_final or p.data.get("final")]
    else:
        # an inseguimento individuale rides its finals like the one a squadre:
        # the sheet is read final by final, 1° and 2° inside each
        rows = []
        shown = _final_order(state, result.placings) if by_final \
            else result.placings
        heat = final = None
        for n, p in enumerate(shown):
            entrant = key_of.get(p.key, p.key)
            riders = R.entrant_riders(entrant, el, state.cat)
            extra = cells(p)
            if lane_col:
                extra["lane"] = lanes.get(p.key, "")
            name = R.entrant_label(entrant, el)
            # the batteria number opens its own block and is not repeated on
            # the riders under it
            new_heat = "heat_no" in extra and extra["heat_no"] != heat
            if "heat_no" in extra:
                heat = extra["heat_no"] if new_heat else heat
                extra["heat_no"] = extra["heat_no"] if new_heat else ""
            if by_final and p.data.get("final") != final:
                final = p.data["final"]
                rows.append(_band(_final_band(final), rows, strong=True))
            # inside a final the two are 1° and 2°, whatever places that final
            # rides for: the overall placing belongs to the classification. A
            # final left a pari merito was not ridden and has no 1° and 2° in
            # it: it prints the place the two share, twice.
            rank = (position_label(p.data.get("heat_place"))
                    if by_final and p.status is Status.OK
                    and p.data.get("heat_place") else p.label)
            # the cut: a heavier rule under the last coppia that goes through,
            # the line the jury draws by hand across the workbook
            cut = bool(qualify) and n == qualify
            if not riders:
                row = {"rank": rank, "group": name, **extra}
                if pairs:
                    row |= {"group": _pair_number(entrant, el), "team": name}
                rows.append(group_start(row, strong=cut)
                            if rows and (grouped or cut or new_heat) else row)
                continue
            for i, r in enumerate(riders):
                first = i == 0
                row = rider_row(r, rank=rank if first else "",
                                group=name if first else "",
                                **(extra if first else {}))
                # the qualifiers carry the name and the time in bold, as on the
                # team sheet: the four that go through are what it is read for.
                # Both riders of a coppia, not only the one the result is on -
                # the entrant that qualifies is the two of them.
                if qualify and n < qualify:
                    row["_bold"] = {"last_name", "time"}
                if pairs:
                    # the number on both lines, the region once: the coppia is
                    # the entrant, and its two riders are one result
                    _pair_cells(row, entrant, el, i)
                    row["team"] = name if first else ""
                if first and rows and (grouped or cut or new_heat):
                    row = group_start(row, strong=cut)
                if not p.position and p.status.value == "OK":
                    row["_class"] = (row.get("_class", "") + " pending").strip()
                rows.append(row)
            # the champions close the first block of the sheet: no rule above
            # it - it belongs to the coppia it follows - and indented under the
            # names, as on the inseguimento
            # only over a first place: a 1°/2° left a pari merito assigns two
            # second places and no title, and the sheet must not name one
            if champion and p.position == 1 and p.status is Status.OK:
                rows.append(_band(champion_label or label("champion_team"),
                                  rows, cls="champion",
                                  rule=False, at="last_name"))

    mark_warned(rows, warned)

    return Document(
        title=title,
        subtitle=subtitle or (f"{round_key} - {label('risultati')}" if round_key
                              else label("classification")),
        # who did not take the start, where the table no longer says it: one
        # line under it, which is all a classifica owes an absence
        legend=msg("dns_note", bibs=", ".join(str(k) for k in absent))
        if absent else "",
        # A classifica carries no distance line at all: it closes the specialità,
        # and how long one fase of it was belongs on the risultati of that fase.
        # A finals sheet counts nothing either - the two finals and who rode
        # them are the table itself, not a head count above it.
        info=("" if doc_kind == DOC_CLASSIFICATION else
              distance_line(0 if by_final or not show_count else len(shown),
                             state.distance or 0,
                             state.n_laps or 0, n_sprint,
                             unit=_count_unit(kind))),
        communique=communique,
        tables=([Table(columns=cols, rows=rows, font_size=font_size)]
                + list(extra_tables)),
        # results and classifications go out blank: the standing note of the
        # event is the business of the ordine di partenza, and what the jury
        # writes here is kept per sheet (`payload["notes"]`)
        decision=(_sheet_note(state, doc_kind) if decision is None
                  else decision),
        notes=decision_notes(decisions,
                             codes=comp.branding.decision_codes),
        slug=(slug or
              (f"{race_slug(state.cat, state.event, state.round_key)}"
               f"_{DOC_RESULTS}" if doc_kind == DOC_RESULTS
               else f"{race_slug(state.cat, state.event)}_{DOC_CLASSIFICATION}")),
    )


def _band(text: str, rows: list[dict], *, cls: str = "band",
          strong: bool = False, rule: bool = True, at: str = "") -> dict:
    """A line of its own across the table: a final, or the champion.

    `rule` draws the usual line above it and starts a printing block; `at` is
    the column the band starts under, when it should not run the full width.
    """
    row = {"_banner": text, "_class": cls}
    if at:
        row["_banner_at"] = at
    return group_start(row, strong=strong) if rows and rule else row


def _final_band(final) -> str:
    """`FINALE 1°/2° POSTO` - the line that opens the block of one final."""
    return ui("final_band", name=T.final_label(final))


def _final_order(state: RaceState, placings: list) -> list:
    """The finalists in the order the finals were ridden, 3/4 first.

    The sheet follows the track, not the ranking: whoever did not reach the
    finals is not on it at all - the classification of the specialità is where
    they are, on their qualifying time.
    """
    order = [T.final_place(h, (state.payload or {}).get("qual_ranking") or [])
             for h in (state.payload or {}).get("final_heats") or []]
    return sorted((p for p in placings if p.data.get("final")),
                  key=lambda p: (order.index(p.data["final"])
                                 if p.data["final"] in order else 9,
                                 p.data.get("heat_place") or 0))


def _team_rows(state: RaceState, result: Result, el: EntryList, cells,
               *, qualify: int = 0, by_final: bool = False,
               champion: bool = False) -> list[dict]:
    """The block of every team, in the order the sheet ranks them.

    One block per team - the riders who rode, then whoever the reserve replaced,
    marked `(ris)` where the placing goes. The bands say what the numbers alone
    cannot: which final these two rode, where the qualification cut falls, and
    who is champion.
    """
    rows: list[dict] = []
    placings = _final_order(state, result.placings) if by_final \
        else result.placings
    final = None
    for n, p in enumerate(placings, start=1):
        extra = cells(p)
        if by_final and p.data.get("final") != final:
            final = p.data["final"]
            rows.append(_band(_final_band(final), rows, strong=True))
        # inside a final the two teams are 1° and 2°, whatever places the final
        # rides for: the overall placing is the business of the classification.
        # One left a pari merito was not ridden: it prints the shared place.
        rank = (position_label(p.data.get("heat_place"))
                if by_final and p.status is Status.OK
                and p.data.get("heat_place") else p.label)
        # the results of a final list who rode it; the classification of the
        # event owes a line to the rider a reserve replaced as well
        lineup = [(r, was) for r, was in R.team_lineup(state, p.key, el)
                  if not (was and by_final)]
        for i, (r, replaced) in enumerate(lineup):
            first = i == 0
            row = rider_row(r, rank=rank if first else "",
                            group=R.entrant_label(p.key, el) if first else "",
                            **(extra if first else {}))
            if replaced:
                # "(ris)" is not a placing: italic, and never in the bold the
                # first column carries
                row["rank"] = f"({label('reserve_short')})"
                row["_class"] = (row.get("_class", "") + " reserve").strip()
            if first and rows:
                row = group_start(row, strong=bool(qualify and n == qualify + 1))
            if first and n <= qualify:
                row["_bold"] = {"group", "time"}
            # the champions' name carries the sheet: bold even where there is
            # no qualification cut to bold anything else
            if first and champion and p.position == 1:
                row["_bold"] = set(row.get("_bold") or ()) | {"group"}
            rows.append(row)
        # a 1°/2° left a pari merito leaves the first place empty: two seconde
        # and no squadra campione, so no band under the first block either
        if champion and p.position == 1 and p.status is Status.OK:
            # no rule above it and indented under the names: it belongs to the
            # team it follows, and a line would cut it off from it
            rows.append(_band(label("champion_team"), rows, cls="champion",
                              rule=False, at="last_name"))
    return rows


def _result_cells(p, n_sprint: int, sprint_cols: bool, result: Result, *,
                  show_carried: bool = False,
                  points_cols: list[tuple[str, str]] = ()) -> dict:
    out: dict = {}
    d = p.data or {}
    if show_carried:
        out["carried"] = str(d.get("carried")) if d.get("carried") else ""
    if "heat_no" in result.columns:
        out["heat_no"] = d.get("heat_no", "")
    for key in result.columns:
        if key.startswith("run_"):
            out[key] = d.get(key, "")
    if sprint_cols:
        sprints = d.get("sprints") or []
        for i in range(n_sprint):
            v = sprints[i] if i < len(sprints) else 0
            out[f"s{i}"] = str(v) if v else ""
    if "time" in result.columns:
        # a squalificata carries no time on paper, whatever the watch said:
        # the ride does not stand, and a time printed next to DSQ reads as a
        # result. The race keeps it - the jury typed it, and a decision can be
        # withdrawn - it just never prints.
        out["time"] = ("" if p.status is Status.DSQ
                       else format_time(d.get("time")))
    if "total" in result.columns:
        laps = d.get("laps") or 0
        out["laps"] = f"{laps:+d}" if laps else ""
        out["total"] = str(d.get("total")) if d.get("total") else ""
    for key, _head in points_cols:
        # a prova a rider did not finish scores nothing, and a zero printed in
        # the column reads as a result: the cell stays empty
        out[key] = str(d.get(key)) if d.get(key) else ""
    return out


def decisions_register(decisions: list, comp: Competition, *,
                       communique: str = "", font_size: int = 8) -> Document:
    """The jury's own log, printable: every decision in the order it was taken.

    Not a comunicato and not meant to become one - what goes out to the teams
    is the decision itself, written on the sheet of the race it belongs to.
    This is the sheet the panel signs off at the end of the day and the one the
    federation asks for afterwards, so it is read in the order things happened
    and carries the text in full.
    """
    cols = [Column("n", label("register_col_n"), "c", 4),
            Column("day", label("register_col_day"), "c", 3),
            Column("cat", label("cat"), "c", 5),
            Column("event", label("event"), "l", 14),
            Column("round_key", label("round"), "l", 14),
            Column("bibs", ui("bibs"), "c", 7),
            Column("code", label("penalty_col"), "c", 6),
            Column("text", label("decision"), "l", 47, wrap=True)]
    rows = []
    last_day = None
    for d in decisions:
        row = {"n": d.n, "day": d.day or "", "cat": d.cat,
               "event": comp.event(d.event).short if d.event else "",
               "round_key": d.round_key, "bibs": d.bibs,
               # the compact code, not the bare letter: the article a decision
               # was taken under is what makes the register answerable
               "code": d.code, "text": d.text}
        if last_day is not None and d.day != last_day:
            row = group_start(row, strong=True)
        last_day = d.day
        rows.append(row)
    return Document(
        title=f"{comp.name} - {label('decisions_title')}",
        info=msg("count_decisions", n=len(rows)),
        communique=communique,
        tables=[Table(columns=cols, rows=zebra(rows), font_size=font_size)],
        slug=label("decisions_slug"),
    )


def comunicati_register(rows: list[dict], comp: Competition, *,
                        communique: str = "", font_size: int = 8) -> Document:
    """The register itself, printable - the 'Lista Comunicati' replacement."""
    cols = [Column("n", label("register_col_n"), "c", 5),
            Column("day", label("register_col_day"), "c", 4),
            Column("cat", label("cat"), "c", 6),
            Column("event", label("event"), "l", 20),
            Column("round_key", label("round"), "l", 30),
            Column("doc", label("document"), "l", 14),
            Column("issued", label("issued"), "c", 8)]
    out = []
    last_day = None
    for r in rows:
        row = {"n": r["label"], "day": r["day"] or "", "cat": r["cat"],
               "event": comp.event(r["event"]).short,
               "round_key": r["round_key"], "doc": label(r["doc"]),
               "issued": "✓" if r["issued"] else ""}
        if last_day is not None and r["day"] != last_day:
            row = group_start(row, strong=True)
        last_day = r["day"]
        out.append(row)
    return Document(
        title=f"{comp.name} - {label('register_title')}",
        info=msg("count_documents", n=len(rows),
                 issued=sum(1 for r in rows if r["issued"])),
        communique=communique,
        tables=[Table(columns=cols, rows=zebra(out), font_size=font_size)],
        slug=label("register_slug"),
    )


# ── how many ride what ──────────────────────────────────────────────────────

#: What a specialità column is worth when it is headed by the short name
#: ("Ins. Individuale") instead of the UCI sigla ("IP"). The cells below it are
#: still one or two characters: the width goes to the header, which is the only
#: thing that has to fit, and the legend under the table is dropped - the head
#: of the column already says what it says.
EVENT_COL_W_SHORT = 13


def speciality_table(el: EntryList, comp: Competition, *, communique: str = "",
                     font_size: int = 9, short_headers: bool = False) -> Document:
    """The tabella specialità: each categoria across the programme.

    The sheet the jury reads out at the briefing - how far the verifica has
    got, and how many riders each categoria fields in each specialità. The
    numbers are `core.recap`'s, the same ones the Verifica page shows.

    A categoria that does not contest a specialità prints blank: a zero there
    would read as "nobody entered", which is a different thing entirely.
    """
    rows, total = RC.speciality_table(el, comp)
    events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]
    heads = comp.event_headers(events, abbr=not short_headers)

    cols = [Column("cat", label("cat"), "c", 6),
            Column("entries", ui("athletes"), "c", 7),
            Column("checked_in", label("checked_in"), "c", 8),
            Column("not_starting", label("not_starting"), "c", 6)]
    cols += [Column(f"ev_{s}", heads[s], "c",
                    EVENT_COL_W_SHORT if short_headers else 6)
             for s in events]

    out = []
    for row in [*rows, total]:
        last = row is total
        out.append({
            "cat": ui("total") if last else row.cat,
            "entries": row.entries,
            "checked_in": f"{row.checked_in}/{row.entries}",
            "not_starting": row.not_starting or "",
            **{f"ev_{s}": ("" if n is RC.NOT_CONTESTED else n)
               for s, n in row.per_event.items()},
        })
        # the totals line is read as a total, not as a fifth categoria
        if last:
            group_start(out[-1], strong=True)

    return Document(
        title=label("speciality_table"),
        subtitle=comp.name,
        info=msg("count_entered_starters", entered=total.entries
                 + total.not_starting, starters=total.entries),
        legend="" if short_headers else msg("event_key", list="  ·  ".join(
            f"{heads[s]} = {comp.event(s).short}" for s in events)),
        communique=communique,
        tables=[Table(columns=cols, rows=zebra(out), font_size=font_size)],
        slug=label("speciality_table_slug"),
    )


# ── what one squadra is riding ──────────────────────────────────────────────

def team_recap(el: EntryList, comp: Competition, team: str, *,
               group: str = RC.DEFAULT_GROUP, heats: dict | None = None,
               include_np: bool = True, font_size: int = 9,
               communique: str = "", short_headers: bool = False) -> Document:
    """One squadra's riders and what each of them rides, on one grid.

    The sheet a team manager asks for and the jury used to answer by hand:
    every rider of the rappresentativa, with a column per specialità and a
    mark where they are entered - `X`, or the letter of the coppia / squadra
    where there are accoppiamenti, `R` for a riserva. Where the jury has
    already composed the batteria, its number follows the mark.

    One table, every categoria in it, in the order the competition lists them:
    a manager reads their whole squadra down one page instead of hunting the
    same rider through four tables.
    """
    heats = heats or {}
    order = {c: i for i, c in enumerate(comp.cat_order())}
    riders = [r for cat in comp.cat_order()
              for r in RC.riders_of(el, team, cat, group,
                                    include_np=include_np)]
    riders.sort(key=lambda r: (order.get(r.cat, 99), r.bib is None,
                               r.bib or 0, r.last_name))

    # only what this squadra actually rides: the columns of a specialità
    # nobody here is entered in would print empty the whole way down
    events = [s for s in comp.event_order()
              if s != EVENT_ENTRY_LIST and any(s in r.events for r in riders)]
    heads = comp.event_headers(events, abbr=not short_headers)

    rows = []
    for r in riders:
        marks = {f"ev_{s}": _entry_mark(r, s, heats) for s in events}
        rows.append(rider_row(r, **marks))
    entries = sum(1 for r in riders for s in events if s in r.events)

    tables = [Table(columns=_recap_cols(group, events, heads,
                                        short_headers=short_headers),
                    rows=zebra(rows), font_size=font_size)] if rows else []
    return Document(
        title=f"{team} - {label('team_recap')}",
        info=msg("count_recap", riders=len(riders), entries=entries),
        # headed by the short name, the columns already say what the sigle
        # would have to be looked up for: only the key to the marks is left
        legend=msg("recap_marks") if short_headers else msg(
            "recap_legend", marks=msg("recap_marks"),
            list="  ·  ".join(f"{heads[s]} = {comp.event(s).short}"
                              for s in events)),
        communique=communique,
        tables=tables,
        slug=f"{slugify(team)}_{label('team_recap_slug')}",
    )


def _entry_mark(rider: Rider, event: str, heats: dict) -> str:
    """`X`, `A`, `AR`, `R` - and the batteria after it once composed."""
    entry = rider.events.get(event)
    if entry is None:
        return ""
    flag = (entry.flag or "").strip().upper() or "X"
    placed = heats.get((rider.cat, event, rider.key))
    return f"{flag} {placed[1]}" if placed else flag


# ── il medagliere ───────────────────────────────────────────────────────────

def medal_table(found: M.Survey, comp: Competition, *, detail: bool = True,
                communique: str = "", font_size: int = 9) -> Document:
    """The medagliere, printable: one line per squadra, best first.

    The sheet asked for at the end of a championship, and the one that gets
    read out. It carries what it is counted from with it:

    * the podiums the count is made of, as a second table, so a line can be
      checked against the comunicati without opening the app;
    * the specialità that are not concluded, named under it - a table that
      looks short says why on its own paper.

    Nothing is counted here: `found` is one reading of the competition
    (`core.medals.survey`), the same one the Statistiche page shows.
    """
    table = M.medal_table(found.places)
    cols = [Column("rank", label("rank"), "c", 6),
            Column("team", label("team"), "l", 40),
            Column("gold", label("medal_gold"), "c", 9),
            Column("silver", label("medal_silver"), "c", 9),
            Column("bronze", label("medal_bronze"), "c", 9),
            Column("total", label("total"), "c", 9, bold=True)]
    rows = [{"rank": position_label(pos), "team": t.team, "gold": t.gold or "",
             "silver": t.silver or "", "bronze": t.bronze or "",
             "total": t.total}
            for pos, t in M.ranked(table)]

    # the first table is the sheet: it is not headed again under its own title.
    # Only the podiums are announced, because they are a second thing.
    tables = [Table(columns=cols, rows=zebra(rows), font_size=font_size)]
    if detail and found.places:
        tables.append(_podium_table(found, comp, font_size))

    return Document(
        title=label("medal_table_title"),
        subtitle=comp.name,
        info=msg("count_medals", events=found.counted,
                 concluded=msg(plural(found.counted, "medals_concluded_one",
                                      "medals_concluded_many")),
                 podiums=len(found.places),
                 podium=msg(plural(len(found.places), "medals_podium_one",
                                   "medals_podium_many")),
                 teams=len(table),
                 team=msg(plural(len(table), "medals_team_one",
                                 "medals_team_many"))),
        legend=msg("medal_counting_note") if any(
            not p.complete for p in found.places) else "",
        communique=communique,
        tables=tables,
        notes=_open_note(found, comp),
        slug=label("medal_table_slug"),
    )


def _podium_table(found: M.Survey, comp: Competition, font_size: int) -> Table:
    """Every podium place the count is made of, in programme order."""
    cols = [Column("cat", label("cat"), "c", 6),
            Column("event", label("event"), "l", 20),
            Column("position", ui("stats_position"), "c", 6),
            Column("team", label("team"), "l", 22),
            Column("who", ui("stats_who"), "l", 34, wrap=True)]
    rows = []
    last = None
    for p in found.places:
        row = {"cat": p.cat,
               # the specialità, and where it is not over yet, that it is not:
               # the fase a place came from says nothing a medagliere is read
               # for - a specialità is counted once, on its final
               "event": (comp.event(p.event).short if p.complete else
                         f"{comp.event(p.event).short} "
                         f"({ui('stats_provisional')})"),
               "position": position_label(p.position),
               "team": ", ".join(p.teams),
               # the names, and the dorsale only where there are none to print:
               # a quartetto whose riders have left the entry list still rides
               # under something
               "who": ", ".join(p.names) or p.label}
        if last is not None and (p.cat, p.event) != last:
            row = group_start(row)
        last = (p.cat, p.event)
        rows.append(row)
    return Table(columns=cols, rows=zebra(rows), font_size=font_size,
                 title=label("podium_detail_title"))


def _open_note(found: M.Survey, comp: Competition) -> list[Note]:
    """What the medagliere is not counting, as the block under the table."""
    if not found.open_events:
        return []
    return [Note(text=msg("medal_open_events", list="  ·  ".join(
                     f"{cat} {comp.event(event).short}"
                     for cat, event, _any in found.open_events)))]


#: What a rider is identified by on their squadra's own sheet, per grouping:
#: the squadra is the title, so the column that names it would repeat it on
#: every line - each grouping prints the *other* one instead.
_RECAP_TAIL = {RC.BY_REGION: "club", RC.BY_CLUB: "region",
               RC.BY_PROVINCE: "club", RC.BY_NATION: "club"}


def _recap_cols(group: str, events: list[str], heads: dict[str, str], *,
                short_headers: bool = False) -> list[Column]:
    tail = _RECAP_TAIL.get(group, "club")
    # the marks are two characters wide at most, so the specialità columns take
    # the least the header needs and leave the width to the società, which is
    # the one value that stops being readable the moment it is cut
    return [Column("bib", label("bib"), "c", 6),
            Column("last_name", label("last_name"), "l", 18),
            Column("first_name", label("first_name"), "l", 14),
            Column("cat", label("cat"), "c", 5),
            Column(tail, label(tail), "l", 24),
            *[Column(f"ev_{s}", heads[s], "c",
                     EVENT_COL_W_SHORT if short_headers else 4.5)
              for s in events]]
