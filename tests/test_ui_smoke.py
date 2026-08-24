"""Headless runs of the Streamlit pages: they must render without exceptions."""

import re
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import EXAMPLE_PROGRAMME, programme_path
from core.i18n import catalogue

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app(tmp_path, monkeypatch, iscritti_path):
    """The real CITA26 programme in a throwaway data directory."""
    data = tmp_path / "competitions"
    (data / "CITA26").mkdir(parents=True)
    # copied under the name the assertions below use, wherever it came from
    shutil.copy(programme_path(), data / "CITA26")
    monkeypatch.setenv("COMMISSAIRE_TRACK_DATA", str(data))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    return at


def _key_of(shown):
    """The catalogue key behind a word a picker shows.

    Every picker whose options are fixed holds a *key* and formats it through
    `ui` when it draws itself, so the pick survives a change of language
    (`core.i18n`); AppTest reports the formatted option and takes the value, so
    a test that says which option it means the way the jury does - by reading
    it - has to come back the other way. Where two keys carry the same word the
    later one wins: the earlier is a heading elsewhere on the page.
    """
    return {v: k for k, v in catalogue().UI.items()}[shown]


def _pick(widget, name):
    """Set a picker by the word it shows, whatever it holds underneath."""
    shown = next(o for o in widget.options if o.endswith(name))
    return widget.set_value(_key_of(shown))


def _page(app, name):
    """Open a page by name, whatever icon its label carries.

    The sidebar picker is an `st.radio` styled into a nav (`ui/style.py`), so
    every label is "🏁 Gare", "✓ Verifica", ... - matched here on the word.
    """
    return _pick(app.sidebar.radio[0], name).run()


def test_without_an_entry_list_the_menu_offers_what_can_be_done(app):
    """The five pages about the riders are not on the menu until there are some.

    They used to be, and every one of them opened on the same line of apology.
    What is left is what can actually be worked on with an empty folder: the
    programme - which is where the elenco iscritti is built - and Impostazioni.
    """
    assert not app.exception
    # the competition is set in Impostazioni, not picked again on every page
    assert not app.sidebar.selectbox
    assert any("CAMPIONATI ITALIANI GIOVANILI SU PISTA 2026" in m.value
               and "Velodromo delle Cascine" in m.value
               for m in app.sidebar.markdown)
    pages = [o for o in app.sidebar.radio[0].options]
    assert [p.split(" ", 1)[-1] for p in pages] == ["Programma", "Impostazioni"]
    assert any("elenco iscritti" in c.value for c in app.sidebar.caption)


def test_the_app_carries_the_document_stylesheet(app):
    """`st.html` throws away the <style> of what it renders.

    Without print.css on the page itself every preview came out as a bare
    browser table: no rule between one coppia and the next, no red second
    rider, no column widths. It has to go in through st.markdown.
    """
    css = [m.value for m in app.markdown if ".cmsr table.data" in m.value]
    assert len(css) == 1 and "group-start" in css[0]



def test_decisioni_page_is_the_register_of_what_was_decided(app):
    """The secretary's log, read back: it works before anything is imported.

    Nothing is composed here any more - a decision is written in the race it
    was taken in (see `_decision_panel` in Gare).
    """
    _seed_entries(app)
    _page(app, "Decisioni")
    assert not app.exception
    assert any("Nessuna decisione" in i.value for i in app.info)
    assert not [t for t in app.text_area if t.key == "dec_text"]


def _file(store, **kw):
    from core import decisions as D
    return D.add(store, D.Decision(**kw))


def test_the_register_lists_and_filters_what_was_filed(app):
    _seed_entries(app)
    from core.store import open_competition

    store = open_competition("CITA26")
    _file(store, cat="AL", event="velocita", round_key="Quarti", bibs="1",
          penalty="A", text="ammonizione al dorsale 1")
    _file(store, cat="AL", event="velocita", text="Reclamo respinto (3.2.026).")
    _page(app, "Decisioni")
    assert not app.exception
    assert any("Decisioni registrate (2)" in s.value for s in app.subheader)
    assert any("Reclamo respinto" in m.value for m in app.markdown)

    # the picker that leaves the ammonizioni out of what gets printed: they
    # are the many, and hardly ever the ones to publish
    kinds = app.multiselect(key="dec_f_kinds")
    # the page opens on the ammonizioni and the squalifiche: a retrocessione is
    # already printed on the sheet of the race it was given in
    assert kinds.value == ["A", "D"]
    kinds.set_value(["C", "D"]).run()
    assert any("Decisioni registrate (1)" in s.value for s in app.subheader)
    assert not any("ammonizione al dorsale" in m.value for m in app.markdown)
    # ... and what the picker does not offer is not filtered by it: the reclamo
    # respinto is a nota, and it stays
    assert any("Reclamo respinto" in m.value for m in app.markdown)

    # and the pickers, which read the same log
    app.multiselect(key="dec_f_kinds").set_value(["A", "C", "D"]).run()
    app.selectbox(key="dec_f_event").set_value("keirin").run()
    assert any("Decisioni registrate (0)" in s.value for s in app.subheader)


def test_a_filed_decision_can_be_corrected_or_deleted(app):
    """Every column of the row is correctable where the decision is shown."""
    _seed_entries(app)
    from core import decisions as D
    from core.store import open_competition

    _file(open_competition("CITA26"), text="Ammonizione al dorsale 4.")
    _page(app, "Decisioni")

    app.text_area(key="et_reg_1").set_value("Ammonizione al dorsale 5.").run()
    app.text_input(key="eb_reg_1").set_value("5").run()
    app.selectbox(key="ec_reg_1").set_value("A").run()
    app.selectbox(key="er_reg_1").set_value("16").run()
    app.button(key="eu_reg_1").click().run()
    assert not app.exception
    store = open_competition("CITA26")
    d = D.load(store)[0]
    assert (d.text, d.bibs, d.code) == ("Ammonizione al dorsale 5.", "5", "A16")

    app.button(key="ed_reg_1").click().run()
    assert not app.exception
    assert D.load(store) == []
    assert any("Nessuna decisione" in i.value for i in app.info)


def test_the_register_recaps_a_specialita_fase_by_fase(app):
    """With a categoria and a specialità chosen, what was decided in each fase.

    Across the whole competition the recap would be the register in a worse
    order, so it only appears once the page is about one specialità.
    """
    _seed_entries(app)
    from core.store import open_competition

    store = open_competition("CITA26")
    _file(store, cat="AL", event="velocita", round_key="Turno 1", bibs="1",
          penalty="A", reason="6", text="AL 1: AMMONIZIONE (A) per la corsia.")
    _file(store, cat="AL", event="velocita", round_key="Quarti", bibs="2",
          penalty="C", reason="2", text="AL 2: RETROCESSIONE (C) per la fascia.")
    _page(app, "Decisioni")
    assert not any(s.value == "Decisioni della specialità" for s in app.subheader)

    app.selectbox(key="dec_f_cat").set_value("AL").run()
    app.selectbox(key="dec_f_event").set_value("velocita").run()
    assert not app.exception
    assert any(s.value == "Decisioni della specialità" for s in app.subheader)
    captions = [c.value for c in app.caption]
    assert "Turno 1 (1)" in captions and "Quarti (1)" in captions
    assert any("A6" in m.value for m in app.markdown)


def test_changing_the_category_clears_an_event_it_does_not_contest(app):
    """The specialità offered depend on the categoria above them.

    Picked for the Allievi and then switched to the Esordienti, the keirin is
    not a specialità of the new categoria: the picker comes back empty rather
    than naming a race that does not exist (`state.sticky_select`).
    """
    _seed_entries(app)
    from core.config import load_competition
    from core.store import competitions_root

    comp = load_competition(competitions_root() / "CITA26" / "programme.yaml")
    # the keirin: gli Allievi lo corrono, gli Esordienti no
    only_al = next(e for e in comp.events_for("AL")
                   if e not in comp.events_for("ES"))

    _page(app, "Decisioni")
    app.selectbox(key="dec_f_cat").set_value("AL").run()
    app.selectbox(key="dec_f_event").set_value(only_al).run()
    assert app.selectbox(key="dec_f_event").value == only_al

    app.selectbox(key="dec_f_cat").set_value("ES").run()
    assert not app.exception
    assert app.selectbox(key="dec_f_event").value == ""


def test_the_puis_panel_opens_on_the_categories_in_gara(app):
    _seed_entries(app)
    _page(app, "Decisioni")
    assert app.selectbox(key="dec_puis_col").value == "DA, AL, ED, ES"
    app.text_input(key="dec_puis_q").set_value("casco").run()
    assert not app.exception
    assert any("PUIS aggiornato" in c.value for c in app.caption)


def test_impostazioni_shows_the_competition_and_the_programme(app):
    _page(app, "Impostazioni")
    assert not app.exception
    assert app.selectbox(key="set_competition").value == "CITA26"
    labels = [m.label for m in app.metric]
    assert "Comunicati previsti" in labels
    assert app.metric[2].value == "140"
    # the register table is not here any more: Documenti → Registro says the
    # same and more, and prints it
    assert not any("Registro" in e.label for e in app.expander)
    # and what a squadra is has gone with the elenco iscritti: both are the
    # programme's, and both are edited in Programma → Gara
    assert not [s for s in app.selectbox if s.key == "team_group"]


def _seed_entries(app):
    """Give the competition an elenco iscritti - empty, but there.

    Five pages are off the menu until one exists (`app.NEEDS_ENTRIES`), and the
    ones about the register and the decisions need it to *exist* and nothing
    more: they are read off the programme and the journal. This is that, and it
    does not need the federation's workbook to be reachable.
    """
    from core import entries as E
    from core.store import open_competition

    E.save_import(open_competition("CITA26"), E.EntryList())
    app.run()
    return app


def _import(app, iscritti_path):
    """Put an entry list in the competition, the way the app stores one.

    Not through the page any more: the elenco is *built* in Programma → Gara
    from a file the jury uploads, and AppTest cannot drive a file uploader.
    What every test below actually needs is a competition that has one - so it
    is written where the app keeps it (`core.entries`), and the run that
    follows finds it exactly as it would after an import.
    """
    from core import entries as E
    from core.config import load_competition
    from core.store import competitions_root, open_competition

    store = open_competition("CITA26")
    comp = load_competition(competitions_root() / "CITA26" / "programme.yaml")
    E.set_source_path(store, str(iscritti_path))
    E.save_import(store, E.import_entries(iscritti_path, comp))
    app.run()
    return app


def _documents(app, group):
    """Documenti → one of its three groups.

    Partenti and Stampa were two pages until the same two batches turned out to
    live in both: they are groups of one page now, picked under the page radio.
    """
    _page(app, "Documenti")
    _pick(app.sidebar.radio(key="doc_group"), group).run()
    return app


def _open_race(app, iscritti_path, cat, event, round_key):
    from core.models import race_id

    _import(app, iscritti_path)
    _page(app, "Gare")
    app.selectbox(key="ga_cat").set_value(cat).run()
    app.selectbox(key="ga_event").set_value(event).run()
    app.selectbox(key="ga_round").set_value(round_key).run()
    assert not app.exception
    return race_id(cat, event, round_key)


def _set_sprints(app, rid, text):
    """Type every sprint at once, in the «Stringa» field under the fields."""
    box = [t for t in app.text_input if t.key.startswith(f"spr_txt_{rid}_")]
    assert box, f"no sprint string field for {rid}"
    return box[0].set_value(text).run()


def _sprint_fields(app, rid):
    """The numbered sprint fields, in order."""
    fields = [t for t in app.text_input
              if t.key.startswith(f"spr_{rid}_") and t.key.split("_")[-1].isdigit()]
    return sorted(fields, key=lambda t: int(t.key.split("_")[-1]))


def test_gare_page_runs_a_race(app, iscritti_path):
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    assert any("partenti" in c.value for c in app.caption)

    _set_sprints(app, rid, "1,2,3,4")
    assert not app.exception
    assert not app.error


def test_gare_page_reports_bad_input(app, iscritti_path):
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    _set_sprints(app, rid, "1,2,tre")
    assert not app.exception
    assert any("dorsale valido" in w.value for w in app.warning)


def test_gare_page_saves_and_reloads_a_race(app, iscritti_path):
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    _set_sprints(app, rid, "1,2,3,4")
    [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()
    assert not app.exception

    from core.store import open_competition
    state = open_competition("CITA26").load_race(rid)
    assert state is not None and state.payload["sprints"] == "1,2,3,4"


def _race_state(comp, cat, event, round_key):
    """The race as core sees it, to read its startlist and planned sprints."""
    from core import entries as E
    from core import race as R
    from core.store import open_competition

    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp)
    return R.ensure_state(store, comp, cat, event, round_key, el)


def test_sprint_fields_are_numbered(app, iscritti_path, comp):
    """Which sprint a field is must be readable, not counted out in dashes."""
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    planned = _race_state(comp, "AL", "omnium", "Corsa a Punti").n_sprint
    assert planned and planned > 1

    fields = _sprint_fields(app, rid)
    assert len(fields) == planned          # a field per planned sprint
    assert [t.label for t in fields] == [f"{i + 1}º sprint"
                                         for i in range(planned)]
    nums = [m.value for m in app.sidebar.markdown if "cmsr-n" in m.value]
    assert nums[0].endswith("1ª</div>")
    # the last planned sprint is the one scoring 10-6-4-2
    assert nums[planned - 1].endswith(f"{planned}ª (×2)</div>")
    assert not [c for c in app.sidebar.caption if ":red" in c.value or "?" in c.value]


