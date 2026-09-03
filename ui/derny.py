"""DERNY - the lap chart, called live.

Three readings of one list of passages (`core.formats.derny`), because three
different people are asking three different questions while the race is on:

* **Passaggi** - the chart the jury reads. One column per lap, the numbers in
  the order they were called; the number of whoever lost a lap printed back in
  red where it should have been, and next to it the standings, full laps first,
  with an asterisk for each lap lost. This is what gets read to the speaker.
* **Cronologico** - the call itself, with the moment each number was typed.
  It is the only thing stored, so it is also the only place to correct it: a
  number typed by mistake is deleted here and every other reading is drawn
  again without it.
* **Statistiche** - one small chart per rider: the lap times as a line, their
  distribution beside it, and the mean and σ over them once there are three.
  A lap that falls outside the band the jury sets is marked here and turns
  yellow on the chart, which is how a number nobody called gets noticed.

Nothing on this page computes a result: `core.formats.derny` does, and the
classifica underneath is the ordinary one every other race prints.
"""

from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import streamlit as st

from core import race as R
from core.formats import derny as DY
from core.i18n import help_text, label, msg, ordinal, ui
from ui import notify

#: The three readings, in the order they are offered.
BOARD, LOG, STATS = "board", "log", "stats"
VIEWS = (BOARD, LOG, STATS)

#: How wide one rider's chart is drawn, in user units of its own viewBox.
_W_LINE, _W_HIST, _H = 260, 56, 60
_PAD = 7
_BINS = 9


def _draw(box, html: str) -> None:
    """Put an SVG on the page - which `st.html` cannot do.

    `st.html` sanitises what it is given with DOMPurify under `USE_PROFILES:
    {html: true}`: that profile allows the HTML namespace and **drops the SVG
    one entirely**, so every chart on this page came out as an empty block.
    `st.markdown(unsafe_allow_html=True)` goes through rehype-raw instead and
    keeps it. The tables are still drawn with `st.html`, which is the narrower
    door and enough for them.
    """
    box.markdown(html, unsafe_allow_html=True)


# ── the call ────────────────────────────────────────────────────────────────

def _key(state, name: str) -> str:
    return f"dy_{name}_{state.race_id}"


def _save(state, store, action: str) -> None:
    """Write the race as it stands, without a snapshot and without a log line.

    The judge calls a number every couple of seconds and each one lands on
    disk: a copy aside and a journal entry per passage would be hundreds of
    each in one race (`core.store.save_race`). The jury's own *Salva* still
    takes a snapshot, as everywhere else.
    """
    store.save_race(state, action=action, snapshot=False, journal=False)


def call_bar(state, el, store) -> None:
    """The one control the race is run from: a button per partente.

    There used to be a field to type the number into as well. Two ways of doing
    the same thing, and the slower one was the one that could go wrong: a
    button is one press, it cannot be misheard into a dorsale nobody is riding,
    and the judge's hands stay where they are. The buttons *are* the lista
    partenti - what is not on it cannot be called - and a passage that has to
    be put in by hand goes in from Cronologico, which is where corrections are
    made anyway (`_insert_row`).

    **Nothing here calls `st.rerun`.** Pressing a button already runs the whole
    script again, and asking for a second run doubled the wait between one
    passage and the next - on a page that is pressed every few seconds. So the
    press is *handled first* and the row above it is drawn afterwards, into a
    container kept for it: everything on the page, this row included, is drawn
    once, from the log as it stands after the press.
    """
    started = [int(x) for x in state.entrants]
    if not started:
        # nothing can be called: the event has nobody entered in it
        notify.info("derny_no_starters")
    top = st.container()          # the row of controls, drawn last
    _keypad(state, store, started)

    log = DY.passages(state.payload)
    cols = top.columns([4, 1, 1], vertical_alignment="bottom")
    cols[0].caption(ui("derny_call"), help=help_text("derny_call"))
    start = state.payload.get(DY.START)
    if start:
        if cols[1].button(ui("derny_start_clear"),
                          key=_key(state, "nostart"), use_container_width=True):
            state.payload.pop(DY.START, None)
            _save(state, store, "derny_start")
            st.rerun()
        cols[1].caption(ui("derny_start_at", at=_clock(start)))
    elif cols[1].button(ui("derny_start"), key=_key(state, "start"),
                        use_container_width=True,
                        help=help_text("derny_start")):
        state.payload[DY.START] = time.time()
        _save(state, store, "derny_start")
        st.rerun()

    cols[2].metric(ui("derny_laps_ridden"),
                   DY.board(log, start, state.n_laps).leader_laps,
                   label_visibility="collapsed")


