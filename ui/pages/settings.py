"""SETTINGS ("Impostazioni") - what holds beyond this competition.

The page is ordered by what it is: from what the app is working on, down to what
can destroy work. Six sections, in this order and no other:

1. **competition** - which one is loaded, whether its programme reads, and
   the language it is all read in.
2. **Cartella dei comunicati** - where a saved sheet lands. The one setting
   that has to be right before the first comunicato goes out.
3. **Aspetto dei comunicati** - the letterhead, the signature, how a name is
   set, the colours of a decision, the **caratteri** each element is set in,
   and the **note di default** a sheet opens on (`core.notes`). All of it is
   "how a sheet looks", so it is one section - and it ends on the one control
   that puts the whole of it back to what the app ships: the
   two images were on the page, the signature was hidden behind an expander
   called *avanzate* and the wordings were a section of their own halfway down,
   which is three places for one question.
4. **event** - what each one *is*: sigla UCI, formato, atleti per squadra,
   the column it is called in the entry file. The same at every championship,
   so it is a table of the installation (`regulations/events.json`) and not
   seven fields typed into every new programme.
5. **Dati e backup** - the folder, the copy, the journal.
6. **Azzera una gara** - last, alone, and the only thing here that deletes.

**Nothing about one competition is here.** The elenco iscritti is built in
Programma → Gara, and so is what a squadra is at this meeting: both are
statements about the championship being run, and they live in its programme.
What is left on this page is either a choice of this machine (`settings.json`)
or a table of this installation (`regulations/`) - and either way it outlives
the competition that is open.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core import config as C
from core import catalogue as CAT
from core import decisions as DEC
from core import notes as NOTES
from core import race as R
from core import recap as RC
from core.config import EVENT_ENTRY_LIST, Competition, validate
from core.i18n import (LANGUAGES, help_text, label, language,
                       language_name, msg, note_kind_name, ui)
from core.store import Store, list_competitions, open_competition
from render.render import darken, data_uri, image_style
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
    _output_folder(store)
    _appearance(comp, store)
    _events()
    _data_and_backup(store)
    _reset_event(comp, store)
    _credit()


def _credit() -> None:
    """The licence notice, at the foot of the sidebar."""
    st.sidebar.markdown(
        '<div class="cmsr-credit">'
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


# ── 2. where a saved comunicato lands ───────────────────────────────────────

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


# ── 3. how a comunicato looks ───────────────────────────────────────────────

def _appearance(comp: Competition, store: Store) -> None:
    """What every sheet of this competition looks like.

    The letterhead carries the venue and the dates, the signature changes with
    the jury president, the name style and the characters are a matter of
    taste: a handful of choices, one section, set once and left alone. The last
    control of the section puts every one of them back (`_restore_appearance`),
    which is what a laptop handed on from last year's championship needs. They are not part of the programme - a
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
    with st.expander(ui("sheet_slots"), expanded=False):
        _sheet_slots(comp, store)
    with st.expander(ui("signature"), expanded=False):
        _signature(comp, store)
    with st.expander(ui("name_style"), expanded=False):
        _name_style(comp, store)
    with st.expander(ui("note_colors"), expanded=False):
        _note_colors(comp, store)
    # the wording of the lines is the same kind of choice as the letterhead and
    # the signature - how a sheet reads - and it used to be a section of its
    # own halfway down the page, which put two answers to "what does a
    # comunicato look like" in two different places
    with st.expander(ui("sheet_lines"), expanded=False):
        _sheet_lines(store)
    with st.expander(ui("fonts"), expanded=False):
        _fonts(comp, store)
    _restore_appearance(store)


#: What a font setting is called in the picker: the key of `config.FONTS`, said
#: in words. The value is looked up when the widget is drawn, so the list
#: follows a change of language on the next rerun.
FONT_LABELS = {key: f"font_{key}" for key in C.FONTS}


