"""Writing `programme.yaml` back out, and what a comunicato carries.

The load-bearing test is the first one: the championship that starts tomorrow
is described by a file written by hand, and the Programma page is only usable
if reading that file and writing it again gives back the same competition.
Everything else in this module rests on it.
"""

from __future__ import annotations

import dataclasses

import pytest

from core import communiques as C
from core import programme as P
from conftest import programme_path
from core.checks import ERROR
from core.config import Round, Sheet, load_competition


@pytest.fixture
def prog():
    """A copy of the real programme that this module may edit.

    The `comp` fixture is session-scoped and shared: half the tests here move a
    comunicato or delete one, and a mutation that leaked would make the next
    test lie. Read fresh, once per test.
    """
    return load_competition(programme_path())


def _same(a, b) -> bool:
    """Two competitions, compared on everything but where they were read from."""
    def norm(c):
        d = dataclasses.asdict(c)
        d.pop("path")
        return d
    return norm(a) == norm(b)


def _round_trip(comp, tmp_path):
    p = tmp_path / "programme.yaml"
    p.write_text(P.dump(comp), encoding="utf-8")
    return load_competition(p)


def _com(comp, cat, event, round_key, doc):
    """The register entry that files a sheet, found by what it is.

    Never by its number: the numbers move whenever a race is added to the
    programme or taken out of it, and a test that named one would fail on a
    change that has nothing to do with what it is checking.
    """
    return next(c for c in comp.communiques
                if (c.cat, c.event, c.round_key, c.doc)
                == (cat, event, round_key, doc))


# ── the guarantee ───────────────────────────────────────────────────────────

def test_the_real_programme_survives_being_written_out(comp, tmp_path):
    """Read it, write it, read it again: the same competition.

    This is the whole contract of the emitter. The file it is checked against
    is the one the championship is actually run from - 4 categorie, 7
    specialità, 30 gare in programma e 140 comunicati.
    """
    assert _same(comp, _round_trip(comp, tmp_path))


def test_writing_it_twice_gives_the_same_bytes(comp, tmp_path):
    """The layout never moves, or a diff is unreadable and a copy-paste is a
    guess: that is the reason for an emitter of our own."""
    once = P.dump(comp)
    assert once == P.dump(_round_trip(comp, tmp_path))


def test_the_running_order_is_not_rearranged(comp, tmp_path):
    """The order of `programme:` is a decision, not something to sort.

    It is what `events_for` reads and what a batch printed per giornata comes
    out in: writing the file back must not quietly put it in another order.
    """
    back = _round_trip(comp, tmp_path)
    assert [(i.cat, i.event, i.day) for i in back.programme] \
        == [(i.cat, i.event, i.day) for i in comp.programme]


def test_a_derived_value_is_not_frozen_into_the_file(prog, tmp_path):
    """A round that says nothing about its laps keeps taking them from the track.

    Writing the computed value back would nail it to this velodrome: the same
    programme run on a 250 would then be silently wrong. Nothing that was not
    written is written back.
    """
    item = next(i for i in prog.programme if i.event == "ins_squadre")
    item.rounds.append(Round(key="Prova", distance=2))       # giri: dalla pista
    assert prog.distances(item.cat, item.event, "Prova") == (2.0, 6.0, 0)

    line = next(ln for ln in P.dump(prog).splitlines() if "key: Prova" in ln)
    assert "laps:" not in line and "sprints:" not in line
    assert _round_trip(prog, tmp_path).round_of(
        item.cat, item.event, "Prova").laps is None


def test_what_the_format_runs_is_written_down_and_read_back(prog, tmp_path):
    """The builder states it; before it existed the app had to guess.

    Whether a velocità qualifies twelve or eight, whether it rides its 5°-8°
    final, whether a keirin rides its second one: `core.race` used to infer all
    three from the round list and from the documents a round files, and the
    jury re-decided them inside the race. Stated in the programme they have to
    survive a save - `False` included, which is the one the writer has to
    special-case.
    """
    item = next(i for i in prog.programme if i.event == "velocita")
    item.scheme, item.final_5_8, item.final_b = "8", False, True
    item.rounds[0] = dataclasses.replace(item.rounds[0], start="14:30")

    back = _round_trip(prog, tmp_path)
    got = next(i for i in back.programme
               if (i.cat, i.event) == (item.cat, item.event))
    assert (got.scheme, got.final_5_8, got.final_b) == ("8", False, True)
    assert got.rounds[0].start == "14:30"


