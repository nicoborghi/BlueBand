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
from core.config import Round, Sheet, load_competition, validate


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


def test_a_meeting_says_whether_it_assigns_titles(prog, tmp_path):
    """Campionato or ordinaria: the one thing that decides CAMPIONE D'ITALIA.

    Written both ways round - a programme silent about it is one the next jury
    would have to guess at - and a file from before the question existed reads
    as a championship, which is what every one of them was.
    """
    from core.config import KIND_CHAMPIONSHIP, KIND_ORDINARY

    assert prog.kind == KIND_CHAMPIONSHIP and prog.assigns_titles is True
    assert "kind: championship" in P.dump(prog)

    prog.kind = KIND_ORDINARY
    again = _round_trip(prog, tmp_path)
    assert again.kind == KIND_ORDINARY and again.assigns_titles is False


def test_a_programme_that_says_nothing_is_a_championship(tmp_path):
    from core.config import KIND_CHAMPIONSHIP, load_competition

    path = tmp_path / "programme.yaml"
    path.write_text("name: Trofeo\ntrack_len: 0.25\nkind: qualunque cosa\n",
                    encoding="utf-8")
    assert load_competition(path).kind == KIND_CHAMPIONSHIP


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
    item.rounds[0] = dataclasses.replace(item.rounds[0], duration=25)

    back = _round_trip(prog, tmp_path)
    got = next(i for i in back.programme
               if (i.cat, i.event) == (item.cat, item.event))
    assert (got.scheme, got.final_5_8, got.final_b) == ("8", False, True)
    assert got.rounds[0].duration == 25


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


def test_a_pinned_number_survives_a_save(prog, tmp_path):
    """`pinned` says *do not move this*, and a save that lost it would move it.

    It is the only thing that holds a number still now: the freeze that used to
    stop the whole register from renumbering itself is gone, together with the
    renumbering it was there to stop.
    """
    prog.communiques[0].pinned = True
    assert _round_trip(prog, tmp_path).communiques[0].pinned is True

    # and the old key is not written back by a file that still carries it
    prog.numbering_frozen = True          # what an old programme.yaml says
    assert "numbering_frozen" not in P.dump(prog)


def test_numbering_the_classification_alone_is_written_only_when_off(prog,
                                                                    tmp_path):
    """On is the default and not a statement; off is one, and goes on paper."""
    assert prog.number_on_classification is True
    assert "number_on_classification" not in P.dump(prog)

    prog.number_on_classification = False
    back = _round_trip(prog, tmp_path)
    assert back.number_on_classification is False


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


def test_moving_a_line_of_the_register_moves_only_that_line(comp):
    """`moved` is the list operation; the numbers are `communiques.autonumber`."""
    day1 = [c for c in comp.communiques if c.day == 1]
    moved = P.moved(day1, 0, 1)
    assert [c.title for c in moved][:2] == [day1[1].title, day1[0].title]
    assert sorted(c.n for c in moved) == sorted(c.n for c in day1)


def test_a_typed_number_takes_the_place_it_asks_for():
    """The scaletta of a giornata, reordered by typing into it.

    One number retyped moves that fase and closes the ranks around it - the
    fase that was already at that place goes down, not the other way round.
    """
    was = [1, 2, 3, 4, 5]
    assert P.reordered([1, 2, 3, 4, 5], was) == [0, 1, 2, 3, 4]
    # the fifth asked to be first: it is, and the rest keep their order
    assert P.reordered([1, 2, 3, 4, 1], was) == [4, 0, 1, 2, 3]
    # the first asked to be last
    assert P.reordered([5, 2, 3, 4, 5], was) == [1, 2, 3, 4, 0]
    # and a number past the end of the giornata is the end of it
    assert P.reordered([9, 2, 3, 4, 5], was) == [1, 2, 3, 4, 0]