def test_a_sprint_typed_in_its_own_field_is_kept(app, iscritti_path, comp):
    """One field, one sprint: what goes in the third field is the third sprint."""
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    bibs = [int(b) for b in _race_state(comp, "AL", "omnium",
                                        "Corsa a Punti").entrants[:4]]
    order = ",".join(str(b) for b in bibs)
    _sprint_fields(app, rid)[2].set_value(order).run()
    assert not app.exception

    # an empty sprint before a full one shifts the ones after it: said out loud
    assert any("slittano" in c.value for c in app.sidebar.caption)
    [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()

    from core.store import open_competition
    state = open_competition("CITA26").load_race(rid)
    assert state.payload["sprints"] == f"--{order}"


def test_sprint_flags_a_bad_row(app, iscritti_path, comp):
    """A wrong bib is called out under its own field, not only in the warnings."""
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    bibs = [int(b) for b in _race_state(comp, "AL", "omnium",
                                        "Corsa a Punti").entrants[:4]]
    good = ",".join(str(b) for b in bibs)
    _set_sprints(app, rid, f"{good}-999,{bibs[0]},{bibs[1]}-{bibs[0]},due")
    assert not app.exception

    notes = [c.value for c in app.sidebar.caption if c.value.startswith(":red")]
    assert notes == [":red[?999 <4]",   # not a starter, and only three finishers
                     ":red[?]"]         # unreadable; the first sprint is clean


def test_the_sprint_string_fills_the_fields(app, iscritti_path):
    """Pasting a whole race fills the fields on the same run, without a rerun."""
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    _set_sprints(app, rid, "1,2,3,4-4,3,2,1")
    assert [t.value for t in _sprint_fields(app, rid)][:2] == ["1,2,3,4",
                                                               "4,3,2,1"]
    # and the document radio has survived: the notation must not rerun the page
    assert app.radio(key=f"doc_{rid}").value is not None


def test_gare_page_handles_a_team_race(app, iscritti_path):
    _open_race(app, iscritti_path, "AL", "ins_squadre", "Qualificazioni")
    assert not app.exception
    assert any("Tempi" in s.value for s in app.subheader)


def test_heat_builder_composes_by_team(app, iscritti_path):
    """Heats are picked as teams; the bibs of each side stay editable."""
    rid = _open_race(app, iscritti_path, "AL", "ins_squadre", "Qualificazioni")
    app.button(key=f"fill_{rid}").click().run()
    assert not app.exception

    note = [c.value for c in app.caption if c.value.startswith("Notazione")]
    assert note and "-" in note[0] and "/" in note[0]

    bibs = [t for t in app.text_input if t.key.startswith(f"hb_{rid}_")]
    assert bibs and all("," in t.value for t in bibs)  # four riders a side

    from core.parse import parse_heats
    heats = parse_heats(note[0].split("`")[1])
    assert len(heats) == 4 and all(len(h) == 2 for h in heats)  # 8 teams

    # Salva sits in the sidebar, which is drawn before the grid: the composed
    # heats must still be the ones that reach the disk
    [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()
    from core.store import open_competition
    state = open_competition("CITA26").load_race(rid)
    assert parse_heats(state.payload["heats"]) == heats


def test_individual_pursuit_pairs_the_field_and_seeds_the_finals(
        app, iscritti_path):
    """The inseguimento individuale is composed and seeded like the one a squadre.

    Its grid opens on as many batterie as the field asks for, the odd rider
    rides the 1ª alone, and the finals - once loaded - carry no button that
    would overwrite them with the entry list.
    """
    from core.parse import parse_heats

    rid = _open_race(app, iscritti_path, "AL", "ins_individuale",
                     "Qualificazioni")
    n = int(app.number_input(key=f"nh_{rid}").value)
    entered = int(re.search(r"(\d+) partenti",
                            " ".join(c.value for c in app.caption)).group(1))
    assert n == -(-entered // 2)          # two a batteria, the odd one alone

    app.button(key=f"fill_{rid}").click().run()
    assert not app.exception
    note = [c.value for c in app.caption if c.value.startswith("Notazione")][0]
    heats = parse_heats(note.split("`")[1])
    assert len(heats) == n
    if entered % 2:
        assert len(heats[0]) == 1     # whoever rides alone opens the round
        assert not any("numero dispari" in w.value for w in app.warning)

    # the finals are seeded from the qualification, never refilled from the
    # entry list: no «Riempi» button there
    fid = _open_race(app, iscritti_path, "AL", "ins_individuale", "Finali")
    assert not app.exception
    assert any("Composizione batterie" in e.label for e in app.expander)
    assert not any(b.key == f"fill_{fid}" for b in app.button)


def test_a_pursuit_can_be_ridden_one_rider_at_a_time(app, iscritti_path):
    """The jury's call at the track: batterie, or an ordine di partenza.

    An inseguimento individuale is normally two at a time, one per straight.
    Moved to one at a time it becomes a start order like the velocità a
    squadre - and what was already composed keeps its order, one per line.
    """
    from core.parse import parse_heats
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "AL", "ins_individuale",
                     "Qualificazioni")
    app.button(key=f"fill_{rid}").click().run()
    paired = parse_heats([c.value for c in app.caption
                          if c.value.startswith("Notazione")][0].split("`")[1])
    assert any(len(h) == 2 for h in paired)

    app.radio(key=f"solo_{rid}").set_value(True).run()
    assert not app.exception
    assert any("Composizione ordine di partenza" in e.label
               for e in app.expander)
    note = [c.value for c in app.caption if c.value.startswith("Notazione")][0]
    solo = parse_heats(note.split("`")[1])
    # same riders, same order, one per start
    assert all(len(h) == 1 for h in solo)
    assert [b for h in solo for b in h] == [b for h in paired for b in h]

    # and it is the race that carries the choice, so the sheets say what was
    # ridden: saved with it, and read back one per start
    [b for b in app.button if b.key == f"savegrid_{rid}"][0].click().run()
    state = open_competition("CITA26").load_race(rid)
    assert state.payload["solo_starts"] is True
    assert parse_heats(state.payload["heats"]) == solo

    # back to batterie: the pairs come back, nobody is lost on the way
    app.radio(key=f"solo_{rid}").set_value(False).run()
    assert not app.exception
    note = [c.value for c in app.caption if c.value.startswith("Notazione")][0]
    again = parse_heats(note.split("`")[1])
    assert again == paired


def test_the_starts_picker_is_not_offered_on_a_finals_round(app, iscritti_path):
    """A finals round is two against two whatever anybody would pick."""
    fid = _open_race(app, iscritti_path, "AL", "ins_individuale", "Finali")
    assert not app.exception
    assert not any(r.key == f"solo_{fid}" for r in app.radio)


def test_a_seeded_final_can_be_closed_without_being_ridden(app, iscritti_path):
    """Under the times: disputata, pari merito, or on the qualifying times.

    One picker per final, and picking *Pari merito* on the 1°/2° leaves the
    first place empty - two seconde, and no champion on the sheet.
    """
    import os

    from core import race as R
    from core.config import load_competition
    from core.entries import effective_entries
    from core.parse import parse_time
    from core.store import Store
    from ui.pages.races import _load_finals

    _import(app, iscritti_path)
    store = Store(Path(os.environ["COMMISSAIRE_TRACK_DATA"]) / "CITA26")
    comp = load_competition(programme_path())
    el, _ = effective_entries(store, comp)

    # a qualification ridden and filed, then carried into the finals: the page
    # under test is the finals one, and this is what reaches it
    qual = R.ensure_state(store, comp, "AL", "ins_squadre", "Qualificazioni", el)
    qual.payload["times"] = {k: parse_time(f"3:5{i},000")
                             for i, k in enumerate(qual.entrants[:4])}
    store.save_race(qual)
    _load_finals(qual, R.classify(qual, el, comp), el, comp, store, "Finali")

    fid = _open_race(app, iscritti_path, "AL", "ins_squadre", "Finali")
    assert not app.exception
    picks = {s.key: s for s in app.selectbox
             if s.key.startswith(f"fin_{fid}_")}
    assert set(picks) == {f"fin_{fid}_1", f"fin_{fid}_3"}
    assert list(picks[f"fin_{fid}_3"].options) == \
        ["Disputata", "Pari merito (4°)", "Tempi qualifiche"]

    app = picks[f"fin_{fid}_1"].set_value("tied").run()
    assert not app.exception
    assert any("2° a pari merito" in c.value for c in app.caption)
    # no first place on the sheet, so no champion named on it
    assert "CAMPIONE" not in "".join(h.body for h in app.get("html"))


def test_empty_finals_warn_and_stay_batterie(app, iscritti_path):
    """Finali opened before *Carica finali*: a warning, and a heat grid.

    A velocità a squadre qualifies one squadra at a time, so its qualifying
    grid is an ordine di partenza - but the finals are two against two, seeded
    or not, and the DA finals opened as a start order.
    """
    _open_race(app, iscritti_path, "DA", "vel_squadre", "Finali")
    assert not app.exception
    assert any("non ha ancora tempi salvati" in w.value for w in app.warning)
    assert any("Composizione batterie" in e.label for e in app.expander)
    assert not any("ordine di partenza" in e.label.lower()
                   for e in app.expander)

    # the qualifying round is where the start order is composed
    _open_race(app, iscritti_path, "DA", "vel_squadre", "Qualificazioni")
    assert not any("tempi salvati" in w.value for w in app.warning)
    assert any("Composizione ordine di partenza" in e.label
               for e in app.expander)


def test_the_flying_200_is_a_start_order(app, iscritti_path):
    """The 200 m lanciati are ridden one at a time, like a velocità a squadre."""
    _open_race(app, iscritti_path, "AL", "velocita", "Qualificazioni")
    assert not app.exception
    assert any("Composizione ordine di partenza" in e.label
               for e in app.expander)
    assert any("tutti gli atleti" in (b.help or "") for b in app.button)


def test_partenti_page_prints(app, iscritti_path):
    _import(app, iscritti_path)
    _documents(app, "Elenchi iscritti")
    assert not app.exception
    _pick(app.radio(key="pa_mode"), "Per specialità").run()
    assert not app.exception
    _pick(app.radio(key="pa_mode"),
          "Tutte le specialità di una categoria").run()
    assert not app.exception


def test_quick_print_writes_one_entry_list_per_category(app, iscritti_path):
    _import(app, iscritti_path)
    _documents(app, "Elenchi iscritti")
    [b for b in app.button if "Stampa tutti gli iscritti" in b.label][0].click().run()
    assert not app.exception

    from core.store import open_competition
    out = open_competition("CITA26").out_dir
    names = sorted(p.name for p in out.iterdir() if "partenti" in p.name)
    assert len(names) == 4  # ES, ED, AL, DA
    assert all(n[:3].isdigit() for n in names)  # numbered from the register
    assert all(n.split("_")[1][:2].isupper()
               for n in names)  # NNN_CAT_partenti, category uppercase


def test_import_then_edit_entry_list(app, iscritti_path):
    # with an entry list the pages about the riders are on the menu, and say
    # how many there are
    _import(app, iscritti_path)
    assert not app.exception

    _page(app, "Impostazioni")
    # the file in force and what the last import found in it - the *building*
    # of the elenco is in Programma → Gara, this is what is left as a setting
    assert any("Ultimo import" in c.value and "atleti" in c.value
               for c in app.caption)

    _page(app, "Verifica")
    # the counters, the tabella specialità and the validation panel
    assert [m.label for m in app.metric] == ["Atleti", "Verificati",
                                             "Squadre", "Coppie"]
    assert any("Tabella specialità" in s.value for s in app.subheader)
    assert app.dataframe
    assert any("da risolvere" in e.label for e in app.expander)

    # filtering the grid by category and event must not blow up
    app.selectbox(key="ver_event").set_value("Madison").run()
    assert not app.exception
    app.multiselect(key="ver_cats").set_value(["AL"]).run()
    assert not app.exception

    # before any tick, everyone is still to be verified and nobody is filtered out
    _pick(app.selectbox(key="ver_state"), "Da verificare").run()
    assert not app.exception
    assert any("Segna verificati" in b.label for b in app.button)
    _pick(app.selectbox(key="ver_state"), "Verificati").run()
    assert not app.exception
    assert any("Nessun atleta" in i.value for i in app.info)


def test_the_overlay_switch_sends_the_edits_into_the_workbook(app,
                                                              iscritti_path):
    """Off, Verifica writes the file itself instead of recording a patch."""
    from core import entries as E
    from core.store import open_competition

    _import(app, iscritti_path)
    _page(app, "Verifica")
    [b for b in app.button if "Segna verificati" in b.label][0].click().run()
    assert not app.exception

    try:
        _page(app, "Impostazioni")
        app.toggle(key="use_overlay").set_value(False).run()
        assert not app.exception
        assert E.overlay_on(open_competition("CITA26")) is False

        _page(app, "Verifica")
        assert not app.exception
        # the ticks are not lost, they are not applied: the page says where an
        # edit goes now, and offers to save it there
        assert any(str(iscritti_path.name) in i.value for i in app.info)
        assert next(m for m in app.metric if m.label == "Verificati").value == "0"
        assert any("Salva nel file" in b.label for b in app.button)
        # ticking is still offered here, because this file has the two columns
        # (`entries.check_in`): the tick goes into the workbook, not the overlay
        from core.config import load_competition
        offered = bool([b for b in app.button if "Segna verificati" in b.label])
        assert offered is bool(E.check_in_columns(load_competition(
            programme_path())))
    finally:
        # the competition folder is the real one: a failure here must not leave
        # the switch off
        E.set_overlay_on(open_competition("CITA26"), True)

    _page(app, "Impostazioni")
    assert app.toggle(key="use_overlay").value is True
    _page(app, "Verifica")
    assert next(m for m in app.metric if m.label == "Verificati").value != "0"


def test_bulk_verification_marks_the_filtered_riders(app, iscritti_path):
    _import(app, iscritti_path)
    _page(app, "Verifica")
    app.multiselect(key="ver_cats").set_value(["ED"]).run()
    [b for b in app.button if "Segna verificati" in b.label][0].click().run()
    assert not app.exception

    from core.entries import effective_entries, check_in_progress
    from core.store import open_competition
    from core.config import load_competition
    comp = load_competition(programme_path())
    el, _ = effective_entries(open_competition("CITA26"), comp)
    assert check_in_progress(el, "ED").done is True
    assert check_in_progress(el, "AL").verificati == 0  # only the filtered ones


def test_entry_grid_edits_become_patches(iscritti_path, comp):
    """The grid diff is tested directly: AppTest cannot drive a data_editor."""
    import pandas as pd

    from core.config import EVENT_ENTRY_LIST

    from core.entries import import_master
    from ui.pages.check_in import _diff

    el = import_master(iscritti_path, comp)
    rider = next(r for r in el.by_cat("AL") if "madison" in r.events)
    events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]

    before = pd.DataFrame([{"key": rider.key, "Dors.": rider.bib,
                            "Cognome": rider.last_name, "Nome": rider.first_name,
                            "Regione": rider.region, "Società": rider.club,
                            "Cod. Soc.": rider.club_code,
                            "Ver.": False, "NP": False, "UCI ID": rider.uci_id,
                            "Cat.": rider.cat,
                            **{comp.event(s).short:
                                (rider.events[s].flag
                                 if s in rider.events else "")
                               for s in events}}])
    after = before.copy()
    after.at[0, "Ver."] = True
    after.at[0, "NP"] = True
    after.at[0, "Dors."] = 500
    after.at[0, "Madison"] = "2"
    after.at[0, "Keirin"] = ""

    patches = _diff(before, after, comp.event_headers(events),
                    "verifica licenze")
    ops = {(p.op, p.field) for p in patches}
    assert ("set_checked_in", "") in ops
    assert ("set_not_starting", "") in ops
    assert ("set_field", "bib") in ops
    assert ("set_event", "madison") in ops
    assert all(p.reason == "verifica licenze" for p in patches)
    assert all(p.target == rider.key for p in patches)

    from core.entries import apply_overlay
    assert apply_overlay(el, patches, comp) == []  # none stale
    assert el.riders[rider.key].checked_in is True
    assert el.riders[rider.key].not_starting is True
    assert el.riders[rider.key].bib == 500
    assert el.riders[rider.key].events["madison"].pair == 2


def test_stampa_page_batches(app, iscritti_path):
    _import(app, iscritti_path)
    _documents(app, "Serie di documenti")
    assert not app.exception
    assert any("documenti" in c.value for c in app.caption)

    _pick(app.sidebar.radio(key="stp_mode"), "Per specialità").run()
    assert not app.exception
    _pick(app.sidebar.radio(key="stp_mode"), "Per giornata").run()
    assert not app.exception


def test_stampa_page_shows_the_register(app, iscritti_path):
    _import(app, iscritti_path)
    _documents(app, "Registro comunicati")
    assert not app.exception
    assert [m.value for m in app.metric][:1] == ["140"]
    assert any("registro" in b.label.lower() for b in app.button)


def test_documenti_prints_one_recap_per_squadra(app, iscritti_path):
    """The pile a team manager is handed: one sheet each, in one PDF."""
    _import(app, iscritti_path)
    _documents(app, "Serie di documenti")
    _pick(app.sidebar.radio(key="stp_mode"), "Per squadra").run()
    assert not app.exception

    picker = app.sidebar.selectbox(key="stp_team")
    regions = [o for o in picker.options if o != "(tutte)"]
    assert len(regions) > 5                      # the rappresentative in gara
    # "(tutte)" is the default: the whole pile, one page per squadra
    assert picker.value == "(tutte)"
    assert any(f"{len(regions)} documenti" in c.value for c in app.caption)

    picker.set_value(regions[0]).run()
    assert any("1 documento" in c.value for c in app.caption)
    sheet = _preview(app)
    assert regions[0] in sheet and "RIEPILOGO ISCRITTI" in sheet
    # the kinds cannot be picked for this batch: a riepilogo is one sheet
    assert app.sidebar.multiselect(key="stp_docs").disabled


def test_documenti_prints_the_tabella_specialita(app, iscritti_path):
    """The same table Verifica shows, on one sheet, for the briefing."""
    _import(app, iscritti_path)
    _documents(app, "Serie di documenti")
    _pick(app.sidebar.radio(key="stp_mode"), "Tabella specialità").run()
    assert not app.exception
    assert any("1 documento" in c.value for c in app.caption)

    sheet = _preview(app)
    assert "TABELLA SPECIALITÀ" in sheet and "Totale" in sheet
    # nothing to pick: the sheet is printed, not composed
    assert app.sidebar.multiselect(key="stp_docs").disabled


def test_the_register_is_read_off_the_programme_and_not_off_the_riders(app):
    """It reads the programme and the comunicati: an empty elenco is enough.

    Documenti is on the menu once there is an elenco at all (`app`), and this
    half of it never looks at a rider: it says what has been filed and what is
    still to file.
    """
    _seed_entries(app)
    _documents(app, "Registro comunicati")
    assert not app.exception
    assert [m.value for m in app.metric][:1] == ["140"]


def test_documenti_keeps_both_halves_of_the_old_pages(app, iscritti_path):
    """One page, three groups: the entry-list composer and the batches.

    They print the same `entry_list`, which is why they were merged; what tells
    them apart is that the composer carries the number, the note and the
    filters of the sheet that goes out.
    """
    _import(app, iscritti_path)
    _documents(app, "Elenchi iscritti")
    assert app.text_input(key="pa_com")                      # the number
    assert any(t.key.startswith("pa_dec_") for t in app.text_area)   # the note
    assert app.checkbox(key="pa_ver")                        # solo verificati

    _documents(app, "Serie di documenti")
    assert app.sidebar.radio(key="stp_mode").value == _key_of("Per categoria")
    assert not app.exception


def test_settings_page_changes_the_output_folder(app, tmp_path):
    from core.store import open_competition

    _page(app, "Impostazioni")
    assert not app.exception
    assert "Cartella dei comunicati" in [s.value for s in app.subheader]

    store = open_competition("CITA26")
    assert app.text_input(key="out_dir_input").value == str(store.out_dir)

    dest = tmp_path / "Comunicati"
    app.text_input(key="out_dir_input").set_value(str(dest)).run()
    [b for b in app.button if b.label == "Salva cartella"][0].click().run()
    assert not app.exception
    assert open_competition("CITA26").out_dir == dest

    [b for b in app.button if b.label == "Ripristina predefinita"][0].click().run()
    assert open_competition("CITA26").out_dir == store.root / "out"


def test_settings_page_refuses_an_unwritable_folder(app):
    _page(app, "Impostazioni")
    app.text_input(key="out_dir_input").set_value("/proc/non-scrivibile").run()
    assert not app.exception
    assert any("Permesso negato" in e.value or "esiste" in e.value
               for e in app.error)
    save = [b for b in app.button if b.label == "Salva cartella"][0]
    assert save.disabled


def test_settings_page_changes_the_letterhead(app, tmp_path):
    """Testata e piè si cambiano qui: un nuovo velodromo è un SVG, non codice."""
    from core.store import open_competition

    _page(app, "Impostazioni")
    assert not app.exception
    # The page runs from what the app is working on down to what destroys work:
    # the folder a comunicato lands in, how a sheet looks, what a specialità is
    # and the lines its sheets open on, the backups - and only last the one
    # control here that deletes a race.
    #
    # Nothing about *this* competition is on it any more: the elenco iscritti
    # and what a squadra is belong to the programme and are edited there
    # (Programma → Gara). What is left holds for the installation.
    subs = [s.value for s in app.subheader]
    assert subs == ["Cartella dei comunicati", "Aspetto dei comunicati",
                    "Specialità", "Righe dei comunicati", "Backup",
                    "Azzera una gara"]
    # the three things that decide how a sheet looks are one section, not two:
    # the letterhead was on the page while the signature was hidden behind an
    # expander called «avanzate», which is not a different kind of choice
    boxes = [e.label for e in app.expander]
    assert boxes[:3] == ["Testata e piè di pagina", "Firma", "Nome"]

    banner = tmp_path / "head_2027.svg"
    banner.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    app.text_input(key="brand_header_img").set_value(str(banner)).run()
    [b for b in app.button if b.label == "Salva testata"][0].click().run()
    assert not app.exception
    from ui import state
    assert open_competition("CITA26").settings["header_img"] == str(banner)
    assert state.competition("CITA26").branding.header_img == str(banner)


def test_madison_pairing_page_composes_the_event(app, iscritti_path):
    """The composition round: a number per coppia, a batteria per number."""
    rid = _open_race(app, iscritti_path, "ES", "madison", "Composizione coppie")
    assert not app.exception
    assert any("coppie" in c.value and "batterie" in c.value for c in app.caption)

    # deal the coppie into the two batterie, then file the composition
    [b for b in app.button if "Distribuisci" in b.label][0].click().run()
    [b for b in app.button if "Salva composizione" in b.label][0].click().run()
    assert not app.exception

    from core.store import open_competition
    from core import race as R
    store = open_competition("CITA26")
    state = store.load_race(rid)
    assert state is not None
    assert sorted(set(state.payload[R.PAIR_HEATS].values())) == [1, 2]
    assert len(set(state.payload[R.PAIR_NUMBERS].values())) == len(state.entrants)


def test_madison_batteria_starts_only_its_own_coppie(app, iscritti_path):
    _open_race(app, iscritti_path, "ES", "madison", "Composizione coppie")
    [b for b in app.button if "Distribuisci" in b.label][0].click().run()
    [b for b in app.button if "Salva composizione" in b.label][0].click().run()

    _open_race(app, iscritti_path, "ES", "madison", "Qualificazioni Batteria 1")
    assert not app.exception
    head = [c.value for c in app.caption if "partenti" in c.value]
    assert head and head[0].split()[0].isdigit()
    # and the start order announces the cut of 3.2.157 by itself
    assert any("Non si qualificano per la finale le ultime 2 coppie "
               "tra le partenti"
               in t.value for t in app.text_area)


def test_madison_heat_results_load_the_final(app, iscritti_path):
    """The results of a batteria send its qualifiers through, from that sheet."""
    from core import race as R
    from core.store import open_competition

    _open_race(app, iscritti_path, "ES", "madison", "Composizione coppie")
    [b for b in app.button if "Distribuisci" in b.label][0].click().run()
    [b for b in app.button if "Salva composizione" in b.label][0].click().run()

    store = open_competition("CITA26")
    for key in ("Qualificazioni Batteria 1", "Qualificazioni Batteria 2"):
        rid = _open_race(app, iscritti_path, "ES", "madison", key)
        # every coppia of the batteria takes a sprint, in startlist order:
        # the numbers on the page are the ones the composition assigned
        state = store.load_race(rid) or R.RaceState(race_id=rid, cat="ES",
                                                    event="madison")
        _set_sprints(app, rid,
                     ",".join(str(n) for n in _pair_numbers(app, state)))
        [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()
        assert not app.exception

    rid = _open_race(app, iscritti_path, "ES", "madison",
                     "Qualificazioni Batteria 2")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    [b for b in app.button if "Carica in finale" in b.label][0].click().run()
    assert not app.exception
    assert any("coppie in finale" in s.value for s in app.success)

    final = store.load_race(R.race_key("ES", "madison", "Finale"))
    assert final is not None and final.payload[R.QUALIFIED]
    assert final.entrants == final.payload[R.QUALIFIED]
    # two out of each batteria, as the composition says
    everyone = store.load_race(R.race_key("ES", "madison",
                                          "Composizione coppie")).entrants
    assert len(final.entrants) == len(everyone) - 4


def test_omnium_composition_splits_the_field_and_loads_the_prove(app,
                                                                iscritti_path):
    """The omnium composed on screen: two batterie, then the four prove.

    Same page as the madison and the same button, without the numbers: the
    riders keep their dorsale and the only decision is the batteria.
    """
    from core import race as R
    from core.formats import omnium as O
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "ES", "omnium",
                     "Composizione batterie")
    assert not app.exception
    assert any("atleti" in c.value and "batterie" in c.value
               for c in app.caption)
    [b for b in app.button if "Distribuisci" in b.label][0].click().run()
    [b for b in app.button if "Salva composizione" in b.label][0].click().run()
    assert not app.exception

    store = open_competition("CITA26")
    setup = store.load_race(rid)
    assert sorted(set(setup.payload[R.PAIR_HEATS].values())) == [1, 2]
    # nothing to number: the dorsale is the number
    assert R.PAIR_NUMBERS not in setup.payload

    heats = setup.payload[R.PAIR_HEATS]
    for n, key in R.heat_rounds(_comp(app), "ES", "omnium"):
        rid = _open_race(app, iscritti_path, "ES", "omnium", key)
        # the batteria starts its own riders and nobody else, by dorsale
        entrants = sorted((k for k in setup.entrants if heats.get(k) == n),
                          key=int)
        assert 0 < len(entrants) < len(setup.entrants)
        _set_sprints(app, rid, ",".join(entrants))
        [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()
        assert not app.exception
        assert store.load_race(rid).entrants == entrants

    rid = _open_race(app, iscritti_path, "ES", "omnium",
                     "Qualificazioni Batteria 2")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    [b for b in app.button if "Carica nelle prove" in b.label][0].click().run()
    assert not app.exception
    assert any("ammessi" in s.value for s in app.success)

    for name in O.ROUNDS:
        prova = store.load_race(R.race_key("ES", "omnium", name))
        assert prova is not None and prova.payload[R.QUALIFIED]
        assert prova.entrants == prova.payload[R.QUALIFIED]
    # five out of each batteria, as the programme says
    scratch = store.load_race(R.race_key("ES", "omnium", O.SCRATCH))
    assert len(scratch.entrants) == len(setup.entrants) - 10


def _pair_numbers(app, state) -> list[int]:
    """The numbers the coppie of one saved heat wear."""
    from core import race as R
    from core.store import open_competition
    store = open_competition("CITA26")
    pr = R.pairing(store, _comp(app), state.cat, state.event)
    return [pr.number(k) for k in state.entrants]


def _comp(app):
    from ui import state
    return state.competition("CITA26")


def test_every_pick_of_the_fase_dropdown_lands(app, iscritti_path):
    """One pick, one race: the picker used to keep every other choice only.

    `index=` was recomputed from the race last saved, so its default moved with
    the jury's own pick and Streamlit re-initialised the widget on the run
    after - a phase selected once stayed on the previous one.
    """
    _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    for round_key in ("Tempo Race", "Eliminazione", "Corsa a Punti",
                      "Scratch", "Qualificazioni Batteria 2"):
        app.selectbox(key="ga_round").set_value(round_key).run()
        assert app.selectbox(key="ga_round").value == round_key
        assert round_key in app.header[0].value


def test_saving_a_pdf_opens_it_without_a_button(app, iscritti_path):
    """One click: the sheet is filed and the tab opens by itself."""
    _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    [b for b in app.button if b.label == "Salva PDF"][0].click().run()
    assert not app.exception
    assert any("Salvato" in t.value for t in app.toast)
    assert not [b for b in app.button if b.label.startswith("Apri")]

    from core.store import open_competition
    files = list(open_competition("CITA26").out_dir.iterdir())
    assert files, "il documento deve restare nella cartella dei comunicati"


def test_screen_and_print_body_sizes_are_separate(app, iscritti_path):
    """The speaker reads the preview across a desk; the sheet is read on paper."""
    rid = _open_race(app, iscritti_path, "ES", "madison", "Finale")
    labels = {s.label: s.value for s in app.sidebar.slider}
    assert labels["Corpo tabella .pdf"] == 9        # an ordine di partenza
    assert labels["Corpo tabella a schermo"] == 11

    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    labels = {s.label: s.value for s in app.sidebar.slider}
    assert labels["Corpo tabella .pdf"] == 9        # as every sheet but one
    assert labels["Corpo tabella a schermo"] == 11  # unchanged by the document


def test_the_last_sprint_is_called_out_over_the_preview(app, iscritti_path):
    """The banner the speaker reads: only on screen, never on the sheet."""
    rid = _open_race(app, iscritti_path, "ES", "madison", "Finale")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _set_sprints(app, rid, "1,2,3,4-4,3,2,1")
    assert not app.exception

    banner = [m.value for m in app.markdown if "volata" in m.value]
    assert banner and "2ª volata" in banner[0]
    # the numbers as they were called, the scoring four in bold
    assert "<b>4</b> - <b>3</b> - <b>2</b> - <b>1</b>" in banner[0]

    # the startlist has no sprint to call
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert not [m.value for m in app.markdown if "volata" in m.value]


def test_the_page_reopens_on_the_sheet_it_was_left_on(app, iscritti_path):
    """Gare comes back where it was: same race, same document.

    Streamlit forgets the radio the moment another page is drawn, so without
    this the jury lands on the ordine di partenza of a race already ridden.
    """
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _page(app, "Decisioni")
    _page(app, "Gare")
    assert not app.exception
    assert app.radio(key=f"doc_{rid}").value == "risultati"


def test_the_time_just_taken_is_called_out_over_the_preview(app, iscritti_path):
    """The 200 m banner: the time in bold, who rode it, where it stands."""
    rid = _open_race(app, iscritti_path, "AL", "velocita", "Qualificazioni")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    fields = [t for t in app.sidebar.text_input if t.key.startswith(f"t_{rid}_")]
    assert fields, "no time fields on the 200 m"
    fields[1].set_value("11,500").run()
    fields[0].set_value("10,900").run()
    assert not app.exception

    banner = [m.value for m in app.markdown if "provvisorio" in m.value]
    assert banner and "<b>10,900</b>" in banner[0]
    assert "1° tempo provvisorio" in banner[0]

    # the ordine di partenza is read before anything has been timed
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert not [m.value for m in app.markdown if "provvisorio" in m.value]


def test_a_decision_is_filed_from_the_race_it_was_taken_in(app, iscritti_path):
    """The sidebar form writes one row of the register, and the W follows.

    The dorsale is picked among the partenti, the penalty is the compact code
    (provvedimento and UCI article), and the text is composed from the two -
    which is what the register is read back from weeks later.
    """
    from core import decisions as DEC
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    key = f"d_{rid}"
    app.sidebar.selectbox(key=f"{key}_pick").set_value("1").run()
    app.sidebar.selectbox(key=f"{key}_class").set_value("A").run()
    app.sidebar.selectbox(key=f"{key}_reason").set_value("5").run()
    # the proposal is composed on demand, in the wording of the UCI table
    app.sidebar.button(key=f"{key}_recompose").click().run()
    assert "AMMONIZIONE (A)" in app.sidebar.text_area(key=f"{key}_text").value
    app.sidebar.button(key=f"{key}_file").click().run()
    assert not app.exception

    taken = DEC.load(open_competition("CITA26"))
    assert [(d.cat, d.event, d.round_key, d.bibs, d.code) for d in taken] \
        == [("AL", "omnium", "Scratch", "1", "A5")]
    assert "AL 1" in taken[0].text
    # not on the sheets of this fase: they carry the decision itself
    assert not [c for c in app.sidebar.checkbox if c.key == f"warn_{rid}"]

    # a second one in the same fase is a squalifica, written into the field
    app.sidebar.selectbox(key=f"{key}_pick").set_value("1").run()
    app.sidebar.text_area(key=f"{key}_text").set_value("seconda").run()
    app.sidebar.button(key=f"{key}_file").click().run()
    assert not app.exception
    assert "1" in app.sidebar.text_input(key=f"dsq_{rid}_").value
    assert any("squalifica" in e.value for e in app.error)

    # both are listed under the panel, where they can be corrected or dropped
    assert any("In questa fase (2)" in c.value for c in app.sidebar.caption)
    app.sidebar.button(key=f"ed_{rid}_2").click().run()
    assert not app.exception
    assert len(DEC.load(open_competition("CITA26"))) == 1

    # and the prova that follows is where the W shows up
    tempo = _open_race(app, iscritti_path, "AL", "omnium", "Tempo Race")
    assert app.sidebar.checkbox(key=f"warn_{tempo}")


def test_a_decision_prints_on_the_sheet_of_the_race_it_was_taken_in(
        app, iscritti_path):
    """It goes out with the risultati, tinted, and not on the ordine di partenza.

    A start order is published before the race is ridden: a retrocessione on it
    would be one taken before anybody started. The sheet that closes the fase is
    where the decision belongs, and the tint is what says what it is across the
    table.
    """
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    _file(open_competition("CITA26"), cat="AL", event="omnium",
          round_key="Scratch", bibs="1", penalty="C", reason="2",
          text="AL 1: RETROCESSIONE (C) per essere transitato sulla fascia.")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert not app.exception
    sheet = _preview(app)
    assert 'class="decisione relegation"' in sheet
    # the sentence, and not the compact code: that one is asked for in
    # Impostazioni, and this competition has not asked for it
    assert "fascia" in sheet and ">C2</span>" not in sheet

    open_competition("CITA26").set_setting("decision_codes", True)
    app.run()
    assert ">C2</span>" in _preview(app)
    open_competition("CITA26").set_setting("decision_codes", False)
    app.run()

    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert not app.exception
    assert "decisione relegation" not in _preview(app)


def test_the_classifica_does_not_reprint_the_decisions_of_the_fasi(app):
    """A decision goes out once, on the comunicato of the fase it was taken in.

    The classifica ranks the specialità: reprinting every retrocessione of
    every turno under a final ranking reads as a fresh set of sanctions. The
    one exception is a specialità filed as a classification and nothing else -
    there the classifica *is* the sheet the decision was taken on.
    """
    from types import SimpleNamespace

    from core.config import (DOC_CLASSIFICATION, DOC_RESULTS, DOC_STARTLIST)
    from core.store import open_competition
    from ui.pages.races import _decisions_on

    store = open_competition("CITA26")
    _file(store, cat="AL", event="velocita", round_key="Quarti", bibs="1",
          penalty="C", reason="2", text="AL 1: RETROCESSIONE (C).")
    state = SimpleNamespace(cat="AL", event="velocita", round_key="Quarti")
    kinds = [DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION]

    assert len(_decisions_on(store, state, DOC_RESULTS, kinds)) == 1
    assert _decisions_on(store, state, DOC_CLASSIFICATION, kinds) == []
    assert _decisions_on(store, state, DOC_STARTLIST, kinds) == []
    # nothing else to publish it on: the classifica carries it
    assert len(_decisions_on(store, state, DOC_CLASSIFICATION,
                             [DOC_STARTLIST, DOC_CLASSIFICATION])) == 1


def test_the_team_sprint_start_order_saves_from_its_own_panel(app, iscritti_path):
    """One squadra per start, and a button to file it where it is composed.

    The save is asked for in the panel and done after the sidebar has run:
    a click up the page must not file a race without the times typed into it.
    """
    from core.parse import parse_heats
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "AL", "vel_squadre", "Qualificazioni")
    assert not any("Batterie" in n.label for n in app.number_input)
    app.button(key=f"fill_{rid}").click().run()

    note = [c.value for c in app.caption if c.value.startswith("Notazione")]
    heats = parse_heats(note[0].split("`")[1])
    assert heats and all(len(h) == 1 for h in heats)   # one squadra per start
    assert any("Tutte le squadre sono nell'ordine" in c.value
               for c in app.caption)

    app.button(key=f"savegrid_{rid}").click().run()
    assert not app.exception
    state = open_competition("CITA26").load_race(rid)
    assert state is not None and parse_heats(state.payload["heats"]) == heats


def test_the_times_follow_the_start_order(app, iscritti_path):
    """The sidebar is read while the track runs: same order, or a time slips.

    The grid is composed in the page body and the fields are in the sidebar,
    which is drawn after it: swapping two starts must move the fields in the
    same run, without saving first.
    """
    rid = _open_race(app, iscritti_path, "AL", "vel_squadre", "Qualificazioni")
    app.button(key=f"fill_{rid}").click().run()

    slots = [s for s in app.selectbox if s.key.startswith(f"hs_{rid}_")]
    order = [s.value for s in slots]
    assert len(order) > 2

    def times_order():
        return [t.key[len(f"t_{rid}_"):] for t in app.sidebar.text_input
                if t.key.startswith(f"t_{rid}_")]

    assert times_order() == order

    # first start against last: the fields follow, nobody is lost
    slots[0].set_value(order[-1]).run()
    app.selectbox(key=slots[-1].key).set_value(order[0]).run()
    assert not app.exception
    assert times_order() == [order[-1], *order[1:-1], order[0]]


def test_a_squadra_left_out_of_the_grid_keeps_its_time_field(app, iscritti_path):
    """An unfinished composition must not hide anyone from the sidebar."""
    rid = _open_race(app, iscritti_path, "AL", "vel_squadre", "Qualificazioni")
    app.button(key=f"fill_{rid}").click().run()
    slots = [s for s in app.selectbox if s.key.startswith(f"hs_{rid}_")]
    left_out = slots[0].value

    slots[0].set_value("").run()          # not yet inserted
    assert not app.exception
    keys = [t.key[len(f"t_{rid}_"):] for t in app.sidebar.text_input
            if t.key.startswith(f"t_{rid}_")]
    assert keys[-1] == left_out and len(keys) == len(slots)


def test_only_the_classifica_prints_a_point_smaller(app, iscritti_path):
    """Every sheet prints at 9. The classifica is the one that drops a point:
    it is the crowded one - it carries the societies and their codes."""
    rid = _open_race(app, iscritti_path, "AL", "ins_squadre", "Qualificazioni")
    font = f"font_{rid}"

    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert app.sidebar.slider(key=f"{font}_risultati").value == 9

    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert app.sidebar.slider(key=f"{font}_partenti").value == 9

    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert app.sidebar.slider(key=f"font_{rid}_risultati").value == 9
    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert app.sidebar.slider(key=f"font_{rid}_classifica").value == 8


def test_one_name_column_gives_the_classifica_its_point_back(app, iscritti_path):
    """A single Nome column is a whole column of width returned: with it the
    classifica has no reason to print smaller than everything else."""
    from core.store import open_competition

    open_competition("CITA26").set_setting("name_style", "full")
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert not app.exception
    assert app.sidebar.slider(key=f"font_{rid}_classifica").value == 9


def test_the_page_says_who_is_not_in_the_arrival(app, iscritti_path, comp):
    """A prova di gruppo that has been run must place everybody."""
    rid = _open_race(app, iscritti_path, "ED", "omnium", "Scratch")
    assert not [w for w in app.warning if "non ancora nei risultati" in w.value]

    bibs = _race_state(comp, "ED", "omnium", "Scratch").entrants
    app.text_input(key=f"spr_{rid}").set_value(",".join(bibs[:-2])).run()
    warn = [w for w in app.warning if "non ancora nei risultati" in w.value]
    assert warn and f"{bibs[-2]}, {bibs[-1]}" in warn[0].value

    app.text_input(key=f"spr_{rid}").set_value(",".join(bibs)).run()
    assert not [w for w in app.warning if "non ancora nei risultati" in w.value]


# ── omnium: every sheet of every prova ──────────────────────────────────────

def test_every_sheet_of_a_prova_renders(app, iscritti_path):
    """Each prova files its own sheets, and the picker offers exactly them."""
    rid = _open_race(app, iscritti_path, "ED", "omnium", "Scratch")
    assert app.radio(key=f"doc_{rid}").options == [
        "Partenti", "Risultati", "Classifica Parziale"]
    # a scratch is one arrival, not a series of sprints
    app.text_input(key=f"spr_{rid}").set_value("1,2,3,4").run()
    app.radio(key=f"doc_{rid}").set_value("classifica_parziale").run()
    assert not app.exception
    # the sheet is the ordine di partenza of the tempo race, and says so
    assert app.text_input(key=f"com_{rid}_classifica_parziale").value == "54"
    assert app.sidebar.checkbox(key=f"lane_{rid}").value is True

    rid = _open_race(app, iscritti_path, "ED", "omnium", "Tempo Race")
    assert app.radio(key=f"doc_{rid}").options == [
        "Partenti", "Gara", "Risultati", "Classifica Parziale"]
    for doc, number in (("gara", "-1"), ("risultati", "63"),
                        ("classifica_parziale", "64")):
        app.radio(key=f"doc_{rid}").set_value(doc).run()
        assert not app.exception
        assert app.text_input(key=f"com_{rid}_{doc}").value == number


def test_the_risultati_of_a_prova_go_out_unnumbered(app, iscritti_path):
    """The comunicato of a prova is the classifica parziale after it."""
    rid = _open_race(app, iscritti_path, "ED", "omnium", "Scratch")
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert app.text_input(key=f"com_{rid}_risultati").value == "-1"

    rid = _open_race(app, iscritti_path, "ED", "omnium", "Eliminazione")
    # the page reopens on the sheet left last (`_seed_doc`): ask for the one
    # this is about
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert app.text_input(key=f"com_{rid}_partenti").value == "-1"


def test_the_omnium_classifica_names_the_champion(app, iscritti_path):
    """An omnium is a title like any other: the classifica names who won it."""
    rid = _open_race(app, iscritti_path, "ED", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert not app.exception
    # the apostrophe is escaped in the HTML the page draws
    assert "CAMPIONESSA D&#39;ITALIA" in _preview(app)

    rid = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    sheet = _preview(app)
    assert "CAMPIONE D&#39;ITALIA" in sheet and "CAMPIONESSA" not in sheet
    # and only there: the classifica parziale of a prova crowns nobody
    rid = _open_race(app, iscritti_path, "AL", "omnium", "Scratch")
    app.radio(key=f"doc_{rid}").set_value("classifica_parziale").run()
    assert "CAMPIONE" not in _preview(app)


def test_the_omnium_classifica_offers_the_points_race_detail(app, iscritti_path):
    rid = _open_race(app, iscritti_path, "ED", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert not app.exception
    assert app.sidebar.checkbox(key=f"det_{rid}").value is True
    app.sidebar.checkbox(key=f"det_{rid}").set_value(False).run()
    assert not app.exception


# ── velocità: the scheme, and every round it composes ───────────────────────

def _save(app):
    [b for b in app.sidebar.button if b.label.endswith("Salva")][0].click().run()


def _qualify(app, iscritti_path, cat="AL", scheme="12", final_5_8=True):
    """Ride the 200 m: pick the scheme, give everybody a time, file the race.

    The 5°-8° is asked for here too, and the test says which velocità it is
    riding: the programme of the year decides the default, and a test that
    took it would change shape whenever the programme does.
    """
    rid = _open_race(app, iscritti_path, cat, "velocita", "Qualificazioni")
    app.selectbox(key=f"scheme_{rid}").set_value(scheme).run()
    app.toggle(key=f"f58_{rid}").set_value(final_5_8).run()
    for i, box in enumerate([t for t in app.sidebar.text_input
                             if t.key.startswith(f"t_{rid}_")]):
        box.set_value(f"11,{i:03d}")
    app.run()
    _save(app)
    return rid


def _picks(app, prefix, rid):
    """The segmented controls of one block of the sidebar, in order."""
    return [g for g in app.sidebar.button_group
            if g.key.startswith(f"{prefix}_{rid}_")]


def _opt(group, i) -> str:
    """The value behind the i-th button of a segmented control.

    A button carries its label and not the value, so the value is read back off
    the label: on a velocità an entrant *is* a dorsale, which is what
    `_entrant_name` puts in front of the name ("84 BORDIGNON").
    """
    return group.options[i].content.split()[0]


def _press(group, i):
    """Press the i-th button of a segmented control."""
    return group.set_value([_opt(group, i)])


def _pick_all(app, rid, prefix):
    """Whoever is in lane 1 wins: one control per batteria, in order."""
    picks = _picks(app, prefix, rid)
    assert picks, f"no {prefix} controls for {rid}"
    for g in picks:
        _press(g, 0)
    app.run()
    return picks


def _advance(app, label):
    hits = [b for b in app.button if b.label == label]
    assert hits, f"{label!r} not on the page: {[b.label for b in app.button]}"
    hits[0].click().run()
    assert not app.exception


def _round(app, cat, event, round_key):
    """Move to another round of the race already open, without re-importing."""
    from core.models import race_id

    app.selectbox(key="ga_round").set_value(round_key).run()
    assert not app.exception
    return race_id(cat, event, round_key)


def test_the_scheme_is_picked_on_the_qualifying_round(app, iscritti_path):
    """The 200 m start order says how many it qualifies - and the jury decides."""
    rid = _open_race(app, iscritti_path, "AL", "velocita", "Qualificazioni")
    box = app.selectbox(key=f"scheme_{rid}")
    assert "12 qualificati" in box.options[0]      # options come out formatted

    box.set_value("8").run()
    assert not app.exception
    dec = app.sidebar.text_area(key=f"dec_{rid}_partenti")
    assert dec.value == "Si qualificano direttamente ai quarti i migliori 8 tempi."

    app.selectbox(key=f"scheme_{rid}").set_value("12").run()
    assert (app.sidebar.text_area(key=f"dec_{rid}_partenti").value
            == "Si qualificano per il 1° turno i migliori 12 tempi.")


def test_the_qualifying_results_load_the_first_round(app, iscritti_path):
    """Twelve qualify, and they meet 1-12, 2-11, … - the UCI table, composed."""
    from core.formats import sprint as S
    from core.models import race_id
    from core.parse import parse_heats
    from core.store import open_competition

    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Turno 1")

    st = open_competition("CITA26").load_race(race_id("AL", "velocita",
                                                      S.TURNO1))
    heats = [[str(b) for s in h for b in s]
             for h in parse_heats(st.payload["heats"])]
    assert len(heats) == 6 and all(len(h) == 2 for h in heats)
    # the fastest meets the twelfth, and nobody rides twice
    fast = [k for k, _ in sorted(
        ((k, v) for k, v in open_competition("CITA26").load_race(
            rid).payload["times"].items()), key=lambda kv: kv[1])][:12]
    assert heats[0] == [fast[0], fast[11]] and heats[5] == [fast[5], fast[6]]
    assert len({k for h in heats for k in h}) == 12


def test_a_round_opened_before_it_is_composed_says_so(app, iscritti_path):
    """The quarti before *Carica Quarti*: a warning naming the sheet to press it on.

    Nothing stops the jury opening a fase early, and unloaded it does not look
    empty - it opens on the whole elenco iscritti with no batterie, which is
    what a broken round looks like. The page says which sheet composes it.
    """
    rid = _qualify(app, iscritti_path)
    _round(app, "AL", "velocita", "Quarti")
    warn = [w for w in app.warning if "non è ancora composta" in w.value]
    assert warn and "Ris. recuperi" in warn[0].value      # on the turno 1
    assert "Carica Quarti di finale" in warn[0].value

    # composed, it is a round like any other and says nothing
    app.selectbox(key="ga_round").set_value("Qualificazioni").run()
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Turno 1")
    _round(app, "AL", "velocita", "Turno 1")
    assert not [w for w in app.warning if "non è ancora composta" in w.value]


def test_the_first_round_composes_its_own_recuperi(app, iscritti_path):
    """One comunicato: the results above, the start order of the recuperi below.

    The recuperi are not a round of the programme and nobody composes them by
    hand - they are the six losers, dealt 1, 4, 6 against 2, 3, 5 - so they
    appear as soon as every batteria has a winner.
    """
    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Turno 1")

    rid = _round(app, "AL", "velocita", "Turno 1")
    # «Risultati» alone would name neither of the two races the round files
    assert [r for r in app.radio if r.key == f"doc_{rid}"][0].options == [
        "Partenti", "Ris. Turno 1", "Ris. recuperi"]
    assert not _picks(app, "rep", rid)

    _pick_all(app, rid, "t1")
    # the recuperi are a box of their own, opened by their own sheet - but
    # drawn either way, or the run that hid them would drop what was typed
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    rep = _picks(app, "rep", rid)
    assert len(rep) == 2                       # two batterie of three
    assert _picks(app, "t1", rid)              # still there, and still filled
    boxes = {e.label: e.proto.expanded for e in app.sidebar.expander}
    assert boxes["Recuperi"] and not boxes["Vincitori 1° turno"]

    # the sheet that files the recuperi is the one that composes the quarti
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    assert not app.exception
    assert any(b.label == "Carica Quarti di finale" for b in app.button)
    dec = app.sidebar.text_area(key=f"dec_{rid}_risultati_recuperi").value
    assert dec.startswith("Due prove + ev. bella.")


def test_a_quarter_is_ridden_at_the_best_of_three(app, iscritti_path):
    """Two prove, and the bella only when they went one each."""
    from core.models import race_id
    from core.parse import parse_heats
    from core.store import open_competition

    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Turno 1")

    rid = _round(app, "AL", "velocita", "Turno 1")
    _pick_all(app, rid, "t1")
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    _pick_all(app, rid, "rep")
    _save(app)
    _advance(app, "Carica Quarti di finale")

    rid = _round(app, "AL", "velocita", "Quarti")
    runs = _picks(app, "run", f"{rid}_0")
    assert len(runs) == 2                      # prova 1 and prova 2, no bella
    assert [r.label for r in runs] == ["Prova 1", "Prova 2"]

    # one prova each: the bella appears
    _press(runs[0], 0)
    _press(runs[1], 1)
    app.run()
    runs = _picks(app, "run", f"{rid}_0")
    assert len(runs) == 3 and runs[2].label == "ev. bella"

    _press(runs[2], 0).run()
    _save(app)
    st = open_competition("CITA26").load_race(race_id("AL", "velocita",
                                                      "Quarti"))
    won = [str(b) for s in parse_heats(st.payload["results"])[0] for b in s]
    # two prove to one, and the batteria is filed with him first
    assert won[0] == _opt(runs[2], 0)      # the one the bella was given to


def _preview(app) -> str:
    """The sheet as it is drawn on the page - the same HTML the PDF is made of."""
    return "\n".join(getattr(e.proto, "body", "") for e in app.main
                     if e.type == "html")


def test_a_velocita_is_ridden_from_the_200_m_to_the_champion(app, iscritti_path):
    """The whole event through the pages, one comunicato at a time.

    Every round is composed by the sheet before it, nothing is typed as
    notation, and the classification names the champion and ranks everybody
    the finals did not - on their 200 m.
    """
    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Turno 1")

    rid = _round(app, "AL", "velocita", "Turno 1")
    _pick_all(app, rid, "t1")
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    _pick_all(app, rid, "rep")            # 1° of each repechage
    _pick_all(app, rid, "rep")            # 2°: the third is whoever is left
    _save(app)
    # the results sheet of the first round carries the recuperi under it
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    # ...under a heading that says it is their start order, not more results,
    # and with the columns of one - UCI ID included
    sheet = _preview(app)
    assert "Turno 1 - Recuperi - Ordine di Partenza" in sheet
    assert "UCI ID" in sheet          # the results table above has no such column
    # on screen the letterhead is dropped: the first table takes the subtitle,
    # or the results would be a nameless block above a block with a heading
    assert '<div class="table-title">Turno 1 - Risultati</div>' in sheet
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    assert "Quarti di Finale - Ordine di Partenza" in _preview(app)
    _advance(app, "Carica Quarti di finale")

    rid = _round(app, "AL", "velocita", "Quarti")
    _pick_all(app, rid, "run")            # prova 1 of every batteria
    _pick_all(app, rid, "run")            # prova 2: two each, no bella
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    sheet = _preview(app)
    assert ("Semifinali - Ordine di Partenza" in sheet
            and "Finale 5°-8° Posto - Ordine di Partenza" in sheet)
    assert "Prova 1" in sheet and "ev. bella" in sheet
    _advance(app, "Carica Semifinali")

    rid = _round(app, "AL", "velocita", "Semifinali")
    _pick_all(app, rid, "run")
    _pick_all(app, rid, "run")
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert "Finali - Ordine di Partenza" in _preview(app)
    _advance(app, "Carica Finali")

    rid = _round(app, "AL", "velocita", "Finali")
    # on a finals round «Risultati» alone would not say which four it ranks:
    # the sheet next to it is the 5°-8°
    assert [r for r in app.radio if r.key == f"doc_{rid}"][0].options == [
        "Partenti", "Ris. 5°-8°", "Ris. 1°-4°", "Classifica"]
    app.radio(key=f"doc_{rid}").set_value("risultati_5-8").run()
    for _ in range(3):                    # 5°, 6°, 7° - the 8° is what is left
        _pick_all(app, rid, "f58")
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    boxes = {e.label: e.proto.expanded for e in app.sidebar.expander}
    assert boxes["Finali 1°-4°"] and not boxes["Finale 5°-8°"]
    _pick_all(app, rid, "run")
    _pick_all(app, rid, "run")
    _save(app)

    # the 5°-8° is one race: the batteria column says so once, against its
    # first line, the way every other batteria number is printed - and on a
    # finals sheet there is no batteria to number, so it is headed «Finale»
    app.radio(key=f"doc_{rid}").set_value("risultati_5-8").run()
    sheet = _preview(app)
    assert sheet.count("<td class=\"c\">5°-8°</td>") == 1
    assert "Finale</th>" in sheet and "Batt.</th>" not in sheet

    # ...same on the ordine di partenza, where the 5°-8° prints under the
    # composition of the two finals for the first four places
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    sheet = _preview(app)
    assert sheet.count("<td class=\"c\">5°-8°</td>") == 1
    assert "Batt.</th>" not in sheet

    # and the sheet of the other two finals says which places they rode for
    from core.config import DOC_RESULTS
    from core.store import open_competition as _open
    from ui.pages.races import _velocita_subtitle

    state = _race_state(comp_of(_open("CITA26")), "AL", "velocita", "Finali")
    assert _velocita_subtitle(state, DOC_RESULTS) == \
        "Finali 1°/2° e 3°/4° posto - Risultati"

    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert not app.exception
    sheet = _preview(app)
    # the apostrophe is escaped in the HTML the page draws
    assert "CAMPIONE D&#39;ITALIA" in sheet and "CAMPIONESSA" not in sheet

    from core import race as R
    from core.store import open_competition
    from core import entries as E
    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp_of(store))
    res = R.sprint_standings(store, comp_of(store), el, "AL", "velocita")
    assert [p.position for p in res.placings[:8]] == list(range(1, 9))
    assert len(res.placings) == 27        # everybody entered is classified


def comp_of(store):
    from core.config import load_competition
    return load_competition(store.root / "programme.yaml")


def test_a_velocita_start_order_carries_the_uci_id(app, iscritti_path):
    """The UCI ID belongs on the ordine di partenza of a velocità - the 200 m
    as much as the batterie composed from it."""
    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert not app.exception
    sheet = _preview(app)
    assert "<th" in sheet and "UCI ID" in sheet

    from core import entries as E
    from core.store import open_competition

    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp_of(store))
    uci = {r.uci_id for r in el.by_cat("AL") if r.uci_id}
    assert uci & set(re.findall(r">(\d{11})<", sheet))

    # a bunch race keeps the columns it has always had
    other = _open_race(app, iscritti_path, "AL", "omnium", "Corsa a Punti")
    app.radio(key=f"doc_{other}").set_value("partenti").run()
    assert "UCI ID" not in _preview(app)


def test_the_200_m_results_carry_the_cut(app, iscritti_path):
    """The line under the twelfth, and the decision that says why it is there."""
    rid = _qualify(app, iscritti_path)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    assert (app.sidebar.text_area(key=f"dec_{rid}_risultati").value
            == "Si qualificano per il 1° turno i migliori 12 tempi.")

    import re

    from core.store import open_competition
    times = open_competition("CITA26").load_race(rid).payload["times"]
    thirteenth = sorted(times, key=lambda k: times[k])[12]

    rows = re.findall(r"<tr[^>]*>.*?</tr>", _preview(app), re.S)
    strong = [r for r in rows if "group-start-strong" in r]
    # one heavier rule on the sheet, and it opens the line of the thirteenth
    assert len(strong) == 1
    assert f">{thirteenth}<" in strong[0]


def test_advanced_settings_hold_for_every_sheet(app):
    """Firma e nome si scelgono una volta, in «Impostazioni avanzate»."""
    from core.store import open_competition
    from ui import state

    _page(app, "Impostazioni")
    app.radio(key="sig_mode").set_value("text").run()
    assert not app.exception
    app.text_input(key="sig_name").set_value("Mario Rossi").run()
    [b for b in app.button if b.label == "Salva nome"][0].click().run()
    app.selectbox(key="sig_scope").set_value("results").run()
    app.radio(key="name_style").set_value("full").run()
    assert not app.exception
    # the single column brings its own width with it: it is only asked for
    # once there is one column to size
    app.slider(key="name_width").set_value(0.5).run()
    assert not app.exception

    s = open_competition("CITA26").settings
    assert s["signature_mode"] == "text" and s["signature_name"] == "Mario Rossi"
    assert s["signature_scope"] == "results" and s["name_style"] == "full"
    assert s["name_width"] == 0.5

    # and from there they set the ticks the other pages open with
    b = state.competition("CITA26").branding
    assert b.signs("risultati") and b.signs("classifica")
    assert not b.signs("partenti")


def test_a_womens_velocita_is_written_about_women(app, iscritti_path, comp):
    """«La vincitrice di ogni batteria», not a generic masculine.

    The sheets are written about the riders in front of the jury, the way the
    classification already names a CAMPIONESSA.
    """
    from core import race as R
    from core.config import DOC_RESULTS, DOC_RESULTS_REP, DOC_STARTLIST
    from core.store import open_competition
    from ui.pages.races import _velocita_notes

    store = open_competition("CITA26")

    def notes(cat):
        _qualify(app, iscritti_path, cat=cat)
        state = _race_state(comp, cat, "velocita", "Turno 1")
        return _velocita_notes(state, comp,
                               R.sprint_scheme(store, comp, cat, "velocita"))

    women = notes("DA")
    assert women[DOC_STARTLIST].startswith("La vincitrice di ogni batteria")
    assert women[DOC_STARTLIST].endswith("le altre ai recuperi.")
    assert women[DOC_RESULTS].startswith("La vincitrice di ogni batteria dei "
                                         "recuperi")
    assert "Le vincitrici passano alle semifinali, le altre" \
        in women[DOC_RESULTS_REP]

    men = notes("AL")
    assert men[DOC_STARTLIST].startswith("Il vincitore di ogni batteria")
    assert men[DOC_RESULTS_REP].startswith("Due prove + ev. bella. I vincitori")


# ── keirin ──────────────────────────────────────────────────────────────────

def _kfields(boxes, prefix):
    """The numbered fields of one block: `results` must not catch
    `results_final_b`, which is another race of the same round."""
    fields = [t for t in boxes if t.key.startswith(prefix)
              and t.key[len(prefix):].isdigit()]
    return sorted(fields, key=lambda t: int(t.key[len(prefix):]))


def _kheats(app, rid, key):
    """The composition fields of one race of a keirin round, in order."""
    return _kfields(app.main.text_input, f"kh_{rid}_{key}_")


def _korders(app, rid, key):
    """The arrival fields in the sidebar, one per batteria."""
    return _kfields(app.sidebar.text_input, f"kr_{rid}_{key}_")


def _kcompose(app, comp, rid, cat, round_key, key="heats"):
    """Type the batterie: the entrants dealt over the fields, as the jury does."""
    entrants = _race_state(comp, cat, "keirin", round_key).entrants
    fields = _kheats(app, rid, key)
    assert fields, f"no composition fields for {rid}/{key}"
    heats = [[] for _ in fields]
    for i, bib in enumerate(entrants):
        heats[i % len(fields)].append(bib)
    for box, heat in zip(fields, heats):
        box.set_value(", ".join(heat))
    app.run()
    assert not app.exception
    return heats


def _kride(app, rid, heats_key, results_key):
    """Every batteria finishes in the order it lines up in."""
    from core import race as R
    from core.store import open_competition

    heats = R.bracket_heats(open_competition("CITA26").load_race(rid),
                            heats_key)
    fields = _korders(app, rid, results_key)
    assert len(fields) == len(heats), (len(fields), len(heats))
    for box, heat in zip(fields, heats):
        box.set_value(", ".join(heat))
    app.run()
    assert not app.exception
    return heats


def test_a_keirin_is_ridden_from_the_first_round_to_the_champion(app,
                                                                 iscritti_path,
                                                                 comp):
    """The whole tournament through the pages: the jury composes the first
    round, the tables compose everything after it."""
    from core import race as R
    from core.store import open_competition

    rid = _open_race(app, iscritti_path, "AL", "keirin", "Turno 1")
    # the shape of the tournament is on the page, read off the entry list
    assert any("tabella UCI 29-42" in c.value for c in app.caption)
    # the round files four sheets: its own two, and the two of its recuperi
    assert [r for r in app.radio if r.key == f"doc_{rid}"][0].options == [
        "Partenti", "Ris. Turno 1", "Recuperi", "Ris. recuperi"]
    dec = app.sidebar.text_area(key=f"dec_{rid}_partenti").value
    assert dec == ("Turno 1: 6 batterie. Il vincitore di ogni batteria passa "
                   "alle semifinali, gli altri ai recuperi.")

    _kcompose(app, comp, rid, "AL", "Turno 1")
    _save(app)
    heats = _kride(app, rid, "heats", "results")
    _save(app)
    # the batterie print on the ordine di partenza, in dorsale order
    app.radio(key=f"doc_{rid}").set_value("partenti").run()
    assert "Batt." in _preview(app)

    # the risultati compose the recuperi, onto this same round
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    _advance(app, "Carica Recuperi")
    rep = R.bracket_heats(open_competition("CITA26").load_race(rid),
                          R.REP_HEATS)
    assert len(rep) == 6 and all(len(h) == 5 for h in rep)
    # nobody who won a batteria is in them
    assert not {h[0] for h in heats} & {k for h in rep for k in h}

    # both grids of the round are full now, each measured against its own
    # riders: the recuperi start who did not qualify, not the categoria
    assert len([c for c in app.caption
                if c.value == "Tutti in batteria."]) == 2

    app.radio(key=f"doc_{rid}").set_value("partenti_recuperi").run()
    # the recuperi have an ordine di partenza of their own on this round: it
    # starts the riders they took in, and not one of the batterie's winners
    from core import entries as E
    by_bib = R.riders_by_bib(
        E.effective_entries(open_competition("CITA26"),
                            comp_of(open_competition("CITA26")))[0], "AL")
    sheet = _preview(app)
    assert by_bib[rep[0][0]].last_name in sheet
    assert by_bib[heats[0][0]].last_name not in sheet   # she won her batteria
    _kride(app, rid, R.REP_HEATS, R.REP_RESULTS)
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati_recuperi").run()
    _advance(app, "Carica Semifinali")

    rid = _round(app, "AL", "keirin", "Semifinali")
    semis = _kride(app, rid, "heats", "results")
    assert len(semis) == 2 and all(len(h) == 6 for h in semis)
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    # the sheet that decides the finals carries their start orders underneath
    sheet = _preview(app)
    assert "Finale 1°-6° posto - Ordine di Partenza" in sheet
    assert "Finale 7°-12° posto - Ordine di Partenza" in sheet
    _advance(app, "Carica Finali")

    rid = _round(app, "AL", "keirin", "Finali")
    assert [r for r in app.radio if r.key == f"doc_{rid}"][0].options == [
        "Partenti", "Ris. 7°-12°", "Ris. 1°-6°", "Classifica"]
    # both finals on the one ordine di partenza, each named by its places
    sheet = _preview(app)
    assert "Finale</th>" in sheet and "1°-6°" in sheet and "7°-12°" in sheet

    app.radio(key=f"doc_{rid}").set_value("risultati_finale_b").run()
    _kride(app, rid, R.HEATS_B, R.RESULTS_B)
    _save(app)
    app.radio(key=f"doc_{rid}").set_value("risultati").run()
    top = _kride(app, rid, "heats", "results")
    _save(app)

    app.radio(key=f"doc_{rid}").set_value("classifica").run()
    assert not app.exception
    sheet = _preview(app)
    assert "CAMPIONE D&#39;ITALIA" in sheet
    # the classifica is read final by final: the one for the title, the one
    # under it, and then everybody the tournament left before them
    for block in ("FINALE 1°-6° POSTO", "FINALE 7°-12° POSTO",
                  "CLASSIFICA GENERALE"):
        assert f'<div class="table-title">{block}</div>' in sheet

    from core import entries as E
    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp_of(store))
    res = R.keirin_standings(store, comp_of(store), el, "AL", "keirin")
    assert [p.key for p in res.placings][:6] == top[0]
    assert [p.position for p in res.placings[:12]] == list(range(1, 13))
    assert len(res.placings) == len(R.keirin_entrants(el, comp_of(store),
                                                      "AL", "keirin"))


