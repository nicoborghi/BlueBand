"""CHECK-IN ("Verifica") - licence check and entry-list editing.

The licence check runs before the racing starts, so the tick marks who *is*
there (`Ver.`), not who is missing: what is left unticked is the work still to
do. A rider who will not start at all is flagged separately (`NP`).

The page reads, in this order: the four counters (atleti, verificati, squadre,
coppie), the tabella specialità, the findings, then the grid the jury edits.

Importing is *not* here - it is a setting (Impostazioni → Elenco iscritti).
The entry file is never written to: edits are appended to the overlay as
explicit patches keyed by UCI ID, so re-importing a newer export keeps every
jury decision and reports the ones that no longer apply.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import entries as E
from core import recap as RC
from core.config import Competition, EVENT_ENTRY_LIST
from core.checks import ERROR
from core.i18n import help_text, label, msg, ui
from core.store import Store
from ui import notify

# Grid columns, in order: the code names, shown with their Italian labels.
GRID = ["checked_in", "not_starting", "bib", "last_name", "first_name",
        "uci_id", "cat", "region", "club", "club_code"]
EDITABLE = ["bib", "last_name", "first_name", "region", "club", "club_code"]
STATES = [ui("state_all"), ui("state_todo"), ui("state_done"), ui("state_np")]
ALL, TODO, DONE, NP = STATES


def render(competition: str, comp: Competition, store: Store) -> None:
    el, stale = E.effective_entries(store, comp)
    if el is None:
        notify.info("import_entries_in_settings")
        return
    if stale:
        notify.warn("stale_patches",
                    list="\n".join(f"- {s}" for s in stale))

    # how far the check has got, then what the field is made of, then what is
    # wrong with it: the numbers the jury is asked for, in that order
    _counters(el, comp)
    _speciality_table(el, comp)
    _issues(el, comp)
    _editor(el, comp, store)
    _history(store)


# ── panels ──────────────────────────────────────────────────────────────────

def _counters(el, comp: Competition) -> None:
    """The four numbers the jury is asked for, and the bar under them."""
    total = E.check_in_progress(el)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(ui("athletes"), total.entries)
    c2.metric(ui("verified"), total.verificati,
              delta=(ui("check_in_left", n=total.missing) if total.missing
                     else ui("check_in_complete")), delta_color="off")
    c3.metric(ui("teams"), sum(1 for t in el.teams.values() if t.riders))
    c4.metric(ui("pairs"), len(el.pairs))
    if total.entries:
        st.progress(total.verificati / total.entries,
                    text=ui("check_in_progress", done=total.verificati,
                            total=total.entries)
                    + (f" · {total.not_starting} NP" if total.not_starting else ""))


def _speciality_table(el, comp: Competition) -> None:
    """The tabella specialità: each categoria across the programme.

    The same table Documenti prints (`render.documents.speciality_table`), from
    the same `core.recap` rows - the screen and the sheet can only agree.
    """
    st.subheader(ui("speciality_table"))
    rows, total = RC.speciality_table(el, comp)
    heads = comp.event_headers([s for s in comp.event_order()
                                if s != EVENT_ENTRY_LIST])
    # kept as strings: a mix of ints and blanks has no Arrow type, and a
    # category that does not contest an event prints blank, not 0
    table = [{label("cat"): r.cat, ui("athletes"): str(r.entries),
              label("checked_in"): f"{r.checked_in}/{r.entries}",
              ui("todo"): str(r.missing),
              label("not_starting"): str(r.not_starting),
              **{heads[s]: ("" if n is RC.NOT_CONTESTED else str(n))
                 for s, n in r.per_event.items()}}
             for r in [*rows, total]]
    table[-1][label("cat")] = ui("total")
    st.dataframe(pd.DataFrame(table), hide_index=True,
                 use_container_width=True)


def _issues(el, comp: Competition) -> None:
    issues = E.validate_entries(el, comp)
    errs = [i for i in issues if i.level == ERROR]
    title = ui("checks_summary", errors=len(errs),
               warnings=len(issues) - len(errs))
    with st.expander(title, expanded=bool(errs)):
        if not issues:
            notify.ok("no_findings")
        notify.issues(issues)
        if comp.quotas.exemptions:
            st.caption(ui("stp_exemptions",
                          list=" · ".join(comp.quotas.exemptions)))


def _editor(el, comp: Competition, store: Store) -> None:
    st.subheader(ui("entry_list_title"))
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    cats = c1.multiselect(ui("categories"), comp.cat_order(),
                          default=comp.cat_order(), key="ver_cats")
    any_f = ui("all_f")
    events = [any_f] + [comp.event(s).short
                        for s in comp.event_order() if s != EVENT_ENTRY_LIST]
    pick = c2.selectbox(ui("event"), events, key="ver_event")
    code = next((s for s in comp.event_order()
                 if comp.event(s).short == pick), "")
    # the third filter is whatever this competition calls a squadra: at a
    # championship the regione, at an open meeting the società
    group = comp.team_group
    teams = [any_f] + RC.teams(el, group)
    team = c3.selectbox(label(group), teams, key="ver_region")
    state = c4.selectbox(ui("state"), STATES, key="ver_state")

    riders = [r for r in el.riders.values() if r.cat in cats]
    if code:
        riders = [r for r in riders if code in r.events]
    if team != any_f:
        riders = [r for r in riders if RC.group_of(r, group) == team]
    if state == TODO:
        riders = [r for r in riders if not r.checked_in and not r.not_starting]
    elif state == DONE:
        riders = [r for r in riders if r.checked_in]
    elif state == NP:
        riders = [r for r in riders if r.not_starting]
    riders.sort(key=lambda r: (comp.cat_order().index(r.cat)
                               if r.cat in comp.cat_order() else 99,
                               r.bib or 9999))
    if not riders:
        notify.info("no_riders_for_filter")
        return

    event_codes = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]
    heads = comp.event_headers(event_codes)
    lim = comp.quotas.max_events_per_rider
    count_reserves = comp.quotas.max_events_count_reserves
    df = pd.DataFrame([{
        "key": r.key,
        **{label(f): getattr(r, f) for f in GRID},
        **{heads[s]: (r.events[s].flag if s in r.events else "")
           for s in event_codes},
        label("n_events"): r.n_events(include_reserves=count_reserves),
        "Max": lim.get(r.cat) or None,
    } for r in riders])

    edited = st.data_editor(
        df, hide_index=True, use_container_width=True, key="ver_editor",
        disabled=[label(f) for f in ("uci_id", "cat", "n_events")] + ["key", "Max"],
        column_config={
            "key": None, "Max": None,
            # Off the grid: at the licence desk the jury reads a dorsale and a
            # name, and two long society columns pushed the specialità - the
            # ones being ticked - off the right edge. The data is still there
            # (the elenco iscritti prints it), just not in the way here.
            label("club"): None, label("club_code"): None,
            label("checked_in"): st.column_config.CheckboxColumn(
                width="small", help=help_text("checked_in")),
            label("not_starting"): st.column_config.CheckboxColumn(
                width="small", help=help_text("not_starting")),
            label("bib"): st.column_config.NumberColumn(width="small"),
            label("n_events"): st.column_config.NumberColumn(
                width="small",
                help=help_text("n_events", reserves=(
                    help_text("n_events_reserves") if count_reserves else ""))),
            **{heads[s]: _event_column(comp, s, heads[s], df[heads[s]])
               for s in event_codes},
        },
    )
    _quota_note(edited, lim)

    reason = st.text_input(ui("edit_reason"), key="ver_reason",
                           help=help_text("edit_reason"))
    b1, b2 = st.columns([1, 2])
    if b1.button(ui("save_edits"), type="primary"):
        patches = _diff(df, edited, heads, reason)
        if not patches:
            notify.info("no_edits_to_save")
            return
        # A tick at the licence desk is self-explanatory; changing a rider's
        # data is not, and still has to say why.
        if not reason.strip() and any(p.op not in E.CHECK_IN_OPS
                                      for p in patches):
            notify.error("reason_required")
            return
        current = E.load_overlay(store)
        E.save_overlay(store, current + patches)
        notify.ok("edits_saved", n=len(patches))
        st.rerun()

    todo = [r for r in riders if not r.checked_in and not r.not_starting]
    if todo and b2.button(ui("mark_verified", n=len(todo))):
        current = E.load_overlay(store)
        E.save_overlay(store, current + [
            E.Patch(target=r.key, op="set_checked_in", value=True,
                    reason=ui("check_in_reason")) for r in todo])
        notify.ok("riders_verified", n=len(todo))
        st.rerun()


def _event_column(comp: Competition, event: str, head: str, values: pd.Series):
    """Event cell: a fixed X / R choice, free text where riders pair up.

    In a team event the letter says which squadra of the region a rider is in,
    and the jury decides how far down the alphabet that goes - a dropdown of
    A/B/C would just be in the way, so those columns are typed.
    """
    ev = comp.event(event)
    if ev.fmt in ("madison", "timed_team"):
        what = label("pair" if ev.fmt == "madison" else "team").lower()
        return st.column_config.TextColumn(
            head, width="small", required=False, max_chars=2,
            help=help_text("event_flag_group", event=ev.name, what=what))
    options = ["", "X", "R"]
    # a flag the workbook wrote but we do not offer has to stay selectable,
    # or the grid refuses to render the row
    options += sorted({str(v) for v in values if str(v) not in options})
    return st.column_config.SelectboxColumn(
        head, options=options, width="small", required=False,
        help=help_text("event_flag", event=ev.name))


def _quota_note(df: pd.DataFrame, lim: dict[str, int]) -> None:
    """Name the riders over the STP event limit, right under the grid."""
    n_col = label("n_events")
    if not lim or n_col not in df:
        return
    over = []
    for _, row in df.iterrows():
        m = row["Max"]
        if row[label("not_starting")] or not pd.notna(m) or row[n_col] <= m:
            continue
        bib = "" if pd.isna(row[label("bib")]) else int(row[label("bib")])
        over.append(f"{row[label('cat')]} {bib} {row[label('last_name')]} "
                    f"{row[label('first_name')]} ({int(row[n_col])})")
    if over:
        notify.warn("over_event_limit", limits=_limits(lim),
                    who=" · ".join(over))


def _limits(lim: dict[str, int]) -> str:
    return ", ".join(msg("limit_of", cat=cat, n=n) for cat, n in lim.items())


def _diff(before: pd.DataFrame, after: pd.DataFrame, heads: dict[str, str],
          reason: str) -> list[E.Patch]:
    """Turn the grid's changes into explicit patches.

    `heads` maps event code -> the header that column was drawn with, so the
    diff works whichever of the two headings the grid is showing.
    """
    short_to_code = {head: code for code, head in heads.items()}
    out: list[E.Patch] = []
    for i in range(len(before)):
        key = before.at[i, "key"]
        for name in EDITABLE:
            col = label(name)
            old, new = before.at[i, col], after.at[i, col]
            if (pd.isna(old) and pd.isna(new)) or old == new:
                continue
            val = None if pd.isna(new) else new
            if name == "bib" and val is not None:
                val = int(val)
            out.append(E.Patch(target=key, op="set_field", field=name,
                               value=val, reason=reason))
        for name, op in (("checked_in", "set_checked_in"),
                         ("not_starting", "set_not_starting")):
            col = label(name)
            if bool(before.at[i, col]) != bool(after.at[i, col]):
                out.append(E.Patch(target=key, op=op, value=bool(after.at[i, col]),
                                   reason=reason or (ui("check_in_reason")
                                                     if name == "checked_in" else "")))
        for short, code in short_to_code.items():
            old, new = str(before.at[i, short] or ""), str(after.at[i, short] or "")
            if old.strip() == new.strip():
                continue
            if not new.strip():
                out.append(E.Patch(target=key, op="clear_event", field=code,
                                   reason=reason))
            else:
                out.append(E.Patch(target=key, op="set_event", field=code,
                                   value=new.strip(), reason=reason))
    return out


def _history(store: Store) -> None:
    patches = E.load_overlay(store)
    if not patches:
        return
    with st.expander(ui("edits_recorded", n=len(patches))):
        st.dataframe(pd.DataFrame([{
            ui("edit_when"): p.ts, ui("edit_rider"): p.target,
            ui("edit_op"): p.op, ui("edit_field"): p.field,
            ui("edit_value"): "" if p.value is None else str(p.value),
            ui("edit_reason_col"): p.reason,
        } for p in reversed(patches)]), hide_index=True, use_container_width=True)
        if st.button(ui("undo_last_edit")):
            E.save_overlay(store, patches[:-1], action="undo_edit")
            st.rerun()
