"""SETTINGS ("Impostazioni") - what holds for the whole competition.

The page is ordered by what it is: from what the app is working on, down to what
can destroy work. Eight sections, in this order and no other:

1. **Manifestazione** - which one is loaded, and whether its programme reads,
   and the language it is all read in.
2. **Elenco iscritti** - which file the riders come from, and the one button
   that reads it again. It lives here and not on Verifica: choosing a file is a
   setting, and re-importing is safe by construction (the jury's edits are an
   overlay keyed by UCI ID, re-applied on top of every new export).
3. **Squadra** - regione, società, provincia o nazione: what the app groups
   riders by, and the word every sheet calls that column.
4. **Cartella dei comunicati** - where a saved sheet lands. The one setting
   that has to be right before the first comunicato goes out.
5. **Aspetto dei comunicati** - the letterhead, the signature, how a name is
   set. All of it is "how a sheet looks", so it is one section: before, the two
   images were on the page and the signature was hidden behind an expander
   called *avanzate*, which is not a different kind of choice.
6. **Dati e backup** - the folder, the copy, the journal.
7. **Azzera una gara** - last, alone, and the only thing here that deletes.

The programme is *not* here, in any form. It is read and written on the
Programma page, which is also where it is printed; the register is on Documenti
→ Registro comunicati. A read-only copy of either on this page was one more
thing to keep in step, and a second place to look for the same answer.

Everything on this page is a local choice stored in `settings.json`; nothing
here is part of a race, and nothing here is part of the programme.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core import config as C
from core import decisions as DEC
from core import entries as E
from core import race as R
from core import recap as RC
from core.config import EVENT_ENTRY_LIST, Competition, validate
from core.i18n import (LANGUAGES, help_text, label, language, msg,
                       note_kind_name, ui)
from core.store import Store, list_competitions, open_competition
from render.render import darken, data_uri
from ui import notify, state


# What each option of a picker is called: the value is a key of the catalogue,
# looked up when the widget is drawn (`format_func=_named`) rather than at
# import, so the page follows a change of language on the next rerun.
GROUP_LABELS = {RC.BY_REGION: "team_group_region",
                RC.BY_CLUB: "team_group_club",
                RC.BY_PROVINCE: "team_group_province",
                RC.BY_NATION: "team_group_nation"}


def _named(labels: dict[str, str]):
    """`format_func` reading the catalogue: value -> the word for its key."""
    return lambda value: ui(labels[value]) if value in labels else str(value)


#: Whose it is and under what licence. On this page and no other: it is the
#: page a jury opens when it wants to know what it is running, and the sidebar
#: is empty from the page list down. On the others that column is controls.
AUTHOR = "Nicola Borghi"
AUTHOR_URL = "https://nicoborghi.github.io/"


def render(competition: str, comp: Competition, store: Store) -> None:
    _competition(competition, comp)
    _language(store)
    _entries(comp, store)
    _team(comp, store)
    _output_folder(store)
    _appearance(comp, store)
    _data_and_backup(store)
    _reset_event(comp, store)
    _credit()


def _credit() -> None:
    """The licence notice, at the foot of the sidebar."""
    st.sidebar.markdown(
        f'<div class="cmsr-credit">'
        + ui("credit", name=f'<a href="{AUTHOR_URL}" target="_blank">'
                            f'{AUTHOR}</a>')
        + '</div>', unsafe_allow_html=True)


# ── 1. which competition is loaded ──────────────────────────────────────────

def _competition(competition: str, comp: Competition) -> None:
    """The competition is set once, here - not on every page."""
    competitions = list_competitions()
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    pick = c1.selectbox(ui("competition"), competitions, key="set_competition",
                        index=competitions.index(competition),
                        help=help_text("competition_folder"))
    if pick != competition:
        state.choose_competition(pick)
    with c2.popover(ui("new_competition")):
        _new_competition(competitions)

    c1, c2, c3 = st.columns(3)
    c1.metric(ui("track"), f"{comp.track_len * 1000:.0f} m")
    c2.metric(ui("races_scheduled"), len(comp.programme))
    c3.metric(ui("communiques_planned"), len(comp.communiques))
    st.caption(ui("competition_line", name=comp.name, location=comp.location,
                  dates=", ".join(comp.dates))
               + "  \n" + ui("programme_path", path=comp.path))

    problems = validate(comp)
    for p in problems:
        notify.text(p)


def _language(store: Store) -> None:
    """What the app and the sheets are written in.

    A setting of the competition and not of the machine: an international
    meeting is run in English and the championship next month in Italian, on
    the same laptop, and neither should have to be switched back by hand. It
    is stored in `settings.json` and read before anything draws a word
    (`ui.state.competition`).

    It moves the *catalogue*, nothing else: the names of the categories, the
    events and the rounds are written out in `programme.yaml` and print as
    they stand there.
    """
    codes = list(LANGUAGES)
    current = language()
    pick = st.selectbox(ui("language"), codes,
                        index=codes.index(current) if current in codes else 0,
                        key="set_language", format_func=LANGUAGES.get,
                        help=help_text("language"))
    st.caption(msg("language_caption"))
    if pick != current:
        store.set_setting("language", pick)
        state.refresh()


def _new_competition(competitions: list[str]) -> None:
    """Start next year's championship, from inside the app.

    It creates the folder and nothing else: with no `programme.yaml` in it the
    app opens on `ui.pages.setup`, which asks for the pista and the categorie
    and writes the first one. `open_competition` is what makes the folder -
    `Store.__init__` creates the tree it needs.
    """
    st.caption(help_text("new_competition"))
    name = st.text_input(ui("new_competition_name"), key="new_comp_name",
                         placeholder="CITA27")
    name = "".join(name.split())
    if st.button(ui("create"), key="new_comp_go", type="primary",
                 disabled=not name):
        if name in competitions:
            notify.error("competition_exists", name=name)
            return
        open_competition(name)
        notify.ok("competition_created", name=name)
        state.choose_competition(name)


# ── 2. the entry file: where it is, and reading it again ────────────────────

def _entries(comp: Competition, store: Store) -> None:
    """Import and re-import the elenco iscritti.

    It is a setting, not a step of the verifica: the file is chosen once, and
    then *reloaded* every time the federation sends a new export. Reloading is
    safe by construction - the import is a read-only snapshot and every jury
    edit lives in the overlay, keyed by UCI ID, so dorsali, regioni and
    specialità typed in the app are re-applied on top of the new file.
    """
    st.subheader(ui("entries"))
    st.caption(msg("entries_caption"))

    current = E.source_path(store, comp)
    value = st.text_input(ui("entries_source"), value=current,
                          key="entries_src", help=help_text("entries_source"))
    path = Path(value.strip()).expanduser() if value.strip() else None
    exists = path is not None and path.exists()

    c1, c2, c3 = st.columns([1, 1, 2])
    if not exists and value.strip():
        notify.error("file_not_found", where=c1)
    elif exists and E.source_changed(store, path):
        notify.warn("source_changed", where=c1)

    if c1.button(ui("import_reload"), key="entries_import",
                 type="primary", disabled=not exists):
        with st.spinner(ui("reading_entries")):
            if value.strip() != current:
                E.set_source_path(store, value)
            el = E.import_entries(path, comp)
            E.save_import(store, el)
        notify.ok("entries_imported", n=len(el.riders), file=path.name)

    el = E.load_import(store)
    if el is None:
        notify.info("import_entries_here")
        return
    c2.caption(ui("last_import", when=el.imported_at or ui("never_saved"))
               + "  \n" + ui("import_summary", n=len(el.riders),
                             file=Path(el.source_file).name))
    if c3.button(ui("export_effective"), key="entries_export"):
        eff, _ = E.effective_entries(store, comp)
        store.out_dir.mkdir(parents=True, exist_ok=True)
        out = store.out_dir / "iscritti_effettivo.xlsx"
        E.export_xlsx(eff, comp, out)
        notify.ok("exported_to", path=out)

    patches = E.load_overlay(store)
    if patches:
        st.caption(ui("overlay_kept", n=len(patches)))

    _overlay_switch(store, len(patches))


def _overlay_switch(store: Store, n_patches: int) -> None:
    """Whether the jury's edits are a layer on top, or go into the file.

    On, they are patches applied over each import - the app never writes the
    workbook. Off, Verifica edits the workbook itself: the cell is written,
    the file is re-imported, and the patches already recorded are set aside
    rather than thrown away - they come back whole when this goes back on.
    """
    on = E.overlay_on(store)
    new = st.toggle(ui("use_overlay"), value=on, key="use_overlay",
                    help=help_text("use_overlay"))
    if new != on:
        E.set_overlay_on(store, new)
        state.refresh()
    if not new:
        # verificati and NP live in the overlay and nowhere else: the workbook
        # has no column for either, so with it off the licence check reads
        # empty. It is not lost - it is not being applied.
        notify.warn("overlay_off", n=n_patches)


# ── 3. what a squadra is, and what it is called ─────────────────────────────

def _team(comp: Competition, store: Store) -> None:
    """Regione, società, provincia or nazione - and the word printed for it.

    A rule at an Italian championship (the rappresentative enter the riders)
    and a different one at an open meeting (the società do), so the programme
    states it (`entries.team_group`) and this overrides it on this machine.
    The name is a second, separate choice: what a sheet *calls* that column.
    """
    st.subheader(ui("team"))
    groups = list(RC.GROUPS)
    current = _team_group(comp, store)
    group = st.selectbox(ui("team_group"), groups,
                         index=groups.index(current) if current in groups
                         else 0,
                         key="team_group", format_func=_named(GROUP_LABELS),
                         help=help_text("team_group"))
    if group != current:
        store.set_setting("team_group", group)
        state.refresh()

    c1, c2 = st.columns([1, 2])
    name = c1.text_input(ui("team_name"), value=comp.team_name,
                         key="team_name", help=help_text("team_name"))
    if c2.button(ui("save_named", what=ui("team_name").lower()),
                 key="save_team_name", disabled=name.strip() == comp.team_name):
        store.set_setting("team_name", name.strip())
        state.refresh()
    st.caption(msg("team_caption", name=comp.team_name,
                   group=_named(GROUP_LABELS)(group)))


def _team_group(comp: Competition, store: Store) -> str:
    return store.settings.get("team_group") or comp.team_group


# ── 4. where a saved comunicato lands ───────────────────────────────────────

def _output_folder(store: Store) -> None:
    """Where the comunicati are written. Free choice: a Drive folder, a stick."""
    st.subheader(ui("out_folder"))
    default = store.root / "out"
    current = store.out_dir

    value = st.text_input(ui("path"), value=str(current), key="out_dir_input",
                          help=help_text("out_folder"))
    path = Path(value).expanduser() if value.strip() else default

    problem = _check_dir(path)
    if problem:
        notify.text(problem, level="error")
    elif path != current:
        notify.info("folder_confirm")

    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button(ui("save_folder"), type="primary", disabled=bool(problem)):
        store.set_out_dir(None if path == default else path)
        notify.ok("folder_saved", path=store.out_dir)
        st.rerun()
    if c2.button(ui("restore_default")):
        store.set_out_dir(None)
        st.rerun()

    if current.exists():
        files = sorted(p for p in current.iterdir() if p.is_file())
        c3.caption(ui("documents_in_folder", n=len(files)))
        if files:
            with st.expander(ui("produced_documents")):
                st.dataframe(pd.DataFrame([{
                    ui("file"): f.name,
                    "kB": round(f.stat().st_size / 1024, 1),
                    ui("modified"): datetime.fromtimestamp(f.stat().st_mtime)
                    .strftime("%d/%m/%Y %H:%M"),
                } for f in sorted(files, key=lambda f: f.stat().st_mtime,
                                  reverse=True)]),
                    hide_index=True, use_container_width=True)
    else:
        c3.caption(ui("folder_will_be_created"))


def _check_dir(path: Path) -> str:
    """Why this folder cannot be used, or '' when it is fine."""
    if path.exists() and not path.is_dir():
        return msg("folder_not_a_dir", path=path)
    probe = path if path.exists() else _first_existing_parent(path)
    if probe is None:
        return msg("folder_no_parent", path=path)
    if not os.access(probe, os.W_OK):
        return msg("folder_not_writable", path=probe)
    return ""


def _first_existing_parent(path: Path) -> Path | None:
    for p in path.parents:
        if p.exists():
            return p
    return None


# ── 5. how a comunicato looks ───────────────────────────────────────────────

def _appearance(comp: Competition, store: Store) -> None:
    """What every sheet of this competition looks like.

    The letterhead carries the venue and the dates, the signature changes with
    the jury president, the name style is a matter of taste: three choices, one
    section, set once and left alone. They are not part of the programme - a
    different jury signs a different year - so they live in `settings.json`
    (`ui.state.BRANDING_SETTINGS`).
    """
    st.subheader(ui("appearance"))
    st.caption(msg("appearance_caption"))
    with st.expander(ui("letterhead"), expanded=False):
        st.caption(msg("letterhead_caption"))
        for key, title, help_key in (("header_img", ui("header_img"),
                                      "header_img"),
                                     ("footer_img", ui("footer_img"),
                                      "footer_img")):
            _image_setting(comp, store, key, title, help_text(help_key))
    with st.expander(ui("signature"), expanded=False):
        _signature(comp, store)
    with st.expander(ui("name_style"), expanded=False):
        _name_style(comp, store)
    with st.expander(ui("note_colors"), expanded=False):
        _note_colors(comp, store)


def _note_colors(comp: Competition, store: Store) -> None:
    """How a decision is printed on a comunicato: its tint, and its code.

    One colour per kind and no more: the rule down the side of the box is
    derived from it (`render.render.darken`), so the pair cannot drift apart
    and there is one decision to make per provvedimento instead of two.

    Written as a whole dict rather than key by key - a settings file holding
    half a palette is one whose other half silently follows a default that may
    change - and the preview under the pickers is the box as it prints.

    The compact UCI code (`A1`, `C3`) is off: a comunicato carries the decision
    written out, and the article it was taken under is in the jury's own
    register. A panel that quotes it on paper turns it on here, once.
    """
    b = comp.branding
    st.caption(msg("note_colors_caption"))
    codes = st.checkbox(ui("decision_codes"), value=b.decision_codes,
                        key="decision_codes",
                        help=help_text("decision_codes"))
    if codes != b.decision_codes:
        store.set_setting("decision_codes", codes)
        state.refresh()
    picked = {}
    for i, kind in enumerate(DEC.NOTE_KINDS):
        col = st.columns([1, 3])
        picked[kind] = col[0].color_picker(
            note_kind_name(kind), b.note_colors.get(kind, ""),
            key=f"note_color_{kind}")
        col[1].html(_swatch(kind, picked[kind]))
    c1, c2 = st.columns([1, 1])
    if c1.button(ui("save"), key="save_note_colors",
                 disabled=picked == b.note_colors):
        store.set_setting("note_colors", picked)
        state.refresh()
    if c2.button(ui("note_colors_reset"), key="reset_note_colors",
                 disabled=b.note_colors == C.NOTE_COLORS):
        store.set_setting("note_colors", dict(C.NOTE_COLORS))
        state.refresh()


def _swatch(kind: str, color: str) -> str:
    """The box as the sheet prints it - the one preview that answers the question."""
    return (f'<div style="background:{color};'
            f'border-left:3px solid {darken(color)};'
            'padding:2px 8px;border-radius:2px;font-weight:600;'
            'font-size:0.85rem;color:#222">'
            f'{note_kind_name(kind)}</div>')


SIG_MODE_LABELS = {C.SIG_IMAGE: "sig_mode_image", C.SIG_TEXT: "sig_mode_text"}
SIG_SCOPE_LABELS = {C.SIG_ALWAYS: "sig_scope_always",
                    C.SIG_RESULTS: "sig_scope_results",
                    C.SIG_NEVER: "sig_scope_never"}


def _signature(comp: Competition, store: Store) -> None:
    """How the «Per la giuria» block is signed, and where it is offered."""
    b = comp.branding
    st.caption(msg("signature_caption", label=b.signature_caption))

    modes = list(C.SIG_MODES)
    mode = st.radio(ui("signature_how"), modes,
                    index=modes.index(b.signature_mode)
                    if b.signature_mode in modes else 0,
                    key="sig_mode", horizontal=True,
                    format_func=_named(SIG_MODE_LABELS))
    if mode != b.signature_mode:
        store.set_setting("signature_mode", mode)
        state.refresh()

    if mode == C.SIG_IMAGE:
        value = st.text_input(ui("signature_file"), value=b.signature,
                              key="sig_input", help=help_text("signature_file"))
        c1, c2 = st.columns([1, 3])
        if c1.button(ui("save_signature"), disabled=value == b.signature):
            store.set_setting("signature", value.strip())
            state.refresh()
        path = _asset_path(value)
        if path is not None:
            _preview(c2, path, width=180)
        elif value:
            notify.error("signature_file_missing", where=c2)
    else:
        value = st.text_input(ui("signature_name"), value=b.signature_name,
                              key="sig_name", help=help_text("signature_name"))
        c1, c2 = st.columns([1, 3])
        if c1.button(ui("save_name"), disabled=value == b.signature_name):
            store.set_setting("signature_name", value.strip())
            state.refresh()
        if value:
            c2.markdown(f"{b.signature_caption} **{value}**")
        else:
            notify.warn("signature_name_missing", where=c2)

    scopes = list(C.SIG_SCOPES)
    scope = st.selectbox(ui("signature_where"), scopes,
                         index=scopes.index(b.signature_scope)
                         if b.signature_scope in scopes else 0,
                         key="sig_scope", format_func=_named(SIG_SCOPE_LABELS),
                         help=help_text("signature_scope"))
    if scope != b.signature_scope:
        store.set_setting("signature_scope", scope)
        state.refresh()


NAME_STYLE_LABELS = {C.NAME_SPLIT: "name_split", C.NAME_FULL: "name_full"}


def _name_style(comp: Competition, store: Store) -> None:
    """Two columns or one, on every printed sheet."""
    b = comp.branding
    styles = list(C.NAME_STYLES)
    style = st.radio(ui("name_style_how"), styles,
                     index=styles.index(b.name_style)
                     if b.name_style in styles else 0,
                     key="name_style", format_func=_named(NAME_STYLE_LABELS),
                     captions=[ui("name_split_example"),
                               ui("name_full_example")])
    if style != b.name_style:
        store.set_setting("name_style", style)
        state.refresh()

    if style == C.NAME_FULL:
        # one column has to hold "ROSSI Mario Luigi" and no more: what it does
        # not take goes to the columns the sheet is read for - le volate, i
        # punti, la società - so it is worth being able to tune it here
        width = st.slider(ui("name_width"), C.NAME_WIDTH_MIN,
                          C.NAME_WIDTH_MAX, float(b.name_width), 0.02,
                          key="name_width", help=help_text("name_width"))
        if width != b.name_width:
            store.set_setting("name_width", width)
            state.refresh()


def _image_setting(comp: Competition, store: Store, key: str, title: str,
                   help_txt: str) -> None:
    """One of the two images that frame every printed sheet.

    A relative path is read from the `track/` folder, where `header/` lives, so
    a new championship is a new SVG here and not a code change.
    """
    current = getattr(comp.branding, key)
    value = st.text_input(title, value=current, key=f"brand_{key}",
                          help=help_txt)
    c1, _ = st.columns([1, 3])
    if c1.button(ui("save_named", what=title.lower()), key=f"save_{key}",
                 disabled=value == current):
        store.set_setting(key, value.strip())
        state.refresh()
    path = _asset_path(value)
    if path is not None:
        # a banner is as wide as the sheet: it goes under the field, full width,
        # rather than squeezed into a column next to it
        _preview(st, path, width=700)
    elif value:
        notify.error("image_missing")


def _preview(container, path: Path, width: int) -> None:
    """Show the image the way the comunicato will.

    Through the renderer's own `data_uri`, not `st.image`: the banners are
    Inkscape SVGs, which `st.image` cannot draw at all and which lose their
    namespaces if injected as raw markup.
    """
    container.html(f'<img src="{data_uri(path)}" '
                   f'style="width:100%;max-width:{width}px;display:block">')


def _asset_path(value: str) -> Path | None:
    """Resolve a branding path the way the renderer does: absolute, or under
    `track/` for the paths written as `header/head_CITA24.svg`."""
    if not value:
        return None
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p if p.exists() else None


# ── 6. the data folder and its copies ───────────────────────────────────────

def _data_and_backup(store: Store) -> None:
    st.subheader(ui("backup"))
    st.caption(msg("backup_caption", root=store.root, out=store.out_dir))
    c1, c2 = st.columns([1, 2])
    dest = c2.text_input(ui("backup_dest"), value=str(store.root) + "_backup")
    if c1.button(ui("backup_button")):
        out = store.backup(dest)
        notify.ok("backup_done", path=out)

    journal = store.read_journal(50)
    if journal:
        with st.expander(ui("journal", n=len(journal))):
            # `extra` puts a value in one row only: the other rows would be
            # NaN in a column of strings, which has no Arrow type
            st.dataframe(pd.DataFrame(journal).fillna(""), hide_index=True,
                         use_container_width=True)


# ── 7. the one thing here that deletes ──────────────────────────────────────

def _reset_event(comp: Competition, store: Store) -> None:
    """Throw away everything typed for one (category, event).

    A race run on the wrong entrants, a test ridden before the championship: the
    jury needs to start it again from an empty sheet. The whole event goes, not
    the round on screen - qualifying rounds and heats included, since a final
    that keeps its qualification is not a clean restart.

    Last on the page, and alone in its section: it is the only control here
    that destroys work, and it must never sit next to one that does not.
    """
    st.subheader(ui("reset_event"))
    st.caption(msg("reset_caption"))

    done = st.session_state.pop("reset_done", "")
    if done:
        notify.text(done, level="info")

    c1, c2 = st.columns(2)
    cats = comp.cat_order()
    cat = c1.selectbox(ui("category"), cats, key="reset_cat")
    events = [s for s in comp.events_for(cat) if s != EVENT_ENTRY_LIST]
    if not events:
        notify.info("no_event_for_category", cat=cat)
        return
    event = c2.selectbox(ui("event"), events, key="reset_event",
                         format_func=lambda s: comp.event(s).short)

    races = R.saved_races(store, cat, event)
    if not races:
        st.caption(msg("no_saved_race"))
        return

    st.dataframe(pd.DataFrame([{
        label("round"): s.round_key or ui("none_short"),
        ui("col_starters"): len(s.entrants),
        ui("col_results"): ui("yes_short") if R.has_results(s)
        else ui("none_short"),
        ui("col_last_saved"): _short_ts(s.updated_at),
        ui("file"): f"races/{s.race_id}.json",
    } for s in races]), hide_index=True, use_container_width=True)

    with_results = [s for s in races if R.has_results(s)]
    name = comp.event(event).short
    confirm = st.checkbox(
        ui("reset_confirm", n=len(races), cat=cat, event=name)
        + (ui("reset_with_results", n=len(with_results)) if with_results
           else ""),
        key="reset_ok")
    if st.button(ui("reset_button"), type="primary", disabled=not confirm):
        removed = R.reset_event(store, cat, event)
        _forget_widgets([s.race_id for s in races])
        st.session_state.pop("reset_ok", None)   # the tick goes back to unset
        st.session_state["reset_done"] = msg("races_reset", n=len(removed),
                                             cat=cat, event=name)
        st.rerun()


def _forget_widgets(race_ids: list[str]) -> None:
    """Drop the inputs the Gare page keeps in the session for those races.

    The state file is gone, but a text area still holding the old heats would
    write it straight back on the next save.
    """
    for key in [k for k in st.session_state
                if any(rid in k for rid in race_ids)]:
        del st.session_state[key]


def _short_ts(value: str) -> str:
    """`2026-08-04T15:12:03` as the jury reads it."""
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return value or ""