def test_a_keirin_says_what_is_wrong_with_a_batteria(app, iscritti_path, comp):
    """A dorsale in two batterie, or one that is not entered, is said at once."""
    rid = _open_race(app, iscritti_path, "AL", "keirin", "Turno 1")
    entered = _race_state(comp, "AL", "keirin", "Turno 1").entrants
    fields = _kheats(app, rid, "heats")
    fields[0].set_value(", ".join(entered[:3]))
    fields[1].set_value(f"{entered[0]}, 999")
    app.run()
    assert not app.exception
    flags = [c.value for c in app.caption if ":red[" in c.value]
    assert any("?999" in f for f in flags)
    assert any(f"!{entered[0]}" in f for f in flags)
    assert any("Non ancora in batteria" in c.value for c in app.caption)


def test_a_womens_keirin_is_written_about_women(app, iscritti_path, comp):
    """«La vincitrice», and the two finals named by the places they ride for."""
    from core.config import DOC_RESULTS, DOC_STARTLIST, DOC_STARTLIST_REP
    from ui.pages.races import _keirin_notes

    _open_race(app, iscritti_path, "DA", "keirin", "Turno 1")
    from core import entries as E
    from core.store import open_competition

    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp)
    state = _race_state(comp, "DA", "keirin", "Turno 1")
    notes = _keirin_notes(state, el, comp)
    assert notes[DOC_STARTLIST] == ("Turno 1: 3 batterie. Le prime 2 "
                                    "classificate di ogni batteria passano "
                                    "alle semifinali, le altre ai recuperi.")
    assert notes[DOC_STARTLIST_REP].startswith("Recuperi: 3 batterie. Le prime 2")

    semi = _race_state(comp, "DA", "keirin", "Semifinali")
    assert _keirin_notes(semi, el, comp)[DOC_RESULTS] == (
        "Semifinali: 2 batterie. Le prime 3 classificate di ogni batteria "
        "passano alla finale 1°-6° posto, le altre alla finale 7°-12° posto.")