def _fonts(comp: Competition, store: Store) -> None:
    """The character and the colour every element of a sheet is set in.

    A picker of what is being set - il titolo, il sottotitolo, il riquadro
    della decisione - and beside it how it is set, because that is the shape of
    the question: a jury changes the titolo of a championship once and never
    looks at the other thirteen. `Imposta` writes both, `Ripristina
    predefinito` takes that one element back to what the app ships, and the
    table under them is the whole set as it stands, so what has been changed is
    readable without opening the picker fourteen times.

    Everything typed here goes into the style of the page
    (`render.font_css_vars`, `render.color_css_vars`), so what does not read as
    a font or as a colour is refused here and never written
    (`config.font_value`, `config.text_color`).

    The colour is stored only where it *differs*: il titolo and the riquadro
    «Comunicato n.» are printed in the colour of the competition, and one saved
    as today's hex would stop following the letterhead the day it changes.
    """
    b = comp.branding
    st.caption(msg("fonts_caption"))
    keys = list(C.FONTS)
    key = st.selectbox(ui("font_element"), keys, key="font_element",
                       format_func=_named(FONT_LABELS),
                       help=help_text("font_element"))
    default = C.FONTS[key]
    current = b.fonts.get(key, default)
    default_color = C.default_text_color(key, b.color)
    current_color = b.text_colors.get(key, default_color)

    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    value = c1.text_input(ui("font_value"), value=current,
                          key=f"font_value_{key}",
                          help=msg("font_default", value=default))
    color = c2.color_picker(ui("font_color"), current_color,
                            key=f"font_color_{key}",
                            help=help_text("font_color"))
    typed = value.strip()
    ok = bool(C.font_value(key, typed))
    if typed and not ok:
        notify.error("font_not_readable", value=typed)

    changed = ok and (typed != current or color != current_color)
    c1, c2 = st.columns([1, 1])
    if c1.button(ui("set"), key="save_font", disabled=not changed):
        store.set_setting("fonts", {**b.fonts, key: typed})
        store.set_setting("text_colors", _with_color(b, key, color) or None)
        state.refresh()
    if c2.button(ui("restore_default"), key="reset_font",
                 disabled=(current, current_color) == (default, default_color)):
        store.set_setting("fonts", {**b.fonts, key: default})
        store.set_setting("text_colors",
                          _with_color(b, key, default_color) or None)
        st.session_state.pop(f"font_value_{key}", None)
        st.session_state.pop(f"font_color_{key}", None)
        state.refresh()

    # the element as the sheet sets it: the one preview that answers "is 17pt
    # too big for this title", which is not a question a number answers
    st.html(_font_sample(b.fonts, key, typed if ok else current, color))
    st.dataframe(pd.DataFrame([{
        ui("font_element"): ui(FONT_LABELS[k]),
        ui("font_value"): b.fonts.get(k, C.FONTS[k]),
        ui("font_color"): b.text_colors.get(
            k, C.default_text_color(k, b.color)),
        ui("font_default"): C.FONTS[k],
    } for k in keys]), hide_index=True, use_container_width=True)


def _with_color(b: C.Branding, key: str, color: str) -> dict[str, str]:
    """The colours as they will be stored, with `key` set to `color`.

    A colour that *is* the default is not written down: two of them are «the
    colour of the letterhead», and a titolo filed as the hex it is today is a
    titolo that stops following the letterhead tomorrow. `Branding` drops it
    again on the way back in - this is the same rule, applied where the file is
    written rather than where it is read.
    """
    colors = {k: v for k, v in b.text_colors.items() if k != key}
    if color and color != C.default_text_color(key, b.color):
        colors[key] = color
    return colors


def _font_sample(fonts: dict[str, str], key: str, value: str,
                 color: str) -> str:
    """One line set the way the sheet would set it - typeface, size, colour."""
    family = fonts.get(C.FONT_FAMILY, C.FONTS[C.FONT_FAMILY])
    size = "" if key == C.FONT_FAMILY else f"font-size:{value};"
    used = value if key == C.FONT_FAMILY else family
    return (f'<div style="font-family:{used};{size}color:{color};'
            'padding:4px 0">'
            f'{ui(FONT_LABELS[key])} - {ui("font_sample")}</div>')