def test_more_than_one_number_moves_in_the_same_gesture():
    """The point of the table: a giornata is reshuffled before it is applied.

    Two fasi retyped at once must both land where they asked, which one nudge
    per rerun could only do one at a time - and a number nobody touched never
    stands in the way of one that was just written.
    """
    was = [1, 2, 3, 4, 5, 6]
    # the fifth and the sixth to the front: first and second, not first and
    # third with the old first row left in between
    assert P.reordered([1, 2, 3, 4, 1, 2], was) == [4, 5, 0, 1, 2, 3]
    # the first two sent to the back, the untouched ones close up
    assert P.reordered([3, 4, 3, 4, 5, 6], was) == [2, 3, 0, 1, 4, 5]
    # the one that was typed takes the place, the one that only happened to be
    # there slides up
    assert P.reordered([2, 2, 3, 4, 5, 6], was) == [1, 0, 2, 3, 4, 5]
    # out of range, and nothing is ever lost
    assert sorted(P.reordered([9, 9, 1, 1, 5, 6], was)) == [0, 1, 2, 3, 4, 5]


def test_a_document_moved_onto_a_taken_number_merges_with_it(comp):
    """Two documents on one number are one comunicato with two sheets on it.

    Which is the whole way the register expresses a velocità: the risultati of
    the batterie and the ordine di partenza dei recuperi go out together.
    """
    rows = P.rows_from_specs([c for c in comp.communiques if c.day == 1])
    first, second = rows[0], rows[1]
    moved = P.numbered(rows, dict(second), first["n"])
    specs = P.specs_from_rows(moved)
    one = next(s for s in specs if s.n == first["n"])
    assert [sheet.doc for sheet in one.sheets] == [first["doc"], second["doc"]]
    # and there is no longer a comunicato under the number it left
    assert not [s for s in specs if s.n == second["n"]]


def test_a_document_numbered_zero_leaves_the_register(comp):
    """A cleared cell is a decision: that sheet is not planned any more."""
    rows = P.rows_from_specs([c for c in comp.communiques if c.day == 1])
    gone = P.numbered(rows, dict(rows[0]), 0)
    assert len(gone) == len(rows) - 1
    assert rows[0] not in gone


def test_the_register_comes_back_in_the_order_of_its_numbers(comp):
    """`specs_from_rows` reads *adjacent* equal numbers as one sheet."""
    rows = P.rows_from_specs([c for c in comp.communiques if c.day == 1])
    moved = P.numbered(rows, dict(rows[-1]), rows[0]["n"])
    assert [r["n"] for r in moved] == sorted(r["n"] for r in moved)



def test_the_register_carries_every_sheet_the_programme_produces(comp):
    """The tedious half: nothing is missing, and nothing is numbered twice.

    What `plan_day` used to promise as a proposal, `autonumber` guarantees as
    the register itself - every document of every fase is on exactly one
    comunicato, and the accorpamenti are which of them share a number.
    """
    specs = C.autonumber(comp, [], rebuild=True)
    carried = [s.key for c in specs for s in c.sheets]
    produced = {s.key for s in C.sheet_order(comp)}

    assert produced <= set(carried), "a sheet the register does not carry"
    assert len(carried) == len(set(carried)), "a sheet on two comunicati"
    assert [c.n for c in specs] == sorted({c.n for c in specs})


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