# ── the Statistiche page ────────────────────────────────────────────────────
#
# The medagliere reads every race of the championship, so the page is opened
# here in the three states it is met in: nothing imported, nothing ridden, and
# a specialità decided.


def test_statistiche_page_is_empty_until_something_is_decided(app,
                                                              iscritti_path):
    _import(app, iscritti_path)
    _page(app, "Statistiche")
    assert not app.exception
    assert any("medagliere" in i.value for i in app.info)


def test_statistiche_page_counts_the_podium_of_a_specialita(app, iscritti_path,
                                                            comp):
    """A finale with times on it puts three squadre in the medagliere."""
    from core import entries as E
    from core import race as R
    from core.store import open_competition

    _import(app, iscritti_path)
    store = open_competition("CITA26")
    el, _ = E.effective_entries(store, comp)
    state = R.ensure_state(store, comp, "AL", "vel_squadre", "Finali", el)
    state.payload["times"] = {key: 60_000 + i
                              for i, key in enumerate(state.entrants)}
    store.save_race(state)

    _page(app, "Statistiche")
    assert not app.exception
    podium = [el.teams[k].region for k in state.entrants[:3]]
    table = app.dataframe[0].value
    assert list(table.columns)[:3] == ["Pos.", "Squadra", "🥇 1°"]
    assert table.iloc[0]["Squadra"] == podium[0]
    assert table[table.columns[2]].sum() == 1     # one title, one gold
    assert set(table["Squadra"]) == set(podium)

    # and the same table on paper: the sheet is there to be saved, not only
    # read off the screen
    assert any("PDF" in b.label for b in app.button)
    assert "MEDAGLIERE" in "".join(h.body for h in app.get("html"))

    # the medagliere is reprinted all day: it can be printed without the
    # "Emesso il ..." line, so two identical copies stay identical
    stamp = [c for c in app.sidebar.checkbox if c.key == "stats_no_printed_at"]
    assert stamp and stamp[0].value is False       # off unless it is asked for
    app = stamp[0].set_value(True).run()
    assert not app.exception