def test_a_format_option_nobody_stated_stays_unstated(prog, tmp_path):
    """`None` is not `False`: it is what lets an old file behave as it always did.

    Every programme written before these fields existed says nothing about
    them, and the resolvers in `core.race` fall back on what they infer. A
    writer that turned "unstated" into "not ridden" would quietly cancel the
    keirin's second final at four championships.
    """
    assert all(i.final_5_8 is None and i.final_b is None and not i.scheme
               for i in prog.programme)
    assert "final_5_8" not in P.dump(prog)
    back = _round_trip(prog, tmp_path)
    assert all(i.final_5_8 is None and i.final_b is None
               for i in back.programme)


def test_the_freeze_and_the_pinned_numbers_survive_a_save(prog, tmp_path):
    """Both say *do not move this*, and a save that lost them would move it."""
    prog.numbering_frozen = True
    prog.communiques[0].pinned = True

    back = _round_trip(prog, tmp_path)
    assert back.numbering_frozen is True
    assert back.communiques[0].pinned is True
    # and neither is written by a competition that never asked for them
    assert "numbering_frozen" not in P.dump(load_competition(programme_path()))


# ── a comunicato that carries more than one document ────────────────────────

def test_a_comunicato_carries_one_document_by_default(comp):
    """Every entry of a register transcribed before `with:` existed still says
    exactly what it said."""
    c = next(c for c in comp.communiques if c.n == 7)
    assert [s.key for s in c.sheets] == [("AL", "ins_squadre",
                                          "Qualificazioni", "partenti")]


def test_a_second_sheet_rides_in_the_same_fase(prog, tmp_path):
    """`with: [partenti_recuperi]` is another sheet of the *same* race.

    That is what a velocità has always printed: the risultati of the turno and,
    under them, the ordine di partenza of the recuperi it just composed.
    """
    c = _com(prog, "AL", "velocita", "Turno 1", "risultati")
    c.extra = [Sheet(doc="partenti_recuperi")]
    assert [s.key for s in c.sheets] == [
        ("AL", "velocita", "Turno 1", "risultati"),
        ("AL", "velocita", "Turno 1", "partenti_recuperi")]
    back = _round_trip(prog, tmp_path)
    assert _same(prog, back)
    assert C.number_for(back, "AL", "velocita", "Turno 1",
                        "partenti_recuperi") == str(c.n)


def test_a_sheet_can_say_it_belongs_to_no_fase(prog, tmp_path):
    """An explicit `round: ""` is a statement, not a missing value.

    The classifica closes the specialità and belongs to no fase; the recuperi
    belong to the one above them. Both are written with `with:`, and the two
    must not collapse into each other.
    """
    c = next(c for c in prog.communiques if c.n == 25)
    c.extra = [Sheet(round_key="", doc="classifica")]
    assert [s.key for s in c.sheets] == [
        ("AL", "vel_squadre", "Finali", "risultati"),
        ("AL", "vel_squadre", "", "classifica")]
    back = _round_trip(prog, tmp_path)
    assert _same(prog, back)
    assert C.number_for(back, "AL", "vel_squadre", "", "classifica") == "25"


def test_two_rows_with_one_number_is_still_a_mistake(prog):
    """`with:` is how a number carries two sheets; two rows is a typo."""
    dup = dataclasses.replace(
        next(c for c in prog.communiques if c.n == 7), title="altro")
    prog.communiques.append(dup)
    found = P.issues(prog)
    assert any(i.code == "communique_dup" and i.level == ERROR for i in found)


# ── what the page needs to know ─────────────────────────────────────────────

def test_a_day_offers_only_the_sheets_its_format_can_file(comp):
    """A velocità rides a 5°-8° final and an omnium does not."""
    assert "risultati_5-8" in P.docs_available(comp, "velocita")
    assert "risultati_5-8" not in P.docs_available(comp, "omnium")
    assert "classifica_parziale" in P.docs_available(comp, "omnium")
    assert "partenti_recuperi" in P.docs_available(comp, "keirin")
    # every event files these three, whatever it is
    for event in comp.events:
        got = P.docs_available(comp, event)
        assert {"partenti", "risultati", "classifica"} <= set(got)


def test_the_days_come_from_the_dates(comp):
    """Four dates are four tabs, even before anything is scheduled on the last."""
    assert P.days_of(comp) == [1, 2, 3, 4]
    assert P.date_of(comp, 1) == "2026-08-04"


