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
    from core.i18n import PENALTIES, penalty_name

    assert code in PENALTIES and penalty_name(code) != code


def test_the_regulation_files_are_json_the_app_can_read():
    """They are replaced by hand when the regulations change: a typo is a crash."""
    for path in (D.PENALTIES_FILE, D.PUIS_FILE):
        with path.open(encoding="utf-8") as fh:
            assert isinstance(json.load(fh), dict)