def test_a_classifica_registered_from_its_fase_has_not_moved(prog):
    """The classifica closes the specialità: the register may still name the
    fase it was printed from, and that is the same sheet the plan carries."""
    from core.communiques import Issued

    spec = next(c for c in prog.communiques
                if any(s.doc == "classifica" for s in c.sheets))
    sheet = next(s for s in spec.sheets if s.doc == "classifica")
    assert sheet.round_key == "", "a classifica is planned against no fase"

    issued = [Issued(n=spec.n, title=spec.title, cat=sheet.cat,
                     event=sheet.event, round_key="Finale", doc="classifica")]
    assert not [i for i in P.issues(prog, issued)
                if i.code == "communique_moved"]


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

    This is the whole reason the order is built from what each sheet *waits
    for* instead of simply putting every start list first.

    Between *stages*, not between fasi: two batterie di qualificazione are
    ridden by different riders and neither composes the other, so both start
    orders go out with the rest of the morning.
    """
    from core.models import split_heat

    order = C.sheet_order(comp)
    at = {(s.cat, s.event, s.round_key, s.doc): i for i, s in enumerate(order)}
    for item in comp.programme:
        for before, after in zip(item.rounds, item.rounds[1:]):
            if split_heat(after.key)[1] and \
                    split_heat(before.key)[0] == split_heat(after.key)[0]:
                continue                  # two batterie of the same fase
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
    """Building a new competition: every comunicato wants a number, and gets one.

    One per *comunicato* and not per sheet: two documents that go out together
    share a number, which is what `bundles` decides.
    """
    prog.communiques = []
    out = C.autonumber(prog)
    assert len(out) == len(C.bundles(prog))
    assert sum(len(c.sheets) for c in out) == len(C.sheet_order(prog))
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


# ── a specialità spezzata su più giornate ───────────────────────────────────
#
# A velocità qualifies on the Saturday and rides its finali on the Sunday, and
# it is one race either way: the fasi carry the day (`Round.day`), the race
# stays one `ProgrammeItem` - which is what `Competition.scheduled` and every
# lookup behind `core.race` reads.

def _split(prog, cat="AL", event="velocita"):
    """Move the last two fasi of a race one day later, and say which they are."""
    item = prog.scheduled(cat, event)
    later = item.day + 1
    for rnd in item.rounds[-2:]:
        rnd.day = later
    return item, later


def test_a_race_can_be_ridden_over_two_days(prog):
    item, later = _split(prog)
    assert prog.day_of(item, item.rounds[0]) == item.day
    assert prog.day_of(item, item.rounds[-1]) == later
    # one race, all its fasi: nothing that looks a round up may notice the split
    assert len(prog.rounds(item.cat, item.event)) == len(item.rounds)
    assert {item.day, later} <= set(prog.days())


def test_the_giornata_of_a_split_race_is_written_and_read_back(prog, tmp_path):
    item, later = _split(prog)
    keys = [r.key for r in item.rounds if r.day]
    again = _round_trip(prog, tmp_path)
    back = again.scheduled(item.cat, item.event)
    assert [r.key for r in back.rounds if r.day == later] == keys
    assert _same(prog, again)


def test_a_programme_that_splits_nothing_says_nothing_about_days(prog):
    """A fase says its giornata only when it is not the one of its race.

    Which is what keeps the file of a competition that splits nothing exactly
    as it was: the field is new, and it must be invisible until it is used.
    """
    rounds = [line for line in P.dump(prog).splitlines()
              if line.strip().startswith("- {key:")]
    assert rounds and not [line for line in rounds if "day:" in line]



def test_the_register_follows_the_fase_and_not_the_race(prog):
    """A fase ridden on the Sunday is numbered among the Sunday's comunicati."""
    item, later = _split(prog)
    moved = {r.key for r in item.rounds if r.day == later}

    specs = C.autonumber(prog, [], rebuild=True)
    mine = [c for c in specs if (c.cat, c.event) == (item.cat, item.event)]
    assert {c.round_key for c in mine if c.day == later} >= moved

    order = [s for s in C.sheet_order(prog)
             if (s.cat, s.event) == (item.cat, item.event)]
    stayed = [s for s in order if s.round_key not in moved and s.round_key]
    went = [s for s in order if s.round_key in moved]
    assert stayed and went
    assert order.index(went[0]) > order.index(stayed[-1])


def test_a_fase_on_no_day_is_a_warning_and_not_an_error(prog):
    item = prog.scheduled("AL", "velocita")
    item.day = 0
    for rnd in item.rounds:
        rnd.day = 0
    found = [i for i in P.issues(prog) if i.code == "round_no_day"]
    assert len(found) == len(item.rounds)
    assert all(i.level != ERROR for i in found)
    assert all(i.level != ERROR for i in P.issues(prog) if i.code == "cat_no_event")


