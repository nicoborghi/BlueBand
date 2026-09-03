"""The rules of a regolamento, counted over an elenco (`config.Check`).

One row of the Controlli tab is one sentence of the articolo sulle iscrizioni,
and what it means is three words: what is counted, what it is counted for, and
how many there may be. These are the tests that the five shapes the old
`quotas:` block had are all of them the same loop now - and that a programme
written in the older words still says the same thing.
"""

from dataclasses import replace

import pytest

from conftest import EXAMPLE_PROGRAMME, COMPETITIONS
from core.config import Check, Quotas, load_competition
from core.entries import validate_entries
from core.models import EntryList, EventEntry, Pair, Rider, Team


@pytest.fixture(scope="module")
def comp():
    return load_competition(EXAMPLE_PROGRAMME)


def _rider(key, cat="AL", region="TOSCANA", club="SC UNA", events=(), **kw):
    return Rider(key=key, cat=cat, bib=int(key), last_name=key.upper(),
                 first_name="X", uci_id=f"1000000000{key}", region=region,
                 club=club, events={s: EventEntry(starter=t) for s, t in events},
                 **kw)


def _list(*riders, teams=(), pairs=()):
    return EntryList(riders={r.key: r for r in riders},
                     teams={t.key: t for t in teams},
                     pairs={p.key: p for p in pairs})


def _quota(el, comp, *checks):
    """Only the findings the rules produced - the elenco itself is not the point."""
    comp = replace(comp, checks=list(checks))
    return [i for i in validate_entries(el, comp) if i.code.startswith("quota")]


# ── atleti, per what the rule counts them for ───────────────────────────────

def test_riders_per_region(comp):
    """«Omnium massimo 2 corridori per regione» - the commonest sentence."""
    el = _list(*[_rider(str(n), cat="ES", events=[("omnium", True)])
                 for n in (1, 2, 3)],
               _rider("4", cat="ES", region="LIGURIA",
                      events=[("omnium", True)]))
    (issue,) = _quota(el, comp, Check(cat="ES", event="omnium", max=2))
    assert issue.level == "warn" and issue.code == "quota_region"
    assert "TOSCANA" in issue.message and "3 atleti (max 2)" in issue.message
    # the regione under the limit is not a finding, and neither is the same
    # sentence about a categoria that does not ride the specialità
    assert "LIGURIA" not in issue.message


def test_a_rule_names_the_categoria_it_is_about(comp):
    """What `max_per_region` could not say: two categorie, two limits.

    At the Trofeo delle Regioni 2026 the Km da fermo is one atleta per regione
    for the JU and two for the DJ. Keyed by specialità alone the two rules are
    one, and whichever was written last decided both.
    """
    el = _list(_rider("1", cat="JU", events=[("chilometro", True)]),
               _rider("2", cat="JU", events=[("chilometro", True)]),
               _rider("3", cat="DJ", events=[("chilometro", True)]),
               _rider("4", cat="DJ", events=[("chilometro", True)]))
    found = _quota(el, comp,
                   Check(cat="JU", event="chilometro", max=1),
                   Check(cat="DJ", event="chilometro", max=2))
    assert len(found) == 1 and "[JU" in found[0].message


def test_riders_per_club_and_per_club_inside_a_region(comp):
    """Two different sentences: over the categoria, and inside one squadra."""
    el = _list(_rider("1", events=[("ins_squadre", True)]),
               _rider("2", events=[("ins_squadre", True)]),
               _rider("3", region="LIGURIA", events=[("ins_squadre", True)]))
    (club,) = _quota(el, comp, Check(cat="AL", event="ins_squadre",
                                     per="club", max=2))
    assert club.code == "quota_club" and "3 atleti" in club.message
    (inside,) = _quota(el, comp, Check(cat="AL", event="ins_squadre",
                                       per="club_in_region", max=1))
    assert inside.code == "quota_club_region" and "TOSCANA" in inside.message
    assert "dorsali 1, 2" in inside.message  # who they are, for the desk


def test_riders_over_the_whole_category(comp):
    """A field limit: nothing to group by, just how many there are."""
    el = _list(*[_rider(str(n), cat="DA", region=f"R{n}",
                        events=[("eliminazione", True)]) for n in (1, 2, 3)])
    (issue,) = _quota(el, comp, Check(cat="DA", event="eliminazione",
                                      per="cat", max=2))
    assert issue.code == "quota_cat" and "3 atleti iscritti (max 2)" in issue.message


def test_a_riserva_counts_only_where_the_rule_says_so(comp):
    el = _list(_rider("1", cat="ES", events=[("omnium", True)]),
               _rider("2", cat="ES", events=[("omnium", False)]))
    assert _quota(el, comp, Check(cat="ES", event="omnium", max=1)) == []
    over = _quota(el, comp, Check(cat="ES", event="omnium", max=1,
                                  count_reserves=True))
    assert len(over) == 1


# ── squadre and coppie ──────────────────────────────────────────────────────

def test_teams_per_region(comp):
    el = _list(teams=[Team(key=f"AL:ins_squadre:TOSCANA:{c}", cat="AL",
                           event="ins_squadre", region="TOSCANA", letter=c,
                           riders=["1"]) for c in "AB"])
    (issue,) = _quota(el, comp, Check(cat="AL", event="ins_squadre",
                                      unit="teams", max=1))
    assert issue.code == "quota_teams" and "2 squadre/coppie" in issue.message


