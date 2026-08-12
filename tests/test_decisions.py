"""The jury's decision log, and the two regulation tables behind it."""

from __future__ import annotations

import json

import pytest

from core import decisions as D


# ── the log ─────────────────────────────────────────────────────────────────

def test_a_decision_is_numbered_from_one_in_the_order_it_was_taken(store):
    first = D.add(store, D.Decision(text="prima"))
    second = D.add(store, D.Decision(text="seconda"))
    assert (first.n, second.n) == (1, 2)
    assert [d.text for d in D.load(store)] == ["prima", "seconda"]
    # written down when it was taken, without the page having to say so
    assert first.ts and first.ts[:4].isdigit()


def test_deleting_one_leaves_the_others_where_they_are(store):
    """Deleting the last entry frees its number; deleting one under it does not.

    The mistyped decision is the one that gets deleted, and it is the one just
    written: retyping it as n. 2 is what the secretary expects. A gap in the
    middle stays a gap - renumbering would rename decisions already quoted.
    """
    for text in ("a", "b", "c"):
        D.add(store, D.Decision(text=text))
    D.remove(store, 2)
    assert [d.n for d in D.load(store)] == [1, 3]
    assert D.add(store, D.Decision(text="d")).n == 4

    D.remove(store, 4)
    assert D.add(store, D.Decision(text="e")).n == 4


def test_an_edit_keeps_the_number_and_the_place(store):
    D.add(store, D.Decision(text="a"))
    D.add(store, D.Decision(text="b"))
    second = D.load(store)[1]
    second.text = "b, corretta"
    second.penalty = "C"
    D.update(store, second)
    assert [(d.n, d.text) for d in D.load(store)] == [
        (1, "a"), (2, "b, corretta")]
    assert D.load(store)[1].penalty == "C"


def test_the_file_survives_a_reload_with_every_field(store):
    D.add(store, D.Decision(day=2, cat="AL", event="velocita",
                            round_key="Quarti", bibs="12, 15", penalty="D",
                            communique="42", text="squalifica"))
    d = D.load(store)[0]
    assert (d.day, d.cat, d.event, d.round_key) == (2, "AL", "velocita",
                                                    "Quarti")
    assert (d.bibs, d.penalty, d.communique) == ("12, 15", "D", "42")


def test_an_unknown_field_in_the_file_is_ignored(store):
    """A file written by a newer version must not take the page down."""
    store.write_json(D.FILE, [{"n": 1, "text": "x", "gravita": "alta"}])
    assert [d.text for d in D.load(store)] == ["x"]


def test_nothing_written_yet_reads_as_an_empty_log(store):
    assert D.load(store) == []
    assert D.next_n([]) == 1


# ── ammonizioni ─────────────────────────────────────────────────────────────

def warn(**kw) -> D.Decision:
    return D.Decision(penalty=D.WARNING, text="ammonizione", **kw)


def test_the_numbers_of_a_decision_are_read_out_of_the_field():
    assert D.bibs_of(D.Decision(bibs="12, 15")) == [12, 15]
    assert D.bibs_of(D.Decision(bibs="12 e 15; 3")) == [12, 15, 3]
    assert D.bibs_of(D.Decision(bibs="")) == []


def test_a_warning_is_carried_into_the_fasi_that_follow():
    rounds = ["Turno 1", "Quarti", "Semifinali", "Finali"]
    taken = [warn(cat="AL", event="velocita", round_key="Quarti", bibs="12"),
             # another specialità: it does not travel across events
             warn(cat="AL", event="keirin", round_key="Turno 1", bibs="7")]
    carried = D.warned_bibs(taken, "AL", "velocita", rounds=rounds,
                            upto="Semifinali")
    assert carried == {12: "Quarti"}
    # and never backwards, onto a sheet filed before the decision existed
    assert D.warned_bibs(taken, "AL", "velocita", rounds=rounds,
                         upto="Turno 1") == {}
    # nor on the fase it was taken in: that sheet carries the decision itself,
    # and the W is there to say it in the *next* race
    assert D.warned_bibs(taken, "AL", "velocita", rounds=rounds,
                         upto="Quarti") == {}