def test_a_categoria_with_nothing_to_ride_is_said_out_loud(prog):
    prog.categories["MA"] = dataclasses.replace(prog.categories["AL"], code="MA")
    assert [i for i in P.issues(prog) if i.code == "cat_no_event"]


def test_a_fase_the_jury_does_not_contest_leaves_the_programme(prog, tmp_path):
    """An omnium without the scratch starts on the eliminazione.

    The regulation proposes the four prove; which of them are ridden is the
    jury's, and a fase nobody rides must not go on filing comunicati.
    """
    item = next(i for i in prog.programme if i.event == "omnium")
    first = item.rounds[0]
    item.rounds = item.rounds[1:]

    assert [s for s in C.sheet_order(prog)
            if (s.cat, s.event, s.round_key) == (item.cat, item.event, first.key)] == []
    again = _round_trip(prog, tmp_path)
    assert [r.key for r in again.scheduled(item.cat, item.event).rounds] \
        == [r.key for r in item.rounds]


def test_a_fase_carries_a_printed_note_and_a_private_one(prog, tmp_path):
    """Two notes: the one the teams read, and the one that never leaves the file."""
    item = prog.scheduled("AL", "velocita")
    rnd = item.rounds[0]
    rnd.sheet_note = "Si corre sul rettilineo opposto."
    rnd.note = "Chiedere conferma al cronometrista."

    back = _round_trip(prog, tmp_path).round_of("AL", "velocita", rnd.key)
    assert back.sheet_note == rnd.sheet_note and back.note == rnd.note


def test_the_composizione_is_not_a_fase_on_a_giornata(prog):
    """It is the jury's own job: nobody rides it and it goes on no day.

    A madison is composed before it is ridden - every coppia numbered and put
    in its batteria - and that round files no comunicato. It must not be the
    thing that makes a scheduled race look half-placed.
    """
    from core.config import ROUND_SETUP

    item = next(i for i in prog.programme if i.event == "madison")
    setup = next(r for r in item.rounds if r.kind == ROUND_SETUP)
    assert setup.day == 0 and item.day

    assert not [i for i in P.issues(prog)
                if i.code == "round_no_day" and setup.label in i.message]
    assert not [s for s in C.sheet_order(prog)
                if s.round_key == setup.key and s.cat == item.cat]


def test_the_scaletta_of_a_giornata_is_numbered_by_the_jury(prog):
    """`seq` is the running order, and the register is a view of it.

    A file nobody has reordered says nothing: the fasi come out in programme
    order, exactly as they always did. Numbering one moves it, and its
    comunicati move with it - which is the whole reason the register is
    proposed from the programme and not typed.
    """
    def numbers_now(comp):
        return {c.sheets[0].key: c.n
                for c in C.autonumber(comp, add_missing=False)}

    day = 1
    before = [(i.cat, i.event, r.key) for i, r in prog.rounds_on(day)]
    assert before and all(r.seq == 0 for _i, r in prog.rounds_on(day))
    was = numbers_now(prog)

    # what the page does when a 1 is typed on the fourth line: that fase to the
    # head, and the giornata closes ranks behind it (`programme._renumber`)
    item, rnd = prog.rounds_on(day)[3]
    rnd.seq = 1
    for n, r in enumerate([p[1] for p in prog.rounds_on(day)
                           if p[1] is not rnd], start=2):
        r.seq = n
    after = [(i.cat, i.event, r.key) for i, r in prog.rounds_on(day)]
    assert after[0] == (item.cat, item.event, rnd.key)
    assert sorted(after) == sorted(before)   # nothing lost, nothing invented

    # its comunicati went up with it. Not necessarily to the head of the day:
    # the sort still publishes every ordine di partenza of a depth before the
    # risultati of that depth (`communiques.sheet_order`), and the scaletta
    # decides the order *inside* that rule.
    opening = (item.cat, item.event, rnd.key, (rnd.docs or [""])[0])
    assert numbers_now(prog)[opening] < was[opening]