#: How many dorsali go on one row of the keypad. Ten is what a hand finds
#: without reading: past that the numbers are too narrow to hit at speed, and
#: a field of twenty is two rows that are still one glance.
_PER_ROW = 10


def _keypad(state, store, started: list[int]) -> None:
    """One button per partente, ten to a row, and the actions under them.

    The last row is what the race asks for that is not a dorsale: the whole
    lap before again (`_again`), for the giro the bunch comes through together;
    `?`, the passage the judge saw without reading the number
    (`formats.derny.UNKNOWN`); and *Annulla ultimo numero*, which drops the
    passage just written - the one correction that has to be within reach while
    the race is on, everything else being done in Cronologico.

    The passage is written and the page carries on being drawn: this is the one
    control that is used all race long, and it is drawn before everything that
    reads the log so that one run of the script is enough (see `call_bar`).
    """
    if not started:
        return
    for i in range(0, len(started), _PER_ROW):
        row = st.columns(_PER_ROW)
        for box, bib in zip(row, started[i:i + _PER_ROW]):
            if box.button(str(bib), key=_key(state, f"k{bib}"),
                          use_container_width=True, type="primary"):
                DY.add(state.payload, bib)
                _save(state, store, "derny_call")

    log = DY.passages(state.payload)
    group = _last_group(log, len(log))
    actions = st.columns([2, 1, 1] + [1] * (_PER_ROW - 4))
    if actions[0].button(ui("derny_prev_lap"), key=_key(state, "again"),
                         use_container_width=True, disabled=not group,
                         help=help_text("derny_prev_lap")):
        at = time.time()
        for one in group:
            DY.add(state.payload, one, at=at)
        _save(state, store, "derny_call")
        notify.saved("derny_prev_lap_done", n=len(group))
    if actions[1].button(DY.UNKNOWN, key=_key(state, f"k{DY.UNKNOWN}"),
                         use_container_width=True,
                         help=help_text("derny_unknown_call")):
        DY.add(state.payload, DY.UNKNOWN)
        _save(state, store, "derny_call")
    if actions[2].button(ui("derny_undo"), key=_key(state, "undo"),
                         use_container_width=True,
                         disabled=not DY.passages(state.payload)):
        log = DY.passages(state.payload)
        DY.remove(state.payload, len(log) - 1)
        _save(state, store, "derny_undo")


def laps_down_tick(state, store, container=None) -> bool:
    """The one column the classifica of a derny is asked for, or not.

    Off by default: most derny are ridden with nobody a lap down, and a column
    of zeros on the sheet is a question the jury then has to answer. It is kept
    on the race and not in the session, so the comunicato printed from Stampa
    is the one that was prepared in Gare (`formats.derny.SHOW_DOWN`).
    """
    now = bool(state.payload.get(DY.SHOW_DOWN))
    on = (container or st).checkbox(ui("laps_down_column"), value=now,
                                    key=_key(state, "down"),
                                    help=help_text("laps_down_column"))
    if on != now:
        state.payload[DY.SHOW_DOWN] = on
        _save(state, store, "derny_laps_down")
    return on


# ── the page ────────────────────────────────────────────────────────────────