def _restore_appearance(store: Store) -> None:
    """Everything on this section back to what the app ships, in one write.

    The letterhead, the slots, the signature, the colours, the characters: a
    laptop that has been set up for last year's championship and is handed on
    is one place where every one of them is wrong, and putting them right one
    expander at a time is how half of them get left. Only what is in
    `settings.json` goes - the programme keeps what it says (`state.BRANDING_SETTINGS`).
    """
    st.caption(msg("restore_appearance_caption"))
    if st.button(ui("restore_all_defaults"), key="restore_appearance",
                 help=help_text("restore_all_defaults")):
        gone = store.clear_settings(state.BRANDING_SETTINGS)
        _forget_appearance_widgets()
        notify.ok("appearance_restored", n=len(gone))
        state.refresh()


#: The fields of this section that own their value once they exist: restoring
#: the defaults has to drop them, or the boxes go on showing what was typed
#: into them after the file underneath has been put back.
#: The picker of which element is being set is not among them: it is where the
#: jury is looking, not something the reset is about.
APPEARANCE_WIDGETS = ("brand_", "fit_", "width_", "align_", "off_", "sig_",
                      "name_style", "name_width", "note_color_",
                      "decision_codes", "slot_", "gap_", "font_value_",
                      "font_color_")


def _forget_appearance_widgets() -> None:
    for k in list(st.session_state):
        if k.startswith(APPEARANCE_WIDGETS):
            del st.session_state[k]


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


FIT_LABELS = {C.FIT_PAGE: "fit_page", C.FIT_SIZE: "fit_size"}
ALIGN_LABELS = {C.ALIGN_LEFT: "align_left", C.ALIGN_CENTER: "align_center",
                C.ALIGN_RIGHT: "align_right"}

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


#: The items a slot can hold, and what each is called on screen.
SLOT_LABELS = {C.SLOT_NONE: "slot_none",
               C.SLOT_COMMUNIQUE: "slot_communique",
               C.SLOT_PRINTED_AT: "slot_printed_at"}

#: The three positions of a line, and the word for each.
SIDE_LABELS = {C.ALIGN_LEFT: "slot_left", C.ALIGN_CENTER: "slot_center",
               C.ALIGN_RIGHT: "slot_right"}

#: The two lines, and the label of the air asked for under / over each.
SLOT_LINES = (("head", "slot_head", "head_gap"),
              ("foot", "slot_foot", "foot_gap"))


def _sheet_slots(comp: Competition, store: Store) -> None:
    """What prints on the two lines that frame the table, and how far in.

    «Comunicato n.» top right and «Emesso il …» bottom right is where the jury
    workbooks put them and what every sheet printed until now; a testata that
    already carries something in one of those corners had nowhere to move them
    to. Six pickers - three positions per line - and two millimetre boxes for
    the air between each line and its edge of the paper.

    An item can only be in one place, so choosing it in a second slot takes it
    out of the first (`config.Branding._settle_slots` does the same to a
    settings.json written by hand).
    """
    b = comp.branding
    st.caption(msg("sheet_slots_caption"))
    items = list(C.SLOT_ITEMS)
    for line, title, gap_key in SLOT_LINES:
        st.markdown(f"**{ui(title)}**")
        cols = st.columns(3)
        picked = []
        for col, side in zip(cols, C.SLOT_SIDES):
            current = getattr(b, f"{line}_{side}")
            picked.append(col.selectbox(
                ui(SIDE_LABELS[side]), items,
                index=items.index(current) if current in items else 0,
                key=f"slot_{line}_{side}", format_func=_named(SLOT_LABELS),
                help=help_text("sheet_slots")))
        mm = st.number_input(ui(gap_key), 0.0, C.SLOT_GAP_MAX,
                             float(getattr(b, gap_key)), step=1.0,
                             key=f"gap_{line}", help=help_text(gap_key))
        # The three slots are read together: an item moved into a new position
        # leaves the one it was in, in the same rerun, or the sheet would print
        # it twice until somebody noticed.
        moved = [side for side, value in zip(C.SLOT_SIDES, picked)
                 if value != getattr(b, f"{line}_{side}")]
        if moved:
            _drop_duplicates(picked, moved)
            for side, value in zip(C.SLOT_SIDES, picked):
                store.set_setting(f"{line}_{side}", value)
            state.refresh()
        if mm != getattr(b, gap_key):
            store.set_setting(gap_key, float(mm))
            state.refresh()