def test_the_composizione_is_not_in_the_running_order(prog):
    """Nobody rides it, so it is not a place in the scaletta of a giornata."""
    from core.config import ROUND_SETUP

    item = next(i for i in prog.programme if i.event == "madison")
    setup = next(r for r in item.rounds if r.kind == ROUND_SETUP)
    assert setup not in [r for _i, r in prog.rounds_on(item.day)]



def test_the_risultati_follow_the_scaletta(prog):
    """A fase moved up the giornata brings its comunicati with it.

    The ordini di partenza do not: they go out when what composes them is
    ridden, or at the head of the day if nothing does.
    """
    day = 2
    specs = C.autonumber(prog, [], rebuild=True)
    scaletta = [(i.cat, i.event, r.key) for i, r in prog.rounds_on(day)]
    filed = [(c.cat, c.event, c.round_key) for c in specs
             if c.day == day and c.doc == "risultati"]
    assert filed == [k for k in scaletta if k in filed]



def test_the_register_opens_on_the_elenchi_and_then_on_start_orders(prog):
    """The order sheets actually go out in, which is what CITA26's register is.

    An elenco iscritti per categoria racing that day, then the ordini di
    partenza of the fasi that open it - nothing has been ridden, so nothing
    composes them - and only then the risultati. Nobody asks for it and nobody
    sets a number: it falls out of `communiques.bundles`, which reads the day
    as the order things can be *published* in.
    """
    day1 = [c for c in C.autonumber(prog, [], rebuild=True) if c.day == 1]
    assert [c.doc for c in day1[:11]] == ["partenti"] * 11
    assert {c.event for c in day1[:4]} == {"entry_list"}
    assert [c.cat for c in day1[:4]] == [c for c in prog.cat_order()
                                         if any(i.cat == c for i, _r
                                                in prog.rounds_on(1))]
    assert day1[11].doc == "risultati"



def test_a_start_order_follows_the_risultati_that_compose_it(prog):
    """*risultati batterie, partenti finale*: the second cannot be written first."""
    specs = C.autonumber(prog, [], rebuild=True)
    keys = [(c.cat, c.event, c.round_key, c.doc) for c in specs]
    # the batterie compose the finale; the risultati of the finale itself go
    # out after its partenti and are not what anybody waits for
    heats = max(i for i, k in enumerate(keys)
                if k[:2] == ("ES", "madison") and k[3] == "risultati"
                and "Batteria" in k[2])
    final = keys.index(("ES", "madison", "Finale", "partenti"))
    assert final == heats + 1



def test_the_numbers_run_from_one_with_no_holes(prog):
    """Whatever else it does, a register is 1..N and says every number once.

    The three switches that used to trim the proposal - elenchi iscritti, how
    many ordini di partenza go out ahead, whether the classifica travels with
    the fase that closes the specialità - are gone: they were questions about
    what the numbering can work out for itself.
    """
    specs = C.autonumber(prog, [], rebuild=True)
    assert [c.n for c in specs] == list(range(1, len(specs) + 1))
    assert [c for c in specs if c.doc == "classifica" or "classifica"
            in [s.doc for s in c.sheets]]



def test_a_madison_publishes_its_classifica_on_the_risultati(prog):
    """The sheet that says who won a madison *is* the ordine d'arrivo.

    One race decides it, so the risultati of the finale and the classifica are
    one comunicato - and the number is printed on the classifica
    (`communiques.number_for`). Its batterie still file their own risultati:
    they are what decides who rides the finale.
    """
    specs = C.autonumber(prog, [], rebuild=True)
    mine = [c for c in specs if (c.cat, c.event) == ("ES", "madison")]
    closing = next(c for c in mine
                   if "classifica" in [s.doc for s in c.sheets])
    assert [(s.round_key, s.doc) for s in closing.sheets] == [
        ("Finale", "risultati"), ("", "classifica")]
    assert [c.round_key for c in mine if c.doc == "risultati"
            and c is not closing] == ["Qualificazioni Batteria 1",
                                      "Qualificazioni Batteria 2"]