def render(state, el, comp, store) -> None:
    """The three readings, under the control the race is called into."""
    call_bar(state, el, store)
    log = DY.passages(state.payload)
    b = DY.board(log, state.payload.get(DY.START), state.n_laps)
    sigma = DY.sigma_of(state.payload)
    names = _names(state, el)

    view = st.pills(ui("derny_view"), VIEWS, key=_key(state, "view"),
                    default=BOARD, label_visibility="collapsed",
                    format_func=lambda v: ui(f"derny_{v}"))
    if view == LOG:
        _log_view(state, store, log, names, _teams(state, el))
    elif view == STATS:
        _stats_view(state, store, b, names, sigma)
    else:
        _board_view(b, names, sigma, state.n_laps)


def _names(state, el) -> dict[int, str]:
    """bib -> COGNOME Nome, as the speaker reads it out.

    Empty where the number is not entered. One string and not two columns: the
    recap is read aloud, and a name is read whole.
    """
    out = {}
    for key in state.entrants:
        riders = R.entrant_riders(str(key), el, state.cat)
        try:
            out[int(key)] = riders[0].full_name if riders else ""
        except (TypeError, ValueError):
            continue
    return out


def _teams(state, el) -> dict[int, str]:
    """bib -> the rappresentativa the rider is filed under, as the sheets do.

    The region, which is what an individual sheet of this app prints as
    *squadra* (`documents._entrant_rows`); the società only where a rider has
    no region on the entry list.
    """
    out = {}
    for key in state.entrants:
        riders = R.entrant_riders(str(key), el, state.cat)
        try:
            out[int(key)] = (riders[0].region or riders[0].club) if riders else ""
        except (TypeError, ValueError):
            continue
    return out


# ── Passaggi: the chart and the standings ───────────────────────────────────

def _board_view(b, names: dict[int, str], sigma: float,
                planned: float | None = None) -> None:
    """The chart, the standings, and how much of the race is left over them.

    *Giri rimanenti* is the one number everybody in the cabin asks for while
    the race is on, and it is arithmetic the jury should not be doing in its
    head: the giri of the fase (Programma → fase) less the giri of the head.
    At zero the winner has crossed the line and the chart says so - what comes
    in after that is the arrival, not another lap (`formats.derny.board`).
    """
    if not b.columns:
        notify.info("derny_no_passages")
        return
    if planned:
        st.caption(ui("derny_over") if b.over
                   else ui("derny_laps_left",
                           n=max(int(planned) - b.leader_laps, 0)))
    left, right = st.columns([3, 2])
    with left:
        st.html(_chart_html(b, sigma))
    with right:
        st.html(_standings_html(b, names))


def _chart_html(b, sigma: float) -> str:
    """One column per lap, the numbers down it in the order they were called.

    A rider who lost a lap is printed twice. In the column he did not ride his
    number is there in a very light grey, at the foot of it, where he would
    have come through: the column reads complete, which is how the eye checks
    that everybody is accounted for, and the grey says he was not actually
    there. In the column where he did reappear the same number is in red and
    bold - that is the lap that went, and it is the head that made it go.

    A lap whose time is off the rider's own mean turns yellow
    (`formats.derny.flagged`).
    """
    hot = DY.flagged(b, sigma)
    rows = max(len(col) + len(gone) for col, gone in zip(b.columns, b.lost))
    head = "".join(f"<th>{ui('derny_lap_n', n=i + 1)}</th>"
                   for i in range(len(b.columns)))
    body = []
    for r in range(rows):
        cells = []
        for i, col in enumerate(b.columns):
            if r < len(col):
                bib = col[r]
                cls = " ".join(x for x in (
                    "dy-unknown" if bib == DY.UNKNOWN else "",
                    "dy-late" if (bib, i) in b.late else "",
                    "dy-hot" if (bib, i) in hot else "") if x)
                cells.append(f'<td class="{cls}">{bib}</td>')
            elif r - len(col) < len(b.lost[i]):
                cells.append(f'<td class="dy-lost">{b.lost[i][r - len(col)]}</td>')
            else:
                cells.append("<td></td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return ('<div class="dy-scroll"><table class="dy-chart"><thead><tr>'
            f"{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>")