def _drop_duplicates(picked: list[str], moved: list[str]) -> None:
    """Blank, in place, every slot that repeats an item the jury just moved.

    The pick that changed is the one that stands: a jury that puts «Emesso il»
    on the left has said it wants it there, not that it wants it twice.
    """
    for side in moved:
        item = picked[C.SLOT_SIDES.index(side)]
        if item == C.SLOT_NONE:
            continue
        for i, other in enumerate(picked):
            if other == item and C.SLOT_SIDES[i] != side:
                picked[i] = C.SLOT_NONE


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
    """One of the two images that frame every printed sheet, and how it sits.

    A relative path is read from the `track/` folder, where `header/` lives, so
    a new championship is a new SVG here and not a code change.

    *Adatta alla pagina* is the default and is what a letterhead wants: drawn
    to the paper width, edge to edge. A logo is not a letterhead - it has its
    own proportions - so the other fit gives it a width of its own, as a
    percentage of the sheet, and a side to sit on. Both are saved in
    `settings.json` (`ui.state.BRANDING_SETTINGS`), so the choice outlives the
    competition the way the image itself does.
    """
    which = key.split("_")[0]                   # header_img -> header
    b = comp.branding
    current = getattr(b, key)
    value = st.text_input(title, value=current, key=f"brand_{key}",
                          help=help_txt)
    c1, _ = st.columns([1, 3])
    if c1.button(ui("save_named", what=title.lower()), key=f"save_{key}",
                 disabled=value == current):
        store.set_setting(key, value.strip())
        state.refresh()

    fits = list(C.IMAGE_FITS)
    fit = st.radio(ui("image_fit"), fits, key=f"fit_{which}", horizontal=True,
                   index=fits.index(getattr(b, f"{which}_fit")),
                   format_func=_named(FIT_LABELS), help=help_text("image_fit"))
    if fit != getattr(b, f"{which}_fit"):
        store.set_setting(f"{which}_fit", fit)
        state.refresh()
    if fit == C.FIT_SIZE:
        c1, c2 = st.columns([1, 1])
        width = c1.slider(ui("image_width"), int(C.IMAGE_WIDTH_MIN),
                          int(C.IMAGE_WIDTH_MAX),
                          value=int(getattr(b, f"{which}_width")), step=5,
                          key=f"width_{which}", help=help_text("image_width"))
        aligns = list(C.ALIGNS)
        align = c2.selectbox(ui("image_align"), aligns, key=f"align_{which}",
                             index=aligns.index(getattr(b, f"{which}_align")),
                             format_func=_named(ALIGN_LABELS),
                             help=help_text("image_align"))
        if (width, align) != (getattr(b, f"{which}_width"),
                              getattr(b, f"{which}_align")):
            store.set_setting(f"{which}_width", float(width))
            store.set_setting(f"{which}_align", align)
            state.refresh()

    # How far it is held off its own edge of the paper - the testata from the
    # top, the piè from the bottom - which is a question either fit can be
    # asked: a full-width banner may want air above it just as a logo does.
    edge = "header_top" if which == "header" else "footer_bottom"
    off = st.number_input(ui(edge), min_value=0.0,
                          max_value=C.IMAGE_OFFSET_MAX,
                          value=float(getattr(b, edge)), step=1.0,
                          key=f"off_{which}", help=help_text(edge))
    if off != getattr(b, edge):
        store.set_setting(edge, float(off))
        state.refresh()

    path = _asset_path(value)
    if path is not None:
        # the preview is the sheet in miniature: same width, same side, so the
        # setting is judged where it is made rather than on the first PDF
        _preview(st, path, width=700, style=image_style(b, which))
    elif value:
        notify.error("image_missing")