def test_an_omnium_prova_is_started_by_the_standings_before_it(proposed):
    """The classifica parziale after a prova *is* the next prova's start order.

    One number, two titles: the sheet exists and does not need a comunicato of
    its own. It used to be expressed by proposing no start order at all, which
    is the same thing said by leaving a document out of the register - and a
    sheet nobody could find in it.
    """
    specs = C.autonumber(proposed, [], rebuild=True)
    mine = [c for c in specs if (c.cat, c.event) == ("ES", "omnium")]
    carried = {(s.round_key, s.doc): c.n for c in mine for s in c.sheets}

    # every prova after the first is started by the parziale of the one before
    for before, after in (("Scratch", "Tempo Race"),
                          ("Tempo Race", "Eliminazione"),
                          ("Eliminazione", "Corsa a Punti")):
        assert carried[(after, "partenti")] == \
            carried[(before, "classifica_parziale")]
    # and the first prova opens on a start order of its own, like any race
    assert carried[("Scratch", "partenti")] not in [
        n for (k, d), n in carried.items() if d == "classifica_parziale"]



def test_a_recount_leaves_the_register_without_holes(prog):
    """A day that gains sheets pushes the days after it, and nothing collides."""
    prog.communiques = C.autonumber(prog, [], rebuild=True)

    numbers = sorted(c.n for c in prog.communiques)
    assert numbers == list(range(1, len(numbers) + 1))
    assert not [i for i in P.issues(prog) if i.level == ERROR]


# ── which documents share a comunicato ──────────────────────────────────────
#
# A fase says which sheets it files; which of them go out on the same number is
# a handful of generic rules (`regulations/communiques.json`). These are about
# the four that matter, on the shapes they were written for.

@pytest.fixture
def proposed(comp):
    """CITA26 with the documents the regulation proposes, not the ones typed.

    The file predates the classifica parziale being a sheet of a fase: it
    declares those in the register instead, which is the same document said in
    the other of the two places. The rules work on what a fase *files*, so the
    fixture asks for the proposal first - which is what the Assegna documenti
    button does.
    """
    import copy
    import dataclasses

    from core import rounds as RD
    from core.config import ROUND_SETUP

    # a deep copy of the programme, not a shallow replace: the fixture rewrites
    # `docs` on every fase, and the competition is session-scoped - doing that
    # in place would hand the next test a file nobody wrote
    fresh = dataclasses.replace(comp, merge={},
                                programme=copy.deepcopy(comp.programme),
                                communiques=copy.deepcopy(comp.communiques))
    for item in fresh.programme:
        if item.event == "entry_list":
            continue
        opts = RD.options_of(fresh, item.cat, item.event)
        for rnd in item.rounds:
            rnd.docs = ([] if rnd.kind == ROUND_SETUP
                        else list(RD.docs_for(fresh, item.cat, item.event,
                                              rnd.key, opts) or []))
    return fresh


def _bundle_of(comp, cat, event, round_key, doc):
    """The comunicato that publishes one sheet, as the rules group them."""
    want = (cat, event, round_key, doc)
    return next(b for b in C.bundles(comp)
                if any(s.key == want for s in b.sheets))


def test_an_omnium_partial_is_the_start_order_of_the_next_prova(proposed):
    """The rule the jury asked for by name, and the exception in it.

    The standings after a prova *are* the ordine di partenza of the one after
    it - one number, two titles. The first prova is the exception: nothing is
    partial before it, so there its risultati and the standings are the same
    table and the next start order rides with both.
    """
    after = _bundle_of(proposed, "ES", "omnium", "Tempo Race",
                       "classifica_parziale")
    assert [s.doc for s in after.sheets] == ["classifica_parziale", "partenti"]
    assert after.sheets[1].round_key == "Eliminazione"

    first = _bundle_of(proposed, "ES", "omnium", "Scratch", "risultati")
    assert [s.doc for s in first.sheets] == ["risultati", "classifica_parziale",
                                             "partenti"]
    assert first.sheets[2].round_key == "Tempo Race"