def _standings_html(b, names: dict[int, str]) -> str:
    """What the speaker reads: the place, the number, the name. Nothing else.

    Full laps first, then one down, then two - an asterisk against the number
    for each lap lost, which is the one thing the speaker has to know that the
    order alone does not say. The giri ridden are not a column: they are the
    race, not the rider, and the chart on the left is where they are counted.
    """
    rows = []
    for i, bib in enumerate(b.order, start=1):
        stars = "*" * b.down.get(bib, 0)
        rows.append(
            f"<tr><td class='dy-pos'>{ordinal(i)}</td>"
            f"<td class='dy-bib'>{bib}<span class='dy-star'>{stars}</span></td>"
            f"<td class='dy-name'>{names.get(bib, '')}</td></tr>")
    return (f"<div class='dy-recap'><h4>{ui('derny_standings')}</h4>"
            f"<table class='dy-standings'><tbody>{''.join(rows)}</tbody>"
            "</table></div>")


# ── Cronologico: the call itself, and the only place to correct it ──────────

def _clock(at: float) -> str:
    return datetime.fromtimestamp(at).strftime("%H:%M:%S.") \
        + f"{int(at % 1 * 10)}"


def _parse_clock(text: str, ref: float) -> float | None:
    """`10:41:07.3` back to an epoch, on the day of `ref`.

    The jury corrects an hour, not a date: what is typed is a time of day and
    it lands on the day the race is being ridden. A bare number of seconds is
    taken as it is - that is what a log written by a machine looks like.
    """
    text = str(text or "").strip().replace(",", ".")
    if not text:
        return None
    day = datetime.fromtimestamp(ref).replace(hour=0, minute=0, second=0,
                                              microsecond=0)
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%M:%S.%f", "%M:%S"):
        try:
            t = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return (day.replace(hour=t.hour, minute=t.minute, second=t.second,
                            microsecond=t.microsecond)).timestamp()
    try:
        return float(text)
    except ValueError:
        return None


def _log_view(state, store, log: list[dict], names: dict[int, str],
              teams: dict[int, str]) -> None:
    """The call as a table the jury edits: the only place it is corrected.

    Everything else on the page is derived, so this is where a race is put
    right: a dorsale read wrong, an hour typed a lap late, a passage that never
    happened, one that happened and nobody typed. The table is in the order it
    was called - **first passage first**, the way the race was ridden - and the
    giro each line falls in is printed beside it, so a correction can be aimed
    at the column of the chart it will move, and the progressivo in front is
    what a passage is inserted after.
    """
    _start_field(state, store)
    if not log:
        notify.info("derny_no_passages")
        return
    st.caption(help_text("derny_log"))
    _insert_row(state, store, log, names)

    # the progressivo first: it is the number the insert control is aimed with
    # ("dopo la riga n."), and a table nobody can point at is a table nobody
    # can correct. It is the position in the call, not a giro and not a placing
    cols = (ui("derny_row_no"), ui("derny_lap"), label("bib"),
            ui("derny_clock"), label("last_name"), label("team_en"))
    frame = pd.DataFrame([
        {cols[0]: i, cols[1]: lap, cols[2]: str(row["bib"]),
         cols[3]: _clock(row["at"]), cols[4]: names.get(row["bib"], ""),
         cols[5]: teams.get(row["bib"], "")}
        for i, (row, lap) in enumerate(zip(log, _laps_of(log)), start=1)])
    edited = st.data_editor(
        frame, key=_key(state, f"ed{_stamp(log)}"), num_rows="dynamic",
        use_container_width=True, hide_index=True,
        column_config={
            cols[0]: st.column_config.NumberColumn(disabled=True,
                                                   width="small"),
            cols[1]: st.column_config.TextColumn(disabled=True, width="small"),
            cols[2]: st.column_config.TextColumn(
                required=True, width="small", help=help_text("derny_bib_cell")),
            cols[3]: st.column_config.TextColumn(width="small"),
            cols[4]: st.column_config.TextColumn(disabled=True),
            cols[5]: st.column_config.TextColumn(disabled=True)})

    new = _log_from(edited, cols, log, state.payload.get(DY.START))
    if new != log:
        DY.replace(state.payload, new)
        _save(state, store, "derny_log_edit")
        notify.saved("derny_log_saved")
        st.rerun()


