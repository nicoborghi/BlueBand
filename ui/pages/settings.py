"""SETTINGS ("Impostazioni") - what holds for the whole competition.

The page is ordered by what it is: from what the app is working on, down to what
can destroy work. Eight sections, in this order and no other:

1. **Manifestazione** - which one is loaded, and whether its programme reads.
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
6. **Programma** - read-only, what the YAML says, with the derived distances.
   The register is *not* here: Documenti → Registro comunicati is the one
   place that says what is planned, what has gone out, and prints it.
7. **Dati e backup** - the folder, the copy, the journal.
8. **Azzera una gara** - last, alone, and the only thing here that deletes.

Everything on this page is either a local choice stored in `settings.json` or a
view of the programme; nothing here is part of a race.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core import config as C
from core import entries as E
from core import race as R
from core import recap as RC
from core.config import EVENT_ENTRY_LIST, Competition, validate
from core.i18n import help_text, label, msg, ui
from core.store import Store, list_competitions
from render.render import data_uri
from ui import notify, state


GROUP_LABELS = {RC.BY_REGION: ui("team_group_region"),
                RC.BY_CLUB: ui("team_group_club"),
                RC.BY_PROVINCE: ui("team_group_province"),
                RC.BY_NATION: ui("team_group_nation")}


def render(competition: str, comp: Competition, store: Store) -> None:
    _competition(competition, comp)
    _entries(comp, store)
    _team(comp, store)
    _output_folder(store)
    _appearance(comp, store)
    _programme(comp)
    _data_and_backup(store)
    _reset_event(comp, store)


# ── 1. which competition is loaded ──────────────────────────────────────────

def _competition(competition: str, comp: Competition) -> None:
    """The competition is set once, here - not on every page."""
    competitions = list_competitions()
    pick = st.selectbox(ui("competition"), competitions, key="set_competition",
                        index=competitions.index(competition),
                        help=help_text("competition_folder"))
    if pick != competition:
        state.choose_competition(pick)

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
                         key="team_group", format_func=GROUP_LABELS.get,
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
                   group=GROUP_LABELS.get(group, group)))


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


SIG_MODE_LABELS = {C.SIG_IMAGE: ui("sig_mode_image"),
                   C.SIG_TEXT: ui("sig_mode_text")}
SIG_SCOPE_LABELS = {C.SIG_ALWAYS: ui("sig_scope_always"),
                    C.SIG_RESULTS: ui("sig_scope_results"),
                    C.SIG_NEVER: ui("sig_scope_never")}


def _signature(comp: Competition, store: Store) -> None:
    """How the «Per la giuria» block is signed, and where it is offered."""
    b = comp.branding
    st.caption(msg("signature_caption", label=b.signature_label))

    modes = list(C.SIG_MODES)
    mode = st.radio(ui("signature_how"), modes,
                    index=modes.index(b.signature_mode)
                    if b.signature_mode in modes else 0,
                    key="sig_mode", horizontal=True,
                    format_func=SIG_MODE_LABELS.get)
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
            c2.markdown(f"{b.signature_label} **{value}**")
        else:
            notify.warn("signature_name_missing", where=c2)

    scopes = list(C.SIG_SCOPES)
    scope = st.selectbox(ui("signature_where"), scopes,
                         index=scopes.index(b.signature_scope)
                         if b.signature_scope in scopes else 0,
                         key="sig_scope", format_func=SIG_SCOPE_LABELS.get,
                         help=help_text("signature_scope"))
    if scope != b.signature_scope:
        store.set_setting("signature_scope", scope)
        state.refresh()


NAME_STYLE_LABELS = {C.NAME_SPLIT: ui("name_split"),
                     C.NAME_FULL: ui("name_full")}


def _name_style(comp: Competition, store: Store) -> None:
    """Two columns or one, on every printed sheet."""
    b = comp.branding
    styles = list(C.NAME_STYLES)
    style = st.radio(ui("name_style_how"), styles,
                     index=styles.index(b.name_style)
                     if b.name_style in styles else 0,
                     key="name_style", format_func=NAME_STYLE_LABELS.get,
                     captions=[ui("name_split_example"),
                               ui("name_full_example")])
    if style != b.name_style:
        store.set_setting("name_style", style)
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


# ── 6. what the programme says (read-only) ──────────────────────────────────

def _programme(comp: Competition) -> None:
    """The flat view of the programme, with the distances it works out.

    The Programma page edits it one day at a time; this reads it whole, with
    the giri and gli sprint that are *derived* from the track length and never
    written anywhere. The register used to be here too, and is not any more:
    Documenti → Registro comunicati says the same and more (emesso o no, il
    prossimo numero libero, i duplicati) and prints it.
    """
    st.subheader(ui("programme_table"))
    with st.expander(ui("races_scheduled"), expanded=False):
        rows = []
        for r in comp.programme:
            for p in r.rounds:
                d, laps, spr = comp.distances(r.cat, r.event, p.key)
                rows.append({
                    label("day"): r.day, label("cat"): r.cat,
                    label("event"): comp.event(r.event).short,
                    label("round"): p.label,
                    # None, not "": a column mixing numbers and empty strings
                    # has no Arrow type, and a missing value prints blank
                    label("distance"): d or None,
                    label("laps"): laps or None,
                    label("sprint"): spr or None,
                    ui("documents"): ", ".join(p.docs),
                })
        df = pd.DataFrame(rows)
        # the missing values made these float columns: 25 laps read better than
        # 25.0, and Int64 keeps the blanks
        for col in (label("laps"), label("sprint")):
            if df[col].dropna().mod(1).eq(0).all():
                df[col] = df[col].astype("Int64")
        st.dataframe(df, hide_index=True, use_container_width=True)


# ── 7. the data folder and its copies ───────────────────────────────────────

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


# ── 8. the one thing here that deletes ──────────────────────────────────────

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