# ── the Programma page ──────────────────────────────────────────────────────
#
# The page edits `programme.yaml` and nothing else. What it must never do is
# change the competition just by being opened and saved: the file it writes is
# the one the championship runs from.

def _programme_page(app):
    _page(app, "Programma")
    assert not app.exception
    return app


def _day(app, day: int):
    """Open a giornata of the Programma page - one is drawn at a time."""
    return app.button_group(key="prog_day").set_value([day]).run()


def test_programma_page_opens_on_the_giornate_and_one_day_at_a_time(app):
    """Four tabs, and Programmazione shows one giornata at a time.

    `st.tabs` builds the body of every tab on every rerun, so a tab per day was
    four scalette drawn to move one fase. The picker carries the four dates.

    Specialità is not a tab of its own: what a specialità *is* holds for every
    championship and is in Impostazioni, and the lines it used to carry to
    every sheet are the regulation's (Impostazioni → Righe dei comunicati).
    """
    _programme_page(app)
    assert [t.label for t in app.tabs] == [
        "Gara", "Categorie, specialità e giornate", "Programmazione",
        "Foglio programma"]
    days = app.button_group(key="prog_day")
    assert [o.content for o in days.options] == [
        f"Giornata {n} · 08-0{n + 3}" for n in (1, 2, 3, 4)]
    # one day is drawn, and it is a day: the scaletta and the register of it
    # one table for the giornata: the register is three columns of it now, and
    # the second table under it is gone
    heads = [s.value for s in app.subheader]
    assert heads.count("Fasi della giornata") == 1
    assert "Comunicati della giornata" not in heads
    # and the one summary: rows the categorie, columns the specialità
    assert "Categorie × specialità" in heads