def test_a_warning_filed_against_no_fase_counts_everywhere():
    taken = [warn(cat="ES", event="omnium", bibs="4")]
    assert D.warned_bibs(taken, "ES", "omnium", rounds=["Scratch"],
                         upto="Scratch") == {4: ""}


def test_two_warnings_in_the_same_fase_are_a_disqualification():
    taken = [warn(cat="AL", event="madison", round_key="Finale", bibs="12"),
             warn(cat="AL", event="madison", round_key="Finale", bibs="12, 3"),
             warn(cat="AL", event="madison", round_key="Qualificazioni",
                  bibs="3")]
    assert D.double_warned(taken, "AL", "madison", "Finale") == [12]
    # 3 was warned twice, but in two different fasi: that is not a DSQ
    assert D.double_warned(taken, "AL", "madison", "Qualificazioni") == []


# ── the regulations ─────────────────────────────────────────────────────────

def test_the_uci_offences_come_out_in_numeric_order():
    reasons = D.reasons()
    assert reasons, "regulations/penalties.json not readable"
    numbers = [int(n) for n, _ in reasons]
    assert numbers == sorted(numbers)
    assert numbers[0] == 1 and len(numbers) > 30


def test_every_offence_has_italian_wording():
    assert all(text and not text.isspace() for _, text in D.reasons())
    assert "fascia azzurra" in D.reason("2")


def test_the_offences_are_translated():
    """The sheet is Italian; the UCI file also carries the other three."""
    assert D.reason("2", "EN") == "for riding on the blue band"
    assert D.reason("999") == ""


def test_the_puis_column_follows_the_categories_in_gara():
    """A giovanili championship reads the giovanili column, not the elite one."""
    assert D.puis_column_for(["ES", "ED", "AL", "DA"]) == "DA, AL, ED, ES"
    assert D.puis_column_for(["JU", "DJ"]) == "DJ, JU"
    # nothing to match still answers with a column: an empty panel helps nobody
    assert D.puis_column_for([]) in D.puis_columns()
    assert D.puis_column_for(["XX"]) in D.puis_columns()


def test_a_puis_column_carries_infringements_and_sanctions():
    rows = D.puis(D.puis_column_for(["ES", "ED", "AL", "DA"]))
    assert len(rows) > 30
    assert all(r.get("infrazione") for r in rows)
    assert any("casco" in r["infrazione"] for r in rows)


def test_the_puis_search_reads_both_columns():
    column = D.puis_column_for(["ES", "ED", "AL", "DA"])
    assert len(D.puis_search(column, "")) == len(D.puis(column))
    assert all("casco" in r["infrazione"].lower()
               for r in D.puis_search(column, "casco"))
    # the sanction is searched too: "what costs an ammenda" is a real question
    assert D.puis_search(column, "ammenda")
    assert D.puis_search(column, "non esiste nel prontuario") == []


def test_a_missing_regulation_file_is_not_an_exception(tmp_path):
    """The free text is what the jury needs; the tables only save it typing."""
    missing = tmp_path / "nope.json"
    assert D._read(missing) == {}
    assert D.updated_at(missing) == ""