def test_a_one_day_race_has_one_day():
    """The page has to work for the next competition, not only for this one."""
    small = P.blank("Trofeo di prova", days=1)
    assert P.days_of(small) == [1]
    P.add_category(small, "AL", "UOMINI ALLIEVI", "M")
    P.add_event(small, "scratch", "SCRATCH", "group")
    P.add_item(small, "AL", "scratch", 1, ["Finale"])
    assert small.events_for("AL") == ["scratch"]
    assert [r.key for r in small.rounds("AL", "scratch")] == ["Finale"]


def test_a_blank_programme_round_trips(tmp_path):
    """Starting a championship from nothing must not need a file to copy."""
    small = P.blank("Trofeo di prova", days=2)
    P.add_category(small, "AL", "UOMINI ALLIEVI", "M")
    P.add_event(small, "scratch", "SCRATCH", "group")
    P.add_item(small, "AL", "scratch", 1, ["Finale"])
    assert _same(small, _round_trip(small, tmp_path))


def test_renumbering_follows_the_order_of_the_list(comp):
    """The order the comunicati are in *is* the order they go out in."""
    day1 = [c for c in comp.communiques if c.day == 1]
    moved = P.moved(day1, 0, 1)
    assert [c.title for c in moved][:2] == [day1[1].title, day1[0].title]
    numbered = P.renumber(moved, start=1)
    assert [c.n for c in numbered] == list(range(1, len(day1) + 1))
    assert numbered[0].title == day1[1].title


def test_a_proposed_register_leaves_nothing_out(comp):
    """`plan_day` is a proposal: what it gets right is that nothing is missing."""
    planned = P.plan_day(comp, 1, start=1)
    scheduled = {(i.cat, i.event, r.key, doc)
                 for i in comp.programme if i.day == 1
                 for r in i.rounds for doc in r.docs}
    proposed = {(c.cat, c.event, c.round_key, c.doc) for c in planned}
    # the classifica of a specialità is filed with no fase, so it is compared
    # on the other three
    assert {s[:2] for s in scheduled} == {p[:2] for p in proposed}
    assert len(planned) == len(scheduled)
    assert [c.n for c in planned] == list(range(1, len(planned) + 1))


def test_the_register_is_a_table_of_documents(prog):
    """One row per document: a comunicato with two sheets is two rows, one number.

    That is what makes the multi-document case editable at all - the jury sees
    the number repeated and knows the two print together.
    """
    c = _com(prog, "AL", "velocita", "Turno 1", "risultati")
    c.extra = [Sheet(doc="partenti_recuperi")]
    rows = P.rows_from_specs(prog.communiques)
    both = [r for r in rows if r["n"] == c.n]
    assert [r["doc"] for r in both] == ["risultati", "partenti_recuperi"]
    # the fase is filled in on both rows: the table shows what actually prints
    assert {r["round"] for r in both} == {"Turno 1"}
    # the title belongs to the sheet, not to each of its documents
    assert both[1]["title"] == ""


def test_the_table_reads_back_into_the_same_register(prog):
    """Table -> model -> table is the page's own round trip."""
    _com(prog, "AL", "velocita", "Turno 1", "risultati").extra = [
        Sheet(doc="partenti_recuperi")]
    _com(prog, "AL", "vel_squadre", "Finali", "risultati").extra = [
        Sheet(round_key="", doc="classifica")]
    rows = P.rows_from_specs(prog.communiques)
    back = P.specs_from_rows(rows)
    assert P.rows_from_specs(back) == rows
    assert [(c.n, [s.key for s in c.sheets]) for c in back] \
        == [(c.n, [s.key for s in c.sheets])
            for c in sorted(prog.communiques, key=lambda c: c.n)]


def test_two_documents_become_one_comunicato_when_the_number_repeats(prog):
    """The jury types the same number on the next row: that is the whole gesture."""
    rows = [
        {"n": 95, "day": 3, "cat": "AL", "event": "velocita",
         "round": "Turno 1", "doc": "risultati", "title": "AL Velocità T1"},
        {"n": 95, "day": 3, "cat": "AL", "event": "velocita",
         "round": "Turno 1", "doc": "partenti_recuperi", "title": ""},
        {"n": 96, "day": 3, "cat": "AL", "event": "velocita",
         "round": "", "doc": "classifica", "title": "AL Velocità Classifica"},
    ]
    specs = P.specs_from_rows(rows)
    assert [c.n for c in specs] == [95, 96]
    assert [s.doc for s in specs[0].sheets] == ["risultati",
                                                "partenti_recuperi"]
    # the second document said nothing about its fase: it rides in the first's
    assert specs[0].extra[0].round_key is None
    assert specs[0].sheets[1].round_key == "Turno 1"


# ── the checks that only matter while it is being edited ────────────────────