def _preview(container, path: Path, width: int, style: str = "") -> None:
    """Show the image the way the comunicato will.

    Through the renderer's own `data_uri`, not `st.image`: the banners are
    Inkscape SVGs, which `st.image` cannot draw at all and which lose their
    namespaces if injected as raw markup.

    `style` is what the renderer puts on the same tag (`render.image_style`):
    the paper is the box, so the sheet's width and side are shown inside a
    frame of the preview's own width.
    """
    container.html(f'<div style="max-width:{width}px">'
                   f'<img src="{data_uri(path)}" '
                   f'style="width:100%;display:block;{style}"></div>')


def _asset_path(value: str) -> Path | None:
    """Resolve a branding path the way the renderer does: absolute, or under
    `track/` for the paths written as `header/head_CITA24.svg`."""
    if not value:
        return None
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p if p.exists() else None


# ── 4. what an event is, once for every championship ────────────────────

#: The formats an event can be run under - what `race.round_format` knows.
FORMATS = ("group", "elimination", "timed", "timed_team", "sprint", "keirin",
           "omnium", "madison", "time_trial", "entrylist")


def _events() -> None:
    """The event this installation knows, and what each one *is*.

    Sigla UCI, formato, atleti per squadra, quante partono insieme, quanto dura
    una sua fase, e come si chiama la colonna nel file iscritti: facts that are
    the same at every championship. They used to be typed into the Programma page of every new
    meeting - seven fields per event, per year, and getting one wrong is a
    programme that runs the wrong machinery.

    So they live in `regulations/events.json` and are edited here. A programme
    reads them (`config._events_of`) and writes down only what it does
    *differently*, so correcting the sigla of the madison here corrects it in
    every file that never disagreed with it. The **name** is not here: it is
    printed on every sheet and belongs to the meeting that wrote it.
    """
    st.subheader(ui("events"))
    st.caption(msg("events_settings_caption"))
    with st.expander(ui("events_settings_edit"), expanded=False):
        table = CAT.load()
        rows = [{"code": code,
                 "short": CAT.name(code, short=True),
                 "abbr": str(entry.get("abbr") or ""),
                 "fmt": str(entry.get("fmt") or "group"),
                 "team_size": int(entry.get("team_size") or 0),
                 "teams_per_start": int(entry.get("teams_per_start") or 2),
                 "minutes": int(entry.get("minutes") or 0),
                 "entry_columns": ", ".join(entry.get("entry_columns") or [])}
                for code, entry in table.items()]
        edited = st.data_editor(
            pd.DataFrame(rows), key="set_events_grid", hide_index=True,
            use_container_width=True, num_rows="fixed",
            column_order=["code", "short", "abbr", "fmt", "team_size",
                          "teams_per_start", "minutes", "entry_columns"],
            column_config={
                "code": st.column_config.TextColumn(ui("code"), disabled=True,
                                                    width="small"),
                "short": st.column_config.TextColumn(ui("short_name"),
                                                     disabled=True),
                "abbr": st.column_config.TextColumn(ui("abbr"), width="small",
                                                    help=help_text("abbr")),
                "fmt": st.column_config.SelectboxColumn(
                    ui("format"), options=list(FORMATS),
                    help=help_text("event_format")),
                "team_size": st.column_config.NumberColumn(
                    ui("team_size"), min_value=0, max_value=12, step=1,
                    width="small", help=help_text("team_size")),
                "teams_per_start": st.column_config.NumberColumn(
                    ui("per_start"), min_value=1, max_value=2, step=1,
                    width="small", help=help_text("starts_per_race")),
                "minutes": st.column_config.NumberColumn(
                    ui("event_minutes"), min_value=0, max_value=240, step=5,
                    width="small", help=help_text("event_minutes")),
                "entry_columns": st.column_config.TextColumn(
                    ui("entry_columns"), help=help_text("entry_columns")),
            })
        if st.button(ui("save_events"), key="set_events_save"):
            _save_events(table, edited)
            notify.ok("events_saved", path=str(CAT.FILE))
            state.refresh()