def test_a_team_of_the_madison_is_a_coppia(comp):
    """«1 Team per regione» on a madison: the formato says which it is.

    A regolamento writes *team* for both, and the elenco keeps coppie in
    another place: reading the word literally counted no coppia at all.
    """
    el = _list(pairs=[Pair(key=f"ES:TOSCANA:{n}", cat="ES", region="TOSCANA",
                           number=n, letter=c, riders=["1", "2"])
                      for n, c in ((1, "A"), (2, "B"))])
    for unit in ("teams", "pairs"):
        (issue,) = _quota(el, comp, Check(cat="ES", event="madison",
                                          unit=unit, max=1))
        assert issue.code == "quota_teams" and "TOSCANA" in issue.message


# ── specialità per atleta ───────────────────────────────────────────────────

def test_events_per_rider_is_one_of_the_rules(comp):
    """The STP limit, said in the same five words as everything else."""
    el = _list(_rider("1", cat="JU", events=[("eliminazione", True),
                                             ("madison", True),
                                             ("chilometro", True)]))
    (issue,) = _quota(el, comp, Check(cat="JU", unit="events", max=2,
                                      level="error"))
    assert issue.level == "error" and issue.code == "quota_rider"
    assert "3 specialità (max 2)" in issue.message
    assert "Eliminazione" in issue.message  # which ones, for the desk


def test_a_rule_that_says_nothing_reports_nothing(comp):
    """`max: 0` is a rule not written, and `level: off` one set aside."""
    el = _list(_rider("1", cat="ES", events=[("omnium", True)]),
               _rider("2", cat="ES", events=[("omnium", True)]))
    assert _quota(el, comp, Check(cat="ES", event="omnium", max=0)) == []
    assert _quota(el, comp, Check(cat="ES", event="omnium", max=1,
                                  level="off")) == []


def test_the_articolo_is_printed_after_the_finding(comp):
    """Where the rule comes from, on the line - so a deroga can be looked up."""
    el = _list(_rider("1", cat="ES", events=[("omnium", True)]),
               _rider("2", cat="ES", events=[("omnium", True)]))
    (issue,) = _quota(el, comp, Check(cat="ES", event="omnium", max=1,
                                      note="Art. 4 reg. TR 2026"))
    assert issue.message.endswith("(Art. 4 reg. TR 2026)")


# ── the older wording ───────────────────────────────────────────────────────

def test_the_old_quotas_block_still_holds(comp):
    """A programme written before `checks:` says the same thing, in fewer words."""
    el = _list(_rider("1", cat="ES", events=[("omnium", True)]),
               _rider("2", cat="ES", events=[("omnium", True)]))
    old = replace(comp, checks=[], quotas=Quotas(max_per_region={"omnium": 1}))
    (issue,) = [i for i in validate_entries(el, old)
                if i.code.startswith("quota")]
    assert "2 atleti (max 1)" in issue.message


def test_a_rule_wins_over_the_old_field_about_the_same_thing(comp):
    """Both blocks in one file - the year before's, and this year's.

    The Controlli tab writes `checks:`; the `quotas:` above it is what was
    there. The same regione must not be reported twice, once per wording.
    """
    el = _list(_rider("1", cat="ES", events=[("omnium", True)]),
               _rider("2", cat="ES", events=[("omnium", True)]))
    comp = replace(comp, quotas=Quotas(max_per_region={"omnium": 1}),
                   checks=[Check(event="omnium", max=9)])
    assert [i for i in validate_entries(el, comp)
            if i.code.startswith("quota")] == []


# ── the competition this was written for ────────────────────────────────────

def test_tr26_states_article_4(comp):
    """Art. 4 of the regolamento, as eleven rows of the programme."""
    path = COMPETITIONS / "TR26" / "programme.yaml"
    if not path.exists():
        pytest.skip("no TR26 folder")
    tr = load_competition(path)
    rules = {(c.cat, c.event): c for c in tr.checks}
    assert rules[("ES", "omnium")].max == 2
    assert rules[("*", "madison")].unit == "pairs"
    assert rules[("*", "madison")].max == 1
    assert rules[("JU", "chilometro")].max == 1
    assert rules[("DJ", "chilometro")].max == 2
    assert rules[("AL", "ins_squadre")].unit == "teams"
    # "Partecipazione libera alle singole Specialità": no limit on how many
    assert tr.max_events("JU") is None
    assert all(c.note for c in tr.checks)


# ── the grid that edits them ────────────────────────────────────────────────

def test_the_controlli_grid_round_trips_the_rules():
    """What the tab shows is the file, and what it reads back is the file.

    The grid shows the words the regolamento is written in - *coppie*, *per
    rappresentativa* - and the file holds codes. The two directions are one
    table (`ui.pages.programme._check_options`), and a rule that came out of it
    changed would be a programme edited by being looked at.
    """
    import pandas as pd

    from ui.pages import programme as PG

    path = COMPETITIONS / "TR26" / "programme.yaml"
    if not path.exists():
        pytest.skip("no TR26 folder")
    tr = load_competition(path)
    opts = PG._check_options(tr)
    rows = PG._check_rows(tr, opts)
    assert rows[0]["unit"] == "atleti" and rows[0]["per"] == "rappresentativa"
    assert PG._read_checks(pd.DataFrame(rows), opts) == tr.checks
    # a row added and left empty is not a rule of zero
    blank = {k: None for k in rows[0]}
    assert PG._read_checks(pd.DataFrame(rows + [blank]), opts) == tr.checks