def test_moving_a_number_that_is_already_on_paper_is_an_error(prog):
    """A comunicato in the jury's hands and the register cannot disagree."""
    from core.communiques import Issued

    issued = [Issued(n=7, title="AL Inseguimento Squadre - Partenti",
                     cat="AL", event="ins_squadre",
                     round_key="Qualificazioni", doc="partenti")]
    assert not [i for i in P.issues(prog, issued)
                if i.code == "communique_moved"]
    # the same number now names another sheet
    spec = next(c for c in prog.communiques if c.n == 7)
    spec.cat, spec.event = "DA", "vel_squadre"
    moved = [i for i in P.issues(prog, issued) if i.code == "communique_moved"]
    assert moved and moved[0].level == ERROR


def test_a_gap_in_the_numbering_is_worth_saying(prog):
    """Numbers run continuously: a hole is usually a row deleted by mistake."""
    prog.communiques = [c for c in prog.communiques if c.n != 50]
    assert any(i.code == "communique_gap" for i in P.issues(prog))


# ── the scalars, where a wrong quote silently changes a value ───────────────

@pytest.mark.parametrize("value, written", [
    ("Qualificazioni", "Qualificazioni"),
    ("Dors.", "Dors."),
    ("Velodromo delle Cascine, Firenze", '"Velodromo delle Cascine, Firenze"'),
    ("#0a5688", '"#0a5688"'),          # a plain # opens a comment
    ("2026-08-04", '"2026-08-04"'),    # unquoted YAML reads a date
    ("177848", '"177848"'),            # ... and a number
    ("Squadra\n(Regione)", '"Squadra\\n(Regione)"'),
    ("no", '"no"'),                    # unquoted YAML reads a boolean
    ("", '""'),
    (3, "3"),
    (0.5, "0.5"),
    (3.0, "3"),
    (True, "true"),
    (None, "null"),
])
def test_a_value_is_quoted_exactly_when_it_has_to_be(value, written):
    assert P.scalar(value) == written


# ── numbering: the register follows the running order ───────────────────────
#
# A comunicato number is not a property of a document, it is *when* the
# document goes out. While the programme is still being built the two are kept
# in step; the moment a sheet is in somebody's hands, they are not.

def test_the_day_opens_with_its_start_lists(comp):
    """Every ordine di partenza of the first fasi, before any risultato."""
    order = C.sheet_order(comp)
    day1 = [s for s in order
            if (comp.scheduled(s.cat, s.event) or comp.programme[0]).day == 1
            and s.event != "entry_list"]
    docs = [s.doc for s in day1]
    first_result = docs.index("risultati")
    assert set(docs[:first_result]) == {"partenti"}


def test_a_start_list_never_overtakes_the_results_that_compose_it(comp):
    """The finali cannot be published before the semifinali they come out of.

    This is the whole reason the sort counts how deep a fase is instead of
    simply putting every startlist first.
    """
    order = C.sheet_order(comp)
    at = {(s.cat, s.event, s.round_key, s.doc): i for i, s in enumerate(order)}
    for item in comp.programme:
        for before, after in zip(item.rounds, item.rounds[1:]):
            r = at.get((item.cat, item.event, before.key, "risultati"))
            p = at.get((item.cat, item.event, after.key, "partenti"))
            if r is not None and p is not None:
                assert r < p, f"{item.cat} {item.event}: {after.key} before {before.key}"


def test_the_elenchi_iscritti_open_the_competition(comp):
    """They are in no day's running order, and they are comunicato 1 to 4."""
    numbered = C.autonumber(comp, add_missing=False)
    first = numbered[:len(comp.cat_order())]
    assert all(c.event == "entry_list" for c in first)
    assert [c.n for c in first] == [1, 2, 3, 4]


def test_renumbering_the_real_register_loses_nothing(comp):
    """140 comunicati in, 140 out, and no number handed out twice.

    The register is the jury's own record: a numbering pass that quietly
    dropped a line - a document the rounds do not declare, a fase spelled two
    ways - would be worse than one that never ran.
    """
    out = C.autonumber(comp, add_missing=False)
    assert len(out) == len(comp.communiques)
    assert {c.sheets[0].key for c in out} == {c.sheets[0].key
                                              for c in comp.communiques}
    assert len({c.n for c in out}) == len(out)