def test_switching_the_omnium_rule_off_gives_every_sheet_its_own_number(
        proposed):
    """It is a rule of this meeting, not a law: `merge:` in the programme."""
    import dataclasses

    on = len(C.bundles(proposed))
    off = dataclasses.replace(proposed, merge={
        "partial_is_next_startlist": False,
        "partial_is_results_of_first": False})
    assert len(C.bundles(off)) > on


def test_a_sprint_publishes_the_next_start_order_with_the_results(proposed):
    """«Quarti - Risultati, Semifinali - Partenti»: one sheet, one number."""
    b = _bundle_of(proposed, "ES", "velocita", "Quarti", "risultati")
    assert [(s.round_key, s.doc) for s in b.sheets] == [
        ("Quarti", "risultati"), ("Semifinali", "partenti")]


def test_a_timed_race_keeps_its_qualifying_and_its_finals_apart(proposed):
    """Half a giornata passes between them: they are two comunicati."""
    b = _bundle_of(proposed, "AL", "ins_squadre", "Qualificazioni", "risultati")
    assert len(b.sheets) == 1


def test_a_race_decided_by_one_run_files_results_and_classification_together(
        proposed):
    """A madison finale *is* its own classifica - one table, one number.

    A velocità a squadre is not: it rides a qualification and two finals, and
    its classifica is a third table that goes out on its own.
    """
    one = _bundle_of(proposed, "ED", "madison", "Finale", "risultati")
    assert [s.doc for s in one.sheets] == ["risultati", "classifica"]

    two = _bundle_of(proposed, "AL", "vel_squadre", "Finali", "risultati")
    assert [s.doc for s in two.sheets] == ["risultati"]


def test_the_titles_name_everything_the_comunicato_carries(proposed):
    """A comunicato that publishes two things and names one is why nobody
    could find the second."""
    b = _bundle_of(proposed, "ES", "velocita", "Quarti", "risultati")
    title = C.title_of(proposed, b)
    assert title.startswith("ES Velocità")
    assert "Quarti" in title and "Semifinali" in title
    # said once: the categoria and the specialità are the same for every sheet
    assert title.count("Velocità") == 1


def test_rebuilding_the_register_drops_what_the_programme_lost(proposed):
    """The button TR26 needs: a register full of fasi that no longer exist.

    Rebuilding is the one operation allowed to throw a line away - and only a
    line nobody has issued, pinned or annulled.
    """
    from core.config import CommuniqueSpec

    proposed.communiques = [
        CommuniqueSpec(n=1, day=1, cat="ES", event="omnium",
                       round_key="Una fase che non esiste", doc="partenti"),
        CommuniqueSpec(n=2, day=1, cat="ES", event="omnium",
                       round_key="Nemmeno questa", doc="partenti", pinned=True),
    ]
    out = C.autonumber(proposed, [], rebuild=True)
    keys = {c.sheets[0].key for c in out}
    assert ("ES", "omnium", "Una fase che non esiste", "partenti") not in keys
    assert ("ES", "omnium", "Nemmeno questa", "partenti") in keys, \
        "a number pinned by hand is somebody's expectation"


def test_a_register_that_already_numbers_a_sheet_is_not_regrouped(proposed):
    """Without a rebuild, what the jury numbered stays numbered.

    The rules would put the start order of the semifinali under the results of
    the quarti; a register that already carries it on a number of its own is
    the jury's record, and renumbering must not swallow it.
    """
    numbered = C.autonumber(proposed, add_missing=False)
    assert len(numbered) == len(proposed.communiques)
    assert {c.sheets[0].key for c in numbered} \
        == {c.sheets[0].key for c in proposed.communiques}


# ── pause: the giornata is not only races ───────────────────────────────────