def _save_events(table: dict, edited) -> None:
    """Write the grid back into the catalogue, and only what it is about.

    The name of an event is per language and is not in the grid, so it is
    carried over untouched: reading a table in Italian and writing it back must
    not be what drops the English one.
    """
    for _i, row in edited.iterrows():
        entry = table.get(str(row["code"]))
        if entry is None:
            continue
        entry["abbr"] = str(row["abbr"] or "").strip()
        entry["fmt"] = str(row["fmt"] or "group").strip()
        size = int(row["team_size"] or 0)
        entry["team_size"] = size
        entry["teams_per_start"] = int(row["teams_per_start"] or 2)
        entry["minutes"] = int(row["minutes"] or 0)
        columns = [c.strip() for c in str(row["entry_columns"] or "").split(",")
                   if c.strip()]
        entry["entry_columns"] = columns
        # what says nothing is not written down: an empty value in this table
        # would be a statement that an event has no sigla
        for name in ("abbr", "team_size", "minutes", "entry_columns"):
            if not entry.get(name):
                entry.pop(name, None)
        if entry.get("teams_per_start") == 2:
            entry.pop("teams_per_start", None)
    CAT.save(table)


# ── 5. what an event announces on its sheets ────────────────────────────

def _sheet_lines(store: Store) -> None:
    """The lines a comunicato opens on, worded once for the installation.

    *Non si qualificano per la finale le ultime 2 coppie tra le partenti*, *La
    prima squadra parte sul rettilineo d'arrivo*: sentences that come out of
    the regulation and are the same at every championship, which is why they
    are here and not in a programme. Which line goes on which sheet is the
    table `core.notes` reads; what is edited here is **how it is worded**, in
    the language of the competition, and the app's own wording is what a field
    left empty falls back to.

    They are written into the programme when a race is added, with the numbers
    of that race in them - so what the jury reads in Programmazione is what
    will print - and re-proposed when one of those numbers moves.
    """
    st.caption(msg("sheet_lines_caption"))
    lang = language()
    st.caption(ui("sheet_lines_language", language=language_name(lang)))
    mine = NOTES.texts()
    edited = dict(mine.get(lang) or {})
    for key in NOTES.keys():
        shipped = NOTES.shipped(key, lang)
        value = st.text_area(
            _line_title(key), edited.get(key, shipped),
            key=f"set_note_{lang}_{key}", height=68,
            help=msg("sheet_line_default", text=shipped))
        edited[key] = value
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if c1.button(ui("save_sheet_lines"), key="set_notes_save"):
        NOTES.save_texts({**mine, lang: edited})
        notify.ok("sheet_lines_saved", path=str(NOTES.FILE))
        state.refresh()
    if c2.button(ui("restore_sheet_lines"), key="set_notes_reset",
                 help=help_text("restore_sheet_lines")):
        NOTES.save_texts({**mine, lang: {}})
        _forget_note_widgets(lang)
        notify.ok("sheet_lines_restored")
        state.refresh()


def _line_title(key: str) -> str:
    """What a wording is called in the list: the key, said in words.

    The genere is part of it - *maschile* and *femminile* are two lines and two
    fields - and the rest is the key as the table names it, which is what the
    rules in `regulations/notes.json` refer to.
    """
    for suffix, word in (("_m", ui("masculine")), ("_f", ui("feminine"))):
        if key.endswith(suffix):
            return f"{key[:-len(suffix)]} · {word}"
    return key


def _forget_note_widgets(lang: str) -> None:
    """Drop the fields, so restoring the defaults shows them.

    A `st.text_area` owns its value once it exists: without this the boxes go
    on showing what was typed into them after the file underneath has been put
    back to what the app ships.
    """
    for key in list(st.session_state):
        if key.startswith(f"set_note_{lang}_"):
            del st.session_state[key]


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