def test_a_number_already_on_paper_never_moves(prog):
    """The sheet is in somebody's hands: this is the one thing that cannot change."""
    issued_spec = sorted(prog.communiques, key=lambda c: c.n)[40]
    issued = [C.Issued(n=issued_spec.n, cat=issued_spec.cat,
                       event=issued_spec.event,
                       round_key=issued_spec.round_key, doc=issued_spec.doc)]

    out = C.autonumber(prog, issued, add_missing=False)
    same = next(c for c in out if c.sheets[0].key == issued_spec.sheets[0].key)
    assert same.n == issued_spec.n


def test_a_number_the_jury_typed_never_moves_either(prog):
    """`pinned` is the jury saying it: somebody is expecting that number."""
    spec = sorted(prog.communiques, key=lambda c: c.n)[60]
    spec.pinned = True
    spec.n = 999

    out = C.autonumber(prog, add_missing=False)
    kept = next(c for c in out if c.sheets[0].key == spec.sheets[0].key)
    assert kept.n == 999
    # ... and nothing else was given 999 on the way past it
    assert [c.n for c in out].count(999) == 1


def test_the_numbers_flow_around_the_ones_that_are_held(prog):
    """What is free is redealt; what is fixed stays, and nothing collides."""
    held = sorted(prog.communiques, key=lambda c: c.n)[10]
    held.pinned, held.n = True, 3

    out = C.autonumber(prog, add_missing=False)
    assert len({c.n for c in out}) == len(out)
    assert next(c for c in out
                if c.sheets[0].key == held.sheets[0].key).n == 3


def test_moving_a_race_moves_its_comunicati(prog):
    """The point of the whole thing: the register is a view of the order."""
    def numbers():
        return {c.sheets[0].key: c.n
                for c in C.autonumber(prog, add_missing=False)}

    def opening_sheet(item):
        """The first ordine di partenza that race files - not its setup fase."""
        rnd = next(r for r in item.rounds if "partenti" in (r.docs or []))
        return (item.cat, item.event, rnd.key, "partenti")

    day1 = [i for i in prog.programme if i.day == 1 and i.rounds]
    first, second = day1[0], day1[1]
    a, b = opening_sheet(first), opening_sheet(second)

    before = numbers()
    assert before[a] < before[b], "the two races were not in the order assumed"

    prog.programme = P.moved(prog.programme, prog.programme.index(first), +1)
    after = numbers()
    assert after[b] < after[a], "the register did not follow the running order"


def test_an_annullato_keeps_its_number_and_nobody_else_gets_it(prog):
    """A number is spent when the sheet is: RET is not a number to hand out."""
    spec = sorted(prog.communiques, key=lambda c: c.n)[5]
    spec.ret = True
    n = spec.n

    out = C.autonumber(prog, add_missing=False)
    assert next(c for c in out if c.sheets[0].key == spec.sheets[0].key).n == n
    assert [c.n for c in out].count(n) == 1


def test_two_documents_on_one_sheet_take_one_number(prog):
    """A comunicato that carries two sheets is one comunicato, and one number."""
    two = _com(prog, "AL", "velocita", "Turno 1", "risultati")
    two.extra = [Sheet(doc="partenti_recuperi")]
    out = C.autonumber(prog, add_missing=False)
    same = [c for c in out if c.sheets[0].key == two.sheets[0].key]
    assert len(same) == 1 and len(same[0].sheets) == len(two.sheets)


def test_the_register_of_a_programme_being_built_gains_what_it_lacks(prog):
    """Building a new competition: every sheet wants a number, and gets one."""
    prog.communiques = []
    out = C.autonumber(prog)
    assert len(out) == len(C.sheet_order(prog))
    assert [c.n for c in out] == list(range(1, len(out) + 1))
    assert all(c.title for c in out), "a proposed comunicato with no title"


def test_numbering_writes_nothing(prog):
    """It returns a list; the page decides whether to put it on the draft."""
    before = [(c.n, c.sheets[0].key) for c in prog.communiques]
    C.autonumber(prog)
    assert [(c.n, c.sheets[0].key) for c in prog.communiques] == before


def test_a_race_ridden_first_is_numbered_first(prog):
    """The 5°-8° final and the keirin's second one go out before the title race.

    The fase's own `docs:` list is the order its sheets are issued in, and it
    is deliberately not the order of `DOC_ALL_KINDS`: both of those races are
    ridden before the final for the title, so both file first.
    """
    item = next(i for i in prog.programme if i.event == "velocita")
    finals = next(r for r in item.rounds if r.key == "Finali")
    finals.docs = ["partenti", "risultati_5-8", "risultati", "classifica"]

    order = [s.doc for s in C.sheet_order(prog)
             if (s.cat, s.event, s.round_key) == (item.cat, item.event, "Finali")]
    assert order.index("risultati_5-8") < order.index("risultati")