def _stamp(log: list[dict]) -> str:
    """A short mark of the call as it stands, for the editor's key.

    The key changes as soon as the log does, so the table is a new widget after
    every correction: `st.data_editor` keeps its edits against the frame it was
    given, and a table redrawn under the old key would apply them a second time
    to the corrected log.
    """
    return f"{len(log)}_{abs(hash(tuple((str(r['bib']), r['at']) for r in log)))}"


def _laps_of(log: list[dict]) -> list[int]:
    """Which giro of the chart each line of the call falls in (1-based)."""
    out, columns = [], DY.board(log).columns
    seen = 0
    for i, col in enumerate(columns, start=1):
        out += [i] * len(col)
        seen += len(col)
    return out + [len(columns)] * (len(log) - seen)


def _log_from(edited, cols, log: list[dict], start) -> list[dict]:
    """The table as a call again: what the jury typed, back in log order.

    A line the jury added carries no hour of its own: it takes the one of the
    line above it, which is where it was put - the order of the call is what
    the chart is read from, and the hour is what the lap times are measured on.
    """
    out, last = [], float(start or (log[0]["at"] if log else 0))
    for _, row in edited.iterrows():
        bib = DY.as_bib(row[cols[2]])
        if bib is None:
            continue
        at = _parse_clock(row[cols[3]], last or 0)
        out.append({"bib": bib, "at": last if at is None else at})
        last = out[-1]["at"]
    return out


def _start_field(state, store) -> None:
    """The gun, as an hour that can be typed: the first lap is measured on it."""
    start = state.payload.get(DY.START)
    box, _ = st.columns([1, 2])
    typed = box.text_input(ui("derny_start_time"),
                           value=_clock(start) if start else "",
                           key=_key(state, "startat"),
                           placeholder="10:40:00.0",
                           help=help_text("derny_start"))
    at = _parse_clock(typed, start or time.time())
    if at is None and typed.strip():
        notify.warn("derny_bad_clock", at=typed)
        return
    if at is None and start:
        state.payload.pop(DY.START, None)
    elif at is not None and at != start:
        state.payload[DY.START] = at
    else:
        return
    _save(state, store, "derny_start")
    st.rerun()


def _insert_row(state, store, log: list[dict], names: dict[int, str]) -> None:
    """Put a passage back where it happened: a dorsale, a place, an hour.

    The judge calls a number half a lap late - it belongs between two lines
    already written, not at the foot of the table. *Dopo la riga n.* is the
    progressivo it goes after, and the hour opens on **the hour of that line**,
    which is where the passage happened as far as anything on this page knows;
    the jury edits it when it knows better. `?` goes in here as well, for the
    passage nobody could name. The lap that came through as a bunch is not put
    in here: it is called, with *Passaggio giro precedente* under the dorsali
    (`_keypad`).
    """
    with st.expander(ui("derny_insert")):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")

        bib = c1.text_input(label("bib"), key=_key(state, "insbib"),
                            placeholder=f"7 {DY.UNKNOWN}",
                            help=help_text("derny_insert"))
        pos = int(c2.number_input(ui("derny_after_row"), min_value=0,
                                  max_value=len(log), value=len(log), step=1,
                                  key=_key(state, "inspos")))
        # the hour of the line it goes after - of the gun, at the head of the
        # table. The key carries the position, so moving the row the passage
        # follows opens the field on *that* line's hour instead of keeping the
        # one typed against the row before
        ref = (log[pos - 1]["at"] if pos
               else state.payload.get(DY.START)
               or (log[0]["at"] if log else time.time()))
        typed = c3.text_input(ui("derny_clock"), value=_clock(ref),
                              key=_key(state, f"instime{pos}"),
                              help=help_text("derny_insert_at"))
        go = c4.button(ui("derny_insert_do"), key=_key(state, "insgo"),
                       use_container_width=True, type="primary")
        if not go:
            return
        at = _parse_clock(typed, ref)
        if at is None:
            notify.warn("derny_bad_clock", at=typed)
            return
        value = DY.as_bib(bib)
        if value is None:
            notify.warn("derny_bad_bib", bib=bib)
            return
        if value != DY.UNKNOWN and value not in [int(x) for x in state.entrants]:
            notify.warn("derny_unknown_bib", bib=value)
            return
        DY.add(state.payload, value, at=at, index=pos)
        _save(state, store, "derny_insert")
        notify.saved("derny_passage_added")
        st.rerun()