def test_a_categoria_is_added_and_given_a_specialita(app):
    """The workflow the page is built around, end to end.

    A sigla the catalogue has not got, ticked into a specialità: the race is in
    the programme with the fasi the regulation proposes and on no giornata,
    which is what the checks then say. Unticking takes it away again.
    """
    _programme_page(app)
    app.text_input(key="prog_cat_code").set_value("MA").run()
    app.button(key="prog_cats_add_go").click().run()
    assert not app.exception
    draft = app.session_state["prog_draft"]
    assert "MA" in draft.categories

    app.multiselect(key="prog_evs_MA").set_value(["keirin"]).run()
    assert not app.exception
    item = app.session_state["prog_draft"].scheduled("MA", "keirin")
    assert item is not None and item.rounds, "the race came with no fasi"
    assert item.day == 0 and all(r.day == 0 for r in item.rounds)
    assert any("nessuna giornata" in w.value for w in app.warning)

    app.multiselect(key="prog_evs_MA").set_value([]).run()
    assert app.session_state["prog_draft"].scheduled("MA", "keirin") is None


def test_a_specialita_is_split_over_two_days_from_the_day_it_moves_to(app):
    """Two of the velocità's fasi put on the fourth day, and they say so.

    The race stays one - `scheduled` still finds all five fasi - and the ones
    that moved carry their own giornata.
    """
    _programme_page(app)
    _day(app, 4)
    app.selectbox(key="prog_addcat_4").set_value("AL").run()
    app.selectbox(key="prog_addev_4").set_value("velocita").run()
    picker = app.multiselect(key="prog_addrnd_4_AL_velocita")
    moved = list(picker.value)[-2:]
    picker.set_value(moved).run()
    app.button(key="prog_add_4").click().run()
    assert not app.exception

    draft = app.session_state["prog_draft"]
    item = draft.scheduled("AL", "velocita")
    assert len(item.rounds) == 5, "the split made a second race"
    assert [r.key for r in item.rounds if draft.day_of(item, r) == 4] == moved
    assert {draft.day_of(item, r) for r in item.rounds} == {item.day, 4}