def test_a_broken_regulation_file_is_not_an_exception(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert D._read(broken) == {}


def test_both_regulation_tables_say_when_they_were_updated():
    for path in (D.PENALTIES_FILE, D.PUIS_FILE):
        assert D.updated_at(path), f"{path.name} has no {D._META}"


@pytest.mark.parametrize("code", D.CLASSES)
def test_every_degree_of_penalty_has_a_name(code):
    """In every language: a letter with no word behind it prints as the letter."""
    from core.i18n import CATALOGUES, penalty_name

    assert all(code in c.PENALTIES for c in CATALOGUES.values())
    assert penalty_name(code) != code


def test_the_regulation_files_are_json_the_app_can_read():
    """They are replaced by hand when the regulations change: a typo is a crash."""
    for path in (D.PENALTIES_FILE, D.PUIS_FILE):
        with path.open(encoding="utf-8") as fh:
            assert isinstance(json.load(fh), dict)


# ── the register: columns, codes, and reading it back ───────────────────────

def test_the_compact_code_is_the_provvedimento_and_the_article():
    """`C3` - what the jury quotes and what the sheet prints next to the number."""
    d = D.Decision(penalty="C", reason="3")
    assert d.code == "C3" and d.kind == "relegation"
    assert D.parse_code("C3") == ("C", "3")
    assert D.parse_code(" c3 ") == ("C", "3")
    # a decision that sanctions nobody has no code and is a plain note
    plain = D.Decision(text="Il torneo è stato disputato in due batterie.")
    assert plain.code == "" and plain.kind == D.NOTE


def test_a_penalty_without_an_article_still_has_a_code():
    """The provvedimento is the decision; the article is what it was taken under."""
    assert D.Decision(penalty="D").code == "D"
    assert D.Decision(penalty="D").kind == "disqualification"


def test_every_kind_a_block_can_have_is_one_the_sheets_can_colour():
    from core.config import NOTE_COLORS
    from core.i18n import CATALOGUES

    assert set(D.KINDS.values()) | {D.NOTE} == set(D.NOTE_KINDS)
    assert set(D.NOTE_KINDS) == set(NOTE_COLORS)
    for lang in CATALOGUES.values():
        assert set(D.NOTE_KINDS) == set(lang.NOTE_KINDS)


def test_the_article_is_kept_across_a_reload(store):
    D.add(store, D.Decision(penalty="A", reason="6", text="ammonito"))
    assert D.load(store)[0].code == "A6"


def test_one_specialita_is_read_back_fase_by_fase(store):
    """The recap the panel signs off: in programme order, empty fasi left out."""
    for rnd, bib in (("Quarti", "5"), ("Turno 1", "3"), ("Quarti", "7")):
        D.add(store, D.Decision(cat="AL", event="velocita", round_key=rnd,
                                bibs=bib, penalty="C", reason="2", text="x"))
    # another specialità entirely: it is not part of this recap
    D.add(store, D.Decision(cat="AL", event="keirin", round_key="Finali",
                            text="y"))
    groups = D.by_round(D.load(store), "AL", "velocita",
                        ["Qualificazioni", "Turno 1", "Quarti"])
    assert [(k, [d.bibs for d in v]) for k, v in groups] == [
        ("Turno 1", ["3"]), ("Quarti", ["5", "7"])]


def test_a_fase_the_programme_does_not_know_is_kept_at_the_end(store):
    """A round_key edited by hand must not drop out of the recap."""
    D.add(store, D.Decision(cat="AL", event="velocita", round_key="Turno 1",
                            text="a"))
    D.add(store, D.Decision(cat="AL", event="velocita", round_key="Spareggio",
                            text="b"))
    assert [k for k, _ in D.by_round(D.load(store), "AL", "velocita",
                                     ["Turno 1"])] == ["Turno 1", "Spareggio"]


def test_one_race_is_not_the_whole_specialita(store):
    """`round_key=None` is every fase; `""` is the fase that has no name."""
    D.add(store, D.Decision(cat="AL", event="omnium", round_key="", text="a"))
    D.add(store, D.Decision(cat="AL", event="omnium", round_key="Scratch",
                            text="b"))
    taken = D.load(store)
    assert len(D.for_race(taken, "AL", "omnium")) == 2
    assert [d.text for d in D.for_race(taken, "AL", "omnium", "")] == ["a"]
    assert [d.text for d in D.for_race(taken, "AL", "omnium", "Scratch")] == ["b"]


# ── the sentence proposed to the jury ───────────────────────────────────────

def test_the_proposal_is_the_wording_the_jury_would_have_written():
    line = D.compose("DA 46 BOSONIN MELANIE", "A", "6")
    assert line.startswith("DA 46 BOSONIN MELANIE: AMMONIZIONE (A) ")
    assert line.endswith(D.reason("6"))


def test_every_part_of_the_proposal_is_optional():
    """A decision about nobody, under no article, is one the jury types itself."""
    assert D.compose("", "", "") == ""
    assert D.compose("AL 3", "", "") == "AL 3:"
    assert "SQUALIFICA (D)" in D.compose("", "D", "")