def _last_group(log: list[dict], pos: int) -> list[int | str]:
    """The numbers of the lap before `pos`, in the order they were called.

    What *Passaggio giro precedente* writes again (`_keypad`). The column now
    open where it is complete - the whole field came through and nobody has
    been called into the next lap yet - and the one before it where it is not,
    which is the lap that has all of them in it.
    """
    columns = DY.board(log[:pos]).columns
    if not columns:
        return []
    if len(columns) > 1 and len(columns[-1]) < len(columns[-2]):
        return list(columns[-2])
    return list(columns[-1])


# ── Statistiche: the lap times, and what stands out among them ─────────────

def _stats_view(state, store, b, names: dict[int, str], sigma: float) -> None:
    choice = st.select_slider(ui("derny_sigma"), options=list(DY.SIGMAS),
                              value=sigma if sigma in DY.SIGMAS
                              else DY.DEFAULT_SIGMA,
                              key=_key(state, "sigma"),
                              help=help_text("derny_sigma"))
    if choice != sigma:
        state.payload[DY.SIGMA] = float(choice)
        _save(state, store, "derny_sigma")
        st.rerun()
    if not b.times:
        notify.info("derny_no_passages")
        return

    flags = sum(len(DY.spread(t, choice).outliers) for t in b.times.values())
    st.caption(ui("derny_flagged", n=flags))

    # two to a row: the chart is small on purpose, so a field of twenty is one
    # screen and not twenty scrolls. Under each of them the passages it is made
    # of, closed - the chart answers "is this rider steady", the list answers
    # "which giro, and at what time", and that one is asked of one rider at a
    # time (`_splits`)
    riders = list(b.order)
    for i in range(0, len(riders), 2):
        for box, bib in zip(st.columns(2), riders[i:i + 2]):
            _draw(box, _card(bib, b.times.get(bib, []), names.get(bib, ""),
                             choice))
            box.expander(ui("derny_splits")).html(_splits_html(b, bib, choice))