# The scaletta of a giornata is a `st.data_editor`, and AppTest cannot type
# into one (see the note in `conftest`): what the grid hands back is a frame,
# so the three tests below hand one over themselves and check what the page
# then writes onto the programme. It is the whole of the write-back - the
# order, the orario, and the fase taken off the day.

def _scaletta(comp, day):
    from ui.pages import programme as PP
    on = comp.rounds_on(day)
    return on, PP._day_rows(comp, on, numbers=False, race=False)


def _apply(comp, day, edits: dict):
    """Edit the scaletta of a day the way the grid does, and apply it."""
    import pandas as pd
    from ui.pages import programme as PP

    on, rows = _scaletta(comp, day)
    frame = pd.DataFrame(rows)
    for (row, col), value in edits.items():
        frame.at[row, col] = value
    return PP._apply_scaletta(comp, on, rows, frame)


def _fresh():
    """The real championship programme, off disk and untouched."""
    from core.config import load_competition
    return load_competition(programme_path())


def test_a_fase_typed_to_the_front_takes_the_giornata_with_it():
    """The gesture the scaletta exists for, and the file it leaves behind."""
    comp = _fresh()
    was = [(i.cat, r.key) for i, r in comp.rounds_on(2)]

    assert _apply(comp, 2, {(4, "n"): 1}), "the page did not see the edit"
    now = [(i.cat, r.key) for i, r in comp.rounds_on(2)]
    assert now[0] == was[4], "the fase did not go to the front"
    assert now[1:] == was[:4] + was[5:], "the rest did not keep its order"
    # renumbered whole, from 1: a running order with a hole in it says nothing
    assert [r.seq for _i, r in comp.rounds_on(2)] == list(range(1, len(now) + 1))


def test_two_numbers_typed_before_applying_both_land():
    """One commit, not one rerun per fase - which is what the grid is for."""
    comp = _fresh()
    was = [(i.cat, r.key) for i, r in comp.rounds_on(2)]

    _apply(comp, 2, {(5, "n"): 1, (6, "n"): 2})
    now = [(i.cat, r.key) for i, r in comp.rounds_on(2)]
    assert now[:2] == [was[5], was[6]]


def test_a_scaletta_nobody_touched_writes_nothing():
    """Opening a giornata must not put a `seq:` on every fase of it.

    The scaletta is shown numbered 1..N whether or not the file says so
    (`config.rounds_on` falls back to the order the programme is in), so a
    write-back that dealt the numbers out unasked would turn every giornata
    merely opened into a diff.
    """
    comp = _fresh()
    was = [r.seq for i in comp.programme for r in i.rounds]
    assert not _apply(comp, 2, {})
    assert [r.seq for i in comp.programme for r in i.rounds] == was


def test_the_box_takes_a_fase_off_the_day_and_leaves_it_in_the_programme():
    """`Togli` is about the giornata, never about the programme."""
    comp = _fresh()
    on, _rows = _scaletta(comp, 2)
    item, rnd = on[3]

    assert _apply(comp, 2, {(3, "off"): True})
    assert comp.day_of(item, rnd) == 0, "still on the day"
    assert rnd in comp.scheduled(item.cat, item.event).rounds, "left the race"
    assert (item.cat, rnd.key) not in [(i.cat, r.key)
                                       for i, r in comp.rounds_on(2)]


def test_the_orario_is_typed_into_the_scaletta():
    """The one field of a fase that is read off the running order itself."""
    comp = _fresh()
    on, _rows = _scaletta(comp, 2)

    assert _apply(comp, 2, {(0, "start"): "09:30"})
    assert on[0][1].start == "09:30"


def test_the_scaletta_carries_the_numbers_of_the_comunicati():
    """One table: the fase, and beside it the comunicato each sheet goes out on.

    The register used to be a second table under the first, in the same order,
    with the same fasi in it - and keeping the two in step by reading down one
    and up the other was the work the jury was left with.
    """
    from ui.pages import programme as PP

    comp = _fresh()
    rows = PP._day_rows(comp, comp.rounds_on(2), numbers=True, race=True)
    first = rows[0]
    assert (first["cat"], first["round"]) == ("ES", "Qualificazioni")
    assert first["com_start"] and first["com_res"]
    # and what the fase actually rides, where it is read
    assert "km" in first["event"] and "giri" in first["event"]


def test_the_race_line_is_off_when_the_switch_is():
    """Two switches in the sidebar, and off is the shortest table there is."""
    from ui.pages import programme as PP

    comp = _fresh()
    rows = PP._day_rows(comp, comp.rounds_on(2), numbers=False, race=False)
    assert "com_start" not in rows[0]
    assert rows[0]["event"] == "Velocità"


def test_two_sheets_given_one_number_become_one_comunicato():
    """Typing the number of another sheet is how a comunicato is merged.

    Which is what a velocità does every turno, and what the register has always
    meant by two rows with one number on them.
    """
    from ui.pages import programme as PP

    comp = _fresh()
    item, rnd = comp.rounds_on(2)[0]
    start = PP._spec_of(comp, item, rnd, "partenti").n
    assert PP._renumber_sheets(comp, [(item, rnd, "risultati", start)])

    one = [c for c in comp.communiques if c.n == start]
    assert len(one) == 1, "the number is on two comunicati"
    assert [s.doc for s in one[0].sheets] == ["partenti", "risultati"]
    # and the table says so on the row of that fase
    row = PP._day_rows(comp, comp.rounds_on(2), numbers=True, race=False)[0]
    assert row["com_start"] == row["com_res"] == start


def test_a_fase_files_the_two_usual_sheets_without_being_told():
    """`Round.docs = None` is *the usual two*, and reading it raw lost them.

    Opening a fase seeded the picker from the raw field, showed nothing ticked
    and wrote that back: a fase that files no comunicato because somebody
    looked at it.
    """
    from core.config import Round
    from ui.pages import programme as PP

    assert PP._docs_of(Round(key="Finale")) == ["partenti", "risultati"]
    assert PP._docs_of(Round(key="Finale", docs=["risultati"])) == ["risultati"]
    assert PP._docs_of(Round(key="Composizione coppie", kind="setup")) == []


def test_assigning_the_documents_gives_back_the_file_that_was_written_by_hand():
    """The strongest check there is: on CITA26 it changes nothing.

    Which sheets a fase files was decided by hand, fase by fase, for a hundred
    and forty comunicati. Proposing them from the regulation has to come out at
    exactly that file, or the button is a way of losing a championship's worth
    of decisions.
    """
    from ui.pages import programme as PP

    comp = _fresh()
    assert PP._assign_docs(comp, classification=True, repechages=True,
                           keep=False) == 0


def test_assigning_the_documents_fills_in_a_programme_that_states_none():
    """And on a programme that says nothing, every fase comes out stated."""
    from core.config import load_competition
    from ui.pages import programme as PP

    comp = load_competition(EXAMPLE_PROGRAMME)
    assert PP._assign_docs(comp, classification=True, repechages=True,
                           keep=False) > 0
    for item in comp.programme:
        ridden = [r for r in item.rounds if r.kind != "setup"]
        assert all(r.docs for r in ridden), item.event
        # the classifica closes the specialità, and closes it once
        closing = [r for r in ridden if "classifica" in (r.docs or [])]
        assert len(closing) == 1 and closing[0] is ridden[-1]