def test_a_pause_takes_its_minutes_off_the_clock(prog):
    """The orari under a pausa are the hours the giuria will actually call.

    A pausa is a programme item like any other (`programme.add_pause`), so it
    sits in the running order, is re-timed by the same clock and moves with the
    same buttons - it simply is not ridden.
    """
    day = prog.days()[0]
    prog.day_start[day] = "14:30"
    was = prog.day_end(day)

    item = P.add_pause(prog, day, 30)
    assert (item, item.rounds[0]) in prog.rounds_on(day)
    assert prog.duration_of(item, item.rounds[0]) == 30
    # it goes in at the bottom of the scaletta, so the giornata ends half an
    # hour later and nothing above it has moved
    end = prog.day_end(day)
    assert int(end[:2]) * 60 + int(end[3:]) \
        == int(was[:2]) * 60 + int(was[3:]) + 30


def test_a_pause_files_nothing_and_carries_no_communique(prog):
    """No comunicato hangs off a pausa: it publishes no sheet to number."""
    day = prog.days()[0]
    item = P.add_pause(prog, day, 20, "Premiazioni")
    assert item.rounds[0].docs == []

    planned = C.plan_from_programme(prog)
    assert not [c for c in planned if c.event == "pause"]
    # and it is not a race with two empty fields: the checks say nothing at all
    keys = {(i.key, i.text) for i in P.issues(prog)}
    assert not [k for k in keys if "pause" in str(k)]


def test_a_pause_survives_being_written_and_read_again(prog, tmp_path):
    """The round trip the whole file rests on, for a line that is not a race."""
    P.add_pause(prog, prog.days()[0], 30, "Intervallo")
    path = tmp_path / "programme.yaml"
    path.write_text(P.dump(prog), encoding="utf-8")

    back = load_competition(path)
    pause = [i for i in back.programme if i.event == "pause"]
    assert len(pause) == 1
    rnd = pause[0].rounds[0]
    assert (rnd.label, rnd.duration, rnd.docs) == ("Intervallo", 30, [])
    assert not [m for m in validate(back) if "pause" in m]


def test_two_pauses_on_one_giornata_are_told_apart(prog):
    """Both are called *Pausa*: the running order still has to know which is which."""
    day = prog.days()[0]
    a = P.add_pause(prog, day, 15)
    b = P.add_pause(prog, day, 30)
    assert a.rounds[0].key != b.rounds[0].key


def test_taking_a_pause_off_the_giornata_deletes_it(prog):
    """A pausa belongs to the giornata and to no race.

    Left in the programme on no day it would be a line nothing shows and
    nobody could get back to - which is not what *Togli* means anywhere else,
    and is the only sensible thing it can mean here.
    """
    from ui.pages.programme import _off_day

    day = prog.days()[0]
    item = P.add_pause(prog, day, 30)
    _off_day(prog, item, item.rounds[0])
    assert item not in prog.programme
    assert not [i for i in prog.programme if i.event == "pause"]


def test_the_documents_of_a_fase_survive_leaving_it_and_coming_back(monkeypatch):
    """Streamlit drops the state of a widget a run does not draw.

    Only one fase is drawn at a time, so switching to another one and back
    used to bring the multiselect up empty - its `_model` signature had not
    moved, nothing reseeded it, and the box wrote *no documents* onto a fase
    nobody had touched. It cost an ED Omnium Tempo Race its comunicati 7 and
    24 in the middle of a competition.
    """
    from ui.pages import programme as PG

    session = {}
    monkeypatch.setattr(PG.st, "session_state", session, raising=False)
    options = ["partenti", "risultati", "classifica_parziale"]
    docs = ["partenti", "risultati", "classifica_parziale"]

    PG._pick_sync("prog_docs_ED_omnium_Tempo Race", options, docs)
    assert session["prog_docs_ED_omnium_Tempo Race"] == docs

    # the jury edits another fase: Streamlit forgets the widget, not the model
    del session["prog_docs_ED_omnium_Tempo Race"]

    PG._pick_sync("prog_docs_ED_omnium_Tempo Race", options, docs)
    assert session["prog_docs_ED_omnium_Tempo Race"] == docs