def _splits_html(b, bib: int, sigma: float) -> str:
    """Every passage of one rider: the giro, the hour, the time on the lap.

    The parziali as the jury reads them back - one line per passage, in the
    order they were called. A giro whose time is off the rider's own mean is
    marked here as it is on the chart, so the line to go and check is the one
    that stands out in both places.
    """
    times = b.times.get(bib) or []
    closes = {c: i for i, c in enumerate(b.lap_col.get(bib) or [])}
    odd = set(DY.spread(times, sigma).outliers)
    rows = []
    for col, at in b.marks.get(bib) or []:
        i = closes.get(col)
        lap = _secs(times[i]) if i is not None and i < len(times) else ""
        cls = " class='dy-hot'" if i in odd else ""
        rows.append(f"<tr><td class='dy-pos'>{col + 1}</td>"
                    f"<td class='dy-name'>{_clock(at)}</td>"
                    f"<td{cls}>{lap}</td></tr>")
    head = (f"<tr><th>{ui('derny_lap')}</th><th>{ui('derny_clock')}</th>"
            f"<th>{ui('derny_lap_time')}</th></tr>")
    return (f"<table class='dy-standings dy-splits'><thead>{head}</thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _card(bib: int, times: list[float], name: str, sigma: float) -> str:
    """One rider: the name, the mean and σ, and the lap times drawn under them.

    A rider with a giro outside the band gets the **whole chart on yellow** -
    the same yellow as the cell on the Passaggi chart. From across the desk
    that is the one thing to see: which riders have something to look at, out
    of twenty small charts that otherwise read alike.
    """
    sp = DY.spread(times, sigma)
    if sp.known:
        note = (f"{ui('derny_mean')} {_secs(sp.mean)} · "
                f"{ui('derny_sd')} {_secs(sp.sd)}")
    else:
        note = msg("derny_needs_times", n=DY.MIN_TIMES)
    hot = " dy-card-hot" if sp.outliers else ""
    return (f"<div class='dy-card{hot}'><div class='dy-card-head'>"
            f"<b>{bib}</b> {name}<span class='dy-dim'>{note}</span></div>"
            f"{_svg(times, sp, sigma)}</div>")


def _secs(v: float | None) -> str:
    return "" if v is None else f"{v:.2f}″"


def _svg(times: list[float], sp, sigma: float) -> str:
    """The lap times as a line, their distribution beside it.

    Plain SVG and no chart library: this is drawn once per rider on every
    rerun - twenty of them while somebody is typing numbers - and a vega spec
    per rider is a page that stops answering. Everything is one colour, the
    page's own (`currentColor`), except what is flagged.
    """
    if not times:
        return f"<svg viewBox='0 0 {_W_LINE + _W_HIST} {_H}'></svg>"
    lo, hi = min(times), max(times)
    if hi - lo < 1e-9:
        lo, hi = lo - 0.5, hi + 0.5
    span = hi - lo

    def y(v: float) -> float:
        return _PAD + (hi - v) / span * (_H - 2 * _PAD)

    def x(i: int) -> float:
        n = max(len(times) - 1, 1)
        return _PAD + i / n * (_W_LINE - 2 * _PAD)

    out = []
    if sp.known and sp.sd:
        top, bot = y(sp.mean + sigma * sp.sd), y(sp.mean - sigma * sp.sd)
        out.append(f"<rect x='0' y='{max(top, 0):.1f}' width='{_W_LINE}' "
                   f"height='{max(min(bot, _H) - max(top, 0), 0):.1f}' "
                   "fill='currentColor' opacity='.07'/>")
    if sp.known:
        out.append(f"<line x1='0' x2='{_W_LINE}' y1='{y(sp.mean):.1f}' "
                   f"y2='{y(sp.mean):.1f}' stroke='currentColor' "
                   "stroke-dasharray='3 3' opacity='.35'/>")
    pts = " ".join(f"{x(i):.1f},{y(t):.1f}" for i, t in enumerate(times))
    out.append(f"<polyline points='{pts}' fill='none' stroke='currentColor' "
               "stroke-width='1.3' opacity='.85'/>")
    for i in sp.outliers:
        out.append(f"<circle cx='{x(i):.1f}' cy='{y(times[i]):.1f}' r='2.8' "
                   "fill='#e0a800'/>")
    out.append(_hist(times, lo, hi, y))
    return (f"<svg class='dy-svg' viewBox='0 0 {_W_LINE + _W_HIST} {_H}' "
            f"preserveAspectRatio='none'>{''.join(out)}</svg>")


def _hist(times: list[float], lo: float, hi: float, y) -> str:
    """The same axis, lying on its side: how often each lap time came up."""
    span = hi - lo
    counts = [0] * _BINS
    for t in times:
        counts[min(int((t - lo) / span * _BINS), _BINS - 1)] += 1
    top = max(counts) or 1
    h = (_H - 2 * _PAD) / _BINS
    bars = []
    for i, c in enumerate(counts):
        if not c:
            continue
        # bin i runs from lo + i*step upward, and the axis is drawn downward
        y0 = y(lo + (i + 1) * span / _BINS)
        bars.append(f"<rect x='{_W_LINE + 3}' y='{y0:.1f}' "
                    f"width='{c / top * (_W_HIST - 6):.1f}' "
                    f"height='{max(h - 1, 1):.1f}' fill='currentColor' "
                    "opacity='.45'/>")
    return "".join(bars)