def test_saving_the_programme_changes_nothing(app, tmp_path):
    """Open the page, press Salva, and the competition is what it was.

    The one property the page owes: it is opened to change a programme, and
    opening it must not change one. Checked on the real championship file -
    the fixture works on a copy of it in a throwaway data directory.
    """
    from core.config import load_competition
    from core.store import competitions_root

    path = competitions_root() / "CITA26" / "programme.yaml"
    before = load_competition(path)

    _programme_page(app)
    app.button(key="savebar_save").click().run()
    assert not app.exception

    after = load_competition(path)
    assert _competition_dict(after) == _competition_dict(before)


def _competition_dict(comp):
    import dataclasses
    d = dataclasses.asdict(comp)
    d.pop("path")
    return d


def test_the_previous_programme_is_kept_as_a_snapshot(app):
    """Overwriting the programme is exactly what `.snapshots/` is for."""
    from core.store import open_competition

    _programme_page(app)
    app.button(key="savebar_save").click().run()
    assert not app.exception
    snaps = open_competition("CITA26").snapshots("programme.yaml")
    assert snaps and "CAMPIONATI ITALIANI" in snaps[0].read_text(encoding="utf-8")


def test_the_page_shows_what_the_file_will_look_like(app):
    """The preview is the file itself: nothing is written blind."""
    _programme_page(app)
    assert any("Anteprima del file" in e.label for e in app.expander)
    text = "\n".join(c.value for c in app.code)
    assert "communiques:" in text and "programme:" in text


def test_a_comunicato_can_carry_two_documents(app, iscritti_path):
    """Stampa → Per comunicato builds exactly what the register declares.

    The velocità has always printed the risultati of a turno with the ordine di
    partenza of the round it composes underneath; the register can now say so
    (`with:` in the programme), and the sheet comes out as one PDF.
    """
    from core.config import Sheet, load_competition
    from core.programme import dump
    from core.store import competitions_root

    _import(app, iscritti_path)
    path = competitions_root() / "CITA26" / "programme.yaml"
    comp = load_competition(path)
    # a round that has been ridden by nobody yet: both its sheets are named,
    # and the page says of each that there is nothing to print
    turno1 = next(c for c in comp.communiques
                  if (c.cat, c.event, c.round_key, c.doc)
                  == ("AL", "velocita", "Turno 1", "risultati"))
    turno1.extra = [Sheet(doc="partenti_recuperi")]
    # two elenchi iscritti on one comunicato - the case a small competition
    # files, and the one that prints without a single race being ridden
    next(c for c in comp.communiques if c.n == 1).extra = [
        Sheet(cat="ED", doc="partenti")]
    path.write_text(dump(comp), encoding="utf-8")

    _documents(app, "Serie di documenti")
    _pick(app.sidebar.radio(key="stp_mode"), "Per comunicato").run()
    assert not app.exception

    picker = app.sidebar.selectbox(key="stp_com")
    picker.set_value(next(o for o in picker.options
                          if o.startswith(f"{turno1.n} "))).run()
    # the page names both documents of the number, and says of each that the
    # race behind it has not been ridden
    assert any("Risultati + Recuperi" in c.value for c in app.caption)
    assert sum("Turno 1" in w.value for w in app.warning) == 2

    picker = app.sidebar.selectbox(key="stp_com")
    picker.set_value(next(o for o in picker.options if o.startswith("1 "))).run()
    assert not app.exception
    assert any("2 documenti" in c.value for c in app.caption)
    # both categorie are on the sheet, which is the whole point of the number
    sheet = _preview(app)
    assert "UOMINI ESORDIENTI" in sheet and "DONNE ESORDIENTI" in sheet


def test_the_tints_of_the_decisions_are_set_in_impostazioni(app):
    """One colour per kind, stored whole - and the sheets print it at once."""
    from core.store import open_competition

    _page(app, "Impostazioni")
    app.color_picker(key="note_color_disqualification").set_value("#ff0000").run()
    app.button(key="save_note_colors").click().run()
    assert not app.exception
    colors = open_competition("CITA26").settings["note_colors"]
    assert colors["disqualification"] == "#ff0000"
    # the others are written with it: half a palette in the file is half of it
    # silently following a default that may move
    assert colors["warning"] == "#fef08a"

    app.button(key="reset_note_colors").click().run()
    assert not app.exception
    assert open_competition("CITA26").settings["note_colors"][
        "disqualification"] == "#fecaca"


def test_a_programme_cached_before_a_code_change_is_read_again(app):
    """A field added to the config since the object was cached must not crash.

    `st.cache_data` keeps the programme across a hot reload and restores it
    without running `__init__`, so a new field is simply missing from the
    instance and the next `dataclasses.replace` raises - on a running app, at
    the track. The stale copy is dropped and read again instead.
    """
    from dataclasses import fields

    from core.store import competitions_root
    from ui import state

    yaml = competitions_root() / "CITA26" / "programme.yaml"
    path, mtime = str(yaml), yaml.stat().st_mtime
    stale = state._load(path, mtime)
    # what an object pickled before the field existed looks like coming back
    del stale.branding.__dict__["note_colors"]
    assert not state._complete(stale)

    fresh = state._stale_free(path, mtime)
    assert state._complete(fresh)
    assert all(hasattr(fresh.branding, f.name)
               for f in fields(fresh.branding))
    _page(app, "Impostazioni")
    assert not app.exception


# ── building a competition from nothing ─────────────────────────────────────

@pytest.fixture
def empty(tmp_path, monkeypatch):
    """The app pointed at a data folder with nothing in it at all."""
    monkeypatch.setenv("COMMISSAIRE_TRACK_DATA", str(tmp_path / "competitions"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    return at


def test_an_empty_data_folder_asks_for_the_first_competition(empty):
    """It used to say the folder was empty and stop, with nowhere to act on it."""
    assert not empty.exception
    assert empty.text_input(key="setup_first_name")

    empty.text_input(key="setup_first_name").set_value("TR2026").run()
    empty.button(key="setup_first_go").click().run()
    assert not empty.exception
    # the folder exists now, and the app has walked on into the three steps
    assert empty.text_input(key="prog_name")


def test_a_competition_with_no_programme_builds_one(empty):
    """The dead end: no programme.yaml, and Impostazioni unreachable to fix it."""
    from core.config import Category, load_competition

    empty.text_input(key="setup_first_name").set_value("TR2026").run()
    empty.button(key="setup_first_go").click().run()

    empty.text_input(key="prog_name").set_value("TROFEO DI PROVA").run()
    empty.text_input(key="prog_dates").set_value("2026-09-05").run()
    empty.number_input(key="prog_track").set_value(250.0).run()
    # the track is quoted in metres and what follows from it is shown at once
    assert any("18" in c.value for c in empty.caption), "no madison capacity"

    # the categorie grid is an st.data_editor, which AppTest cannot drive
    empty.session_state["setup_draft"].categories = {
        "DA": Category(code="DA", name="DONNE ALLIEVE", sex="F", order=1)}
    [b for b in empty.button if "Crea" in b.label][-1].click().run()
    assert not empty.exception

    written = load_competition(
        __import__("core.store", fromlist=["open_competition"])
        .open_competition("TR2026").path("programme.yaml"))
    assert written.name == "TROFEO DI PROVA"
    assert written.track_len == 0.25 and written.dates == ["2026-09-05"]
    assert "DA" in written.categories
    # the pseudo-event the opening comunicati hang off is declared from the start
    assert "entry_list" in written.events


def test_a_specialita_is_picked_and_its_shape_asked_per_categoria(empty):
    """Seven fields typed by hand is how an inseguimento becomes a corsa.

    The specialità are *ticked*, on the categoria that rides them - the
    catalogue knows the code, the sigla, the format and the atleti per squadra,
    and the race comes out whole. What differs from categoria to categoria is
    asked under that categoria and nowhere else: the same chilometro is ridden
    two at a time by one and one at a time by the next.
    """
    from core.config import Category

    empty.text_input(key="setup_first_name").set_value("TR2026").run()
    empty.button(key="setup_first_go").click().run()
    empty.text_input(key="prog_dates").set_value("2026-09-05").run()
    empty.number_input(key="prog_track").set_value(250.0).run()
    empty.session_state["setup_draft"].categories = {
        "DA": Category(code="DA", name="DONNE ALLIEVE", sex="F", order=1)}
    [b for b in empty.button if "Crea" in b.label][-1].click().run()

    # a fresh run rather than the same one: the app has just left the setup
    # page for the race pages, and AppTest cannot follow a widget it has
    # already touched off the screen (it is the harness, not the app)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app.run()
    _page(app, "Programma")
    empty = app

    empty.multiselect(key="prog_evs_DA").set_value(["chilometro"]).run()
    assert not empty.exception

    ev = empty.session_state["prog_draft"].events["chilometro"]
    assert (ev.fmt, ev.abbr) == ("time_trial", "TT")

    # ticking it gave the whole race, distance and giri included; the one thing
    # the specialità cannot answer for every categoria is asked under this one
    starts = empty.radio(key="prog_opt_per_start_DA_chilometro")
    starts.set_value(starts.options[1]).run()          # uno alla volta
    assert not empty.exception

    # and it is put on the giornata one fase at a time
    empty.selectbox(key="prog_addcat_1").set_value("DA").run()
    empty.selectbox(key="prog_addev_1").set_value("chilometro").run()
    empty.multiselect(key="prog_addrnd_1_DA_chilometro").set_value(["Finale"]).run()
    empty.button(key="prog_add_1").click().run()
    assert not empty.exception

    item = empty.session_state["prog_draft"].scheduled("DA", "chilometro")
    assert [r.key for r in item.rounds] == ["Finale"]
    assert item.day == 1
    # a kilometre is a kilometre, and on a 250 it is four giri
    assert (item.rounds[0].distance, item.rounds[0].laps) == (1.0, 4.0)
    assert item.rounds[0].docs[-1] == "classifica"
    # ... and this categoria rides it one at a time, whatever the next one does
    assert item.teams_per_start == 1
    from core import race as R
    assert R.starts_per_race(empty.session_state["prog_draft"],
                             "DA", "chilometro") == 1


def test_the_last_races_are_one_tap_away(app, iscritti_path):
    """Three selectboxes to go back to the sheet left two minutes ago is two too many.

    A championship is not run one specialità at a time: the risultati of a
    batteria are typed while another event is on the track. The pills are the
    races last *written*, so the row is exactly the ones being worked on.
    """
    def save(cat, event, rnd):
        _open_race(app, iscritti_path, cat, event, rnd)
        # the one Salva of the page, pinned at the foot of the sidebar
        app.button(key="savebar_save").click().run()
        assert not app.exception

    save("AL", "velocita", "Qualificazioni")
    save("ES", "madison", "Finale")
    # the row is drawn at the top of the page, so a race saved further down it
    # joins the row on the next run - one more of them, and it is there
    app.run()

    # st.pills is a button_group in the element tree, and its options carry
    # the formatted label rather than the value behind it
    pills = app.button_group(key="ga_recent")
    labels = [o.content for o in pills.options]
    # both races worked on are on the row, named as the jury names the sheet
    # (the order they come in is `store.recent_races`, tested there)
    assert any(t.startswith("ES · Madison") for t in labels)
    assert any(t.startswith("AL · Velocità") for t in labels)

    # picking one moves the three pickers under it. The pill holds the race id
    # and shows the label, so it is set by the id - which is what the page
    # reads back to seed `ga_cat`, `ga_event` and `ga_round`.
    from core.models import race_id

    pills.set_value([race_id("AL", "velocita", "Qualificazioni")]).run()
    assert not app.exception
    assert app.selectbox(key="ga_cat").value == "AL"
    assert app.selectbox(key="ga_event").value == "velocita"
    assert app.selectbox(key="ga_round").value == "Qualificazioni"


def test_an_inseguimento_can_be_ridden_as_a_direct_final(app, iscritti_path):
    """«Finale diretta»: one race against the clock, and the classifica.

    A categoria that has not got four squadre does not ride finals: it rides
    once, the times are taken and the classification comes straight out of
    them. The programme says so by scheduling one fase, and the race page has
    to run it like the qualification it replaces - not like a finals round
    waiting for somebody to load four teams into it.
    """
    from core import rounds as RD
    from core.config import load_competition
    from core.programme import dump
    from core.store import competitions_root, open_competition

    path = competitions_root() / "CITA26" / "programme.yaml"
    comp = load_competition(path)
    item = comp.scheduled("AL", "ins_squadre")
    item.rounds = RD.propose(comp, "AL", "ins_squadre",
                             RD.Options(direct_final=True))
    assert [r.key for r in item.rounds] == ["Finale"]
    path.write_text(dump(comp), encoding="utf-8")

    rid = _open_race(app, iscritti_path, "AL", "ins_squadre", "Finale")
    assert not app.exception
    assert any("Tempi" in s.value for s in app.subheader)
    # the whole field rides it: there is nothing to qualify into a direct final
    from core import race as R
    from core.entries import import_master

    [b for b in app.sidebar.button if "Salva" in b.label][0].click().run()
    state = open_competition("CITA26").load_race(rid)
    comp = load_competition(path)
    riding = R.entrants(import_master(iscritti_path, comp), comp,
                        "AL", "ins_squadre", "Finale")
    assert riding and list(state.entrants) == list(riding)
