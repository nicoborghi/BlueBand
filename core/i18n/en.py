"""English: the same catalogue as `it.py`, key for key.

UCI vocabulary throughout, and the abbreviations a printed sheet uses are the
UCI ones (Bib, Rnd, TT, DNF), not spelled-out words: a column heading has a few
millimetres, and a commissaire reads the regulations in these.

The keys are the Italian file's keys and nothing here invents one: what is
missing is answered from `it.py`, so a key that has drifted shows an Italian
word on the page instead of failing - see `core.i18n`.
"""

from __future__ import annotations

#: What this language is called, in itself, in the picker in Settings.
NAME = "English"


# ── ordinals ────────────────────────────────────────────────────────────────


def ordinal(n: int) -> str:
    """1 -> '1st', 11 -> '11th', 22 -> '22nd'."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


# ── field / column labels ───────────────────────────────────────────────────

FIELDS = {
    "bib": "Bib",
    "last_name": "Surname",
    "first_name": "Name",
    "full_name": "Rider",
    "uci_id": "UCI ID",
    "fci_code": "Licence",
    "cat": "Cat.",
    "nation": "Nat",
    "club": "Club",
    "club_code": "Club code",
    "region": "Region",
    "province": "Prov.",
    "sex": "Sex",
    "birth_date": "Born",
    "certificate_date": "Certificate",
    "reserve_entry": "Reserve",
    "checked_in": "Ver.",
    "not_starting": "NS",
    "n_events": "Ev.",
    "note": "Notes",
    # the two columns of the PUIS, read on the Decisions page
    "infringement": "Infringement",
    "sanction": "Sanction",
}


# ── race sheets ─────────────────────────────────────────────────────────────

RACE = {
    "rank": "Pl.",
    "group": "Group",
    "team": "Team",
    "teams": "teams",     # counted on the sheet: "3 teams started"
    "pair": "Pair",
    "pairs": "pairs",
    "heat": "Heat",
    "heat_no": "Ht.",
    # where one team starts at a time (team sprint) the column counts starts,
    # not heats
    "start_no": "Ord.",
    "round": "Round",
    "time": "Time",
    "points": "Points",
    "laps": "Laps",
    "total": "Tot.",
    "sprint": "Sprint",
    "qualified": "Qual.",
    # where a rider lines up for the next race of an omnium: the standings are
    # its start order, and they start alternately at the balustrade and at the
    # rail, in the order the sheet ranks them
    "lane_balustrade": "Bal.",
    "lane_rail": "Rail",
    "points_total": "Total Points",
    "points_of": "Points",       # "Scratch Points" - + the name of the race
    "reserve_short": "res",      # marks the rider a reserve replaced
    "final": "Final",
    "champion_team": "NATIONAL CHAMPION TEAM",
    "champion_region": "NATIONAL TRACK CHAMPION REGION",
    "champion_m": "NATIONAL CHAMPION",
    "champion_f": "NATIONAL CHAMPION",
    # sprint: two runs and a decider that is often not ridden
    "run_1": "Run 1",
    "run_2": "Run 2",
    "run_3": "decider",
    "day": "Day",
    "event": "Event",
    "competition": "Competition",
    "distance": "Km",
    # what a head count counts, and the two words a sheet is numbered by
    "starters": "starters",
    "entered": "entered",
    "athletes": "riders",
    "number": "No.",             # a team's or a pair's number, not a bib
    "team_en": "Team",           # the entrant a rider rides for, on a sheet
    "general_classification": "GENERAL CLASSIFICATION",
    "final_classification": "Final Classification",

    "laps_down": "Laps down",

}


# ── documents ───────────────────────────────────────────────────────────────

DOCS = {
    "partenti": "Start List",
    "risultati": "Results",
    "classifica": "Classification",
    # the omnium races: the sheet the jury scores the race on, and the standings
    # after it - which are the start order of the race that follows
    "gara": "Race",
    "classifica_parziale": "Standings",
    "risultati_recuperi": "Rep. results",
    "risultati_5-8": "Results 5th-8th",
    # a keirin publishes the start order of its repechages on a communiqué of
    # its own, and rides a second final whose places depend on how many ride it:
    # the picker names it with the range it is actually run for
    "partenti_recuperi": "Repechages",
    "risultati_finale_b": "Final B results",
    # the results of a finals round rank the four who rode the two finals:
    # "Results" alone does not say which sheet it is next to the 5th-8th
    "risultati_1-4": "Results 1st-4th",
    "repechages": "Repechages",
    "final_5_8": "Final for 5th-8th Place",
    # what each final rides for, as it is written on the sheet: the slash is
    # the two places one race decides, the dash a range of them
    "final_1_2": "1st/2nd",
    "final_3_4": "3rd/4th",
    "final_5_8_short": "5th-8th",
    "entry_list": "LIST OF ENTRIES",
    "startlist": "Start List",
    "start_order": "Start Order",
    "classification": "Classification",
    "communique": "Communiqué",
    "communique_no": "Communiqué no.",
    "register": "Communiqué register",
    "register_col_n": "No.",
    "register_col_day": "D.",
    "register_title": "COMMUNIQUÉ REGISTER",
    "decisions_title": "REGISTER OF DECISIONS",
    "decisions_slug": "decisions-register",
    "penalty_col": "Measure",
    "issued": "Issued",
    "issued_at": "When",
    "decision": "Decision",
    "document": "Document",
    "signature": "For the commissaires' panel:",
    "printed_at": "Issued on",
    "off_plan": "unscheduled",
    "draft": "draft",           # file-name prefix of a non-definitive sheet
    # the sheet a team asks for: who of ours rides what, and in which heat
    "team_recap": "TEAM ENTRY SUMMARY",
    "team_recap_slug": "summary",
    "team_recap_all_slug": "team-summaries",
    # the event table: how many riders each category fields in what
    "speciality_table": "EVENT TABLE",
    "speciality_table_slug": "event-table",
    # the medal table, on paper: the columns are written out, not the medals of
    # the screen - an emoji is not a heading a sheet can be read out from
    "medal_table_title": "MEDAL TABLE",
    "medal_table_slug": "medal-table",
    "medal_gold": "Gold",
    "medal_silver": "Silver",
    "medal_bronze": "Bronze",
    "podium_detail_title": "PODIUMS",
    "trofeo_table_title": "REGIONS TROPHY STANDINGS",
    "trofeo_table_slug": "trophy-standings",
    "trofeo_detail_title": "POINTS, EVENT BY EVENT",
    "trofeo_points": "Points",
    "trofeo_placing_points": "Plac.",
    "trofeo_participation": "Part.",
    "trofeo_starters": "Starters",
    "trofeo_wins": "Wins",
    "trofeo_placings": "Placings",
    "programme_title": "RACE PROGRAMME",
    "programme_slug": "programme",
    "programme_start": "Time",
    "programme_startlist": "St.",
    "programme_results": "Res.",
    "programme_classification": "Class.",
    "programme_sheets": "Communiqués",
    "entry_list_slug": "entries",
    "startlist_slug": "startlist",
    "register_slug": "communique-register",
    "letterhead_slug": "letterhead",
    "document_slug": "document",
}


# ── statuses ────────────────────────────────────────────────────────────────
#
# The codes themselves are UCI and are the same in every language: what changes
# is what they are called in a picker, below.

STATUSES = {
    "OK": "",
    "REL": "REL",
    "DNF": "DNF",
    "ABD": "ABD",
    "DNS": "DNS",
    "DSQ": "DSQ",
    "NS": "NS",            # not starting, declared before the event
    "W": "W",              # warning: carried into the rounds that follow
}

STATUS_NAMES = {
    "REL": "Relegated",
    "DNF": "Did not finish",
    "ABD": "Abandoned",
    "DNS": "Did not start",
    "DSQ": "Disqualified",
    "NS": "Not starting",
    "W": "Warned",
}


# ── penalties ───────────────────────────────────────────────────────────────
#
# The four degrees a penalty is given in (`core.decisions.CLASSES`), in
# increasing gravity. The letter is what the jury writes and what the UCI
# tables use; this is what it means.

#: What a round is called when its name has to fit a column heading. The keys
#: are programme vocabulary (`formats.omnium`), not labels: only what does not
#: fit in full is here - "Points Eliminazione" eats the column next to it,
#: "Points Elim." does not. A round that is not here prints as it is written.
ROUNDS_SHORT = {
    "Eliminazione": "Elim.",
}


PENALTIES = {
    "A": "Warning",
    "B": "Fine",
    "C": "Relegation",
    "D": "Disqualification",
}

# The same four said the other way round - by what the block on the sheet *is*
# rather than by the letter it was given under (`core.decisions.KINDS`) - plus
# the note, which is not a penalty at all: what the tint settings and the recap
# of an event are labelled with.

NOTE_KINDS = {
    "disqualification": "Disqualification",
    "relegation": "Relegation",
    "fine": "Fine",
    "warning": "Warning",
    "note": "Note",
}


# ── issue codes ─────────────────────────────────────────────────────────────
#
# What a finding is *about*, one word, shown in bold in front of it. The code
# itself is what the tests match on; this is the word the jury reads
# (`ui.notify.issues`).

CODES = {
    "teams": "Teams",
    "pairs": "Pairs",
    "total": "Total",
    "speciality_table": "Event table",
    "import": "Import",
    "uci": "UCI ID",
    "region": "Region",
    "bib": "Bib",
    "bib_dup": "Duplicate bib",
    "certificate": "Certificate",
    "quota_rider": "Event limit",
    "event_not_run": "Event not scheduled",
    "quota_region": "Region quota",
    "quota_club": "Club quota",
    "quota_club_region": "Club-per-team quota",
    "quota_teams": "Team quota",
    "quota_cat": "Category quota",
    "quota_teams_cat": "Category team quota",
    "round_no_day": "Round with no day",
    "cat_no_event": "Category with no event",
    "day_empty": "Empty day",
}


# ── controls: what every page, button and field is called ───────────────────

UI = {
    # -- the app shell -------------------------------------------------------
    "page": "Page",
    "page_races": "Races",
    "page_check_in": "Check-in",
    "page_decisions": "Decisions",
    "page_documents": "Documents",
    "page_stats": "Statistics",
    "page_programme": "Programme",
    "page_settings": "Settings",
    "programme_problems": "{n} problems in the programme",

    # -- pickers shared by several pages -------------------------------------
    "competition": "Competition",
    "category": "Category",
    "categories": "Categories",
    "event": "Event",
    "round": "Round",
    "day": "Day",
    "region": "Region",
    "state": "State",
    "all_f": "(all)",
    "all_days": "all",
    "table_font": "Table body",
    "table_font_pdf": "Table body, .pdf",
    "table_font_screen": "Table body, on screen",
    "landscape": "Print landscape",
    "title_suffix": "Added to the title",
    "title_suffix_hint": "e.g. updated version",
    "signature_tick": "Sign «For the commissaires' panel»",
    "save_pdf": "Save PDF",
    "save_pdf_all": "Save PDF (all)",
    "print_hint": "{n} {what} - print with Ctrl+P",
    "document_one": "document",
    "document_many": "documents",

    # -- entry file: chosen and reloaded in Settings -------------------------
    "entries": "List of entries",
    "entries_source": "Entry file (read-only)",
    "import_reload": "Import / Reload",
    "export_effective": "Export XLSX (effective list)",
    "overlay_kept": "{n} jury edits are re-applied on every reload.",
    "use_overlay": "Keep the edits apart (do not write to the file)",
    "save_to_file": "Write to the entry file",

    # -- check-in ------------------------------------------------------------
    "entry_list_title": "List of entries",
    "athletes": "Riders",
    "verified": "Checked in",
    "todo": "To do",
    "teams": "Teams",
    "pairs": "Pairs",
    "total": "Total",
    "speciality_table": "Event table",
    "check_in_progress": "Licence check: {done} of {total}",
    "check_in_left": "-{n} to do",
    "check_in_complete": "complete",
    "state_all": "All",
    "state_todo": "To check",
    "state_done": "Checked in",
    "state_ns": "NS",
    "checks_summary": "Checks - {errors} to resolve, {warnings} warnings",
    "stp_exemptions": "Authorised exemptions: {list}",
    "edit_reason": "Reason for the edit (required)",
    "save_edits": "Save edits",
    "edits_recorded": "Edits recorded ({n})",
    "undo_last_edit": "Undo the last edit",
    "edit_when": "when",
    "edit_rider": "rider",
    "edit_op": "operation",
    "edit_field": "field",
    "edit_value": "value",
    "edit_reason_col": "reason",
    "last_import": "Last import: {when}",
    "import_summary": "{n} riders · {file}",
    "reading_entries": "Reading the entry file...",

    # -- documents: which group of the page ----------------------------------
    "document_group": "Documents",
    "docs_entries": "Entry lists",
    "docs_batch": "Batches of documents",
    "docs_register": "Communiqué register",

    # -- documents: entry lists ----------------------------------------------
    "print_mode": "Print",
    "mode_by_category": "By category",
    "mode_by_event": "By event",
    "mode_all_events": "All events of one category",
    "mode_by_day": "By day",
    "mode_by_communique": "By communiqué",
    "mode_by_team": "By team",
    "mode_speciality_table": "Event table",
    "short_headers": "Short names instead of UCI codes",
    "all_event_columns": "A column for every event",
    "show_column": "Show {name}",
    "rule_categories": "Rule between the categories",
    "communique_carries": "Communiqué {n} · {title} — {docs}",
    "row_number": "Row number",
    "event_matrix": "Event matrix",
    "include_ns": "Include NS",
    "include_reserves": "Include reserves",
    "only_verified": "Checked in only",
    "minimal_columns": "Essential columns",
    "not_final": "Not final",
    "decision_note": "Decision / notes",
    "print_all_entries": "⚡ Print every entry list ({n} communiqués)",
    "building_documents": "Building the documents...",
    "check_in_line": "{cat}: {done}/{total} checked in · {left} still to check",

    # -- documents: batches and register -------------------------------------
    "documents": "Documents",
    "planned": "Planned",
    "issued": "Issued",
    "next_free": "Next free",
    "title": "Title",
    "team": "Team",
    "team_group": "What a team is",
    "team_group_region": "Region (representative side)",
    "team_group_club": "Club",
    "team_group_province": "Province",
    "team_group_nation": "Nation",
    "team_name": "What it is called on the documents",
    "save_register_pdf": "Save the register as PDF",
    "print_preview": "Print preview",
    # the blocks printed under a table: their tints, and whether they open
    # with the compact UCI code (Settings → Appearance)
    "note_colors": "Decisions on the communiqués",
    "note_colors_reset": "↩ Default tints",
    "decision_codes": "UCI code on the communiqué (A1, C3)",

    # -- decisions -----------------------------------------------------------
    "decision_body": "Decision",
    "penalty_quick": "Quick penalties",
    "penalty_reason": "Reason (UCI table)",
    "penalty_class": "Measure",
    "puis_panel": "What the national table says",
    "puis_column": "Column of the table",
    "puis_search": "Search",
    "puis_updated": "National table updated {when} · {n} entries",
    "penalties_updated": "UCI table updated {when}",
    "decisions_taken": "Decisions recorded ({n})",
    "decision_head": "no. {n} · {when}",
    "decision_delete": "🗑 Delete",
    "decision_edit": "Correct",
    # the panel that files a decision from the race being run, and the
    # register the Decisions page keeps of them all
    "decision_panel": "Decisions",
    "decision_file": "💾 Record",
    "decision_update": "Update",
    "decisions_here": "In this round ({n})",
    "show_warnings": "Warnings (W) on the sheets",
    "decisions_register": "Register of decisions",
    "save_decisions_pdf": "Save the register as PDF",
    "decisions_filter_cat": "Category",
    "decisions_filter_event": "Event",
    "decisions_all": "All",
    # the popover that files one: the columns of the register, in the order
    # they are filled in, and the sentence they compose
    "decision_add": "➕ New decision",
    "decision_round": "Round",
    "decision_bib": "Bib",
    "decision_code": "UCI penalty",
    "decision_code_none": "None (note)",
    "decision_proposal": "Proposed wording",
    "decision_recompose": "↻ Recompose",
    "decision_no_starters": "No starters: type the bib by hand.",
    "decision_bib_other": "Other...",
    "decision_summary": "Decisions of this event",
    "decision_summary_none": "No decision in this event.",
    "decision_of_round": "{round} ({n})",

    # -- races: the sheet being prepared -------------------------------------
    "race_line": "{n} starters · {info} · format: {fmt} · last saved: {saved}",
    "never_saved": "-",
    "save": "💾 Save",
    "save_heats": "💾 Save heats",
    "save_start_order": "💾 Save start order",
    "save_pairing": "💾 Save pairing",
    "restore_previous": "↩ Restore the previous version",
    "club_column": "Club column",
    "lane_column": "Balustrade / rail column",
    "points_race_detail": "Points race detail",
    "time_column": "Times column",
    "bib_column": "Bib column",

    # -- races: result entry -------------------------------------------------
    "eliminations": "Eliminations",
    "elimination_order": "Bibs in order of elimination",
    "sprints": "Sprints",
    "sprint_n": "Sprint {n}",
    "sprint_mark": "{n}",
    "sprint_mark_final": "{n} (×2)",
    "arrival_order": "Finishing order",
    "sprint_string_box": "String",
    "volata_n": "Sprint {n}",
    "times": "Times",
    "unridden_finals": "Finals not ridden",
    "unridden_final": "Final {name}",
    "final_ridden": "Ridden",
    "final_tied": "Tied ({place})",
    "final_on_qual": "Qualifying times",
    "laps_gained": "Laps gained",
    "laps_lost": "Laps lost",
    "statuses": "Statuses",
    "heats": "Heats",
    "heat_composition": "Composition",
    "heat_order_by_heat": "Finishing order by heat",
    "heat_n": "Heat {n}",
    "heat_one": "Heat",
    "heat_short": "Ht. {n}",
    "heat_bibs": "bibs separated by commas",
    "arrival": "finishing order",
    "lane_n": "Lane {n}",
    "bibs": "Bibs",
    "reserves_are": "reserves: {bibs}",

    # -- races: heat / start-order builder ----------------------------------
    "build_start_order": "Start order composition",
    "build_heats": "Heat composition",
    # how a timed round is run: two at a time, or one at a time
    "starts_mode": "How it is run",
    "starts_two": "Two at a time (heats)",
    "starts_one_riders": "One rider at a time",
    "starts_one_teams": "One team at a time",
    "fill_in_entry_order": "Fill in entry order",
    "start_n": "Start {n}",
    "notation_is": "Notation: `{text}`",
    "not_placed_yet": "Not placed yet ({n}): {who}",
    "all_in_heats": "Every entrant is in a heat.",
    "all_in_start_order": "{who} are in the start order.",
    "everyone_teams": "all the teams",
    "everyone_riders": "all the riders",
    "not_in_heat_yet": "Not in a heat yet ({n}): {who}",
    "all_in_heat": "Everyone is in a heat.",
    "heats_not_composed": "Heats not composed yet.",

    # -- races: sprint -------------------------------------------------------
    "next_rounds": "Following rounds",
    # the two ways a sprint tournament is run, as the dropdown offers them
    "scheme_12": "12 qualified - 1st round - quarterfinals - semifinals - finals",
    "scheme_8": "8 qualified - quarterfinals - semifinals - finals",
    "scheme_line": "{qualified} qualified · {rounds}",
    "scheme_repechages": " · repechages in the 1st round",
    "ride_final_5_8": "The final for 5th-8th place is ridden",
    "no_final_5_8_line": ("Only the finals for 1st-4th are ridden: from 5th "
                          "place on, the classification follows the 200 m "
                          "times."),
    "winners_round_1": "1st round winners",
    "repechages": "Repechages",
    "finals_1_4": "Finals 1st-4th",
    "final_5_8": "Final 5th-8th",
    "runs": "Runs",
    "place_n": "{n}",
    "final_n_place": "{name} place",
    "wins": "→ **{who}** wins",
    "load_round_1": "Load 1st Round",
    "load_quarters": "Load Quarterfinals",
    "load_semifinals": "Load Semifinals",
    "load_finals": "Load Finals",
    "load_repechages": "Load Repechages",
    "load_generic": "Load {round}",
    "update_finals": "Update Finals",
    "load_madison_final": "Load into the final",
    "load_omnium_final": "Load into the races",
    "compose_heats": "Compose heats",

    # -- races: keirin -------------------------------------------------------
    "keirin_shape": "{n} entered · UCI table {lo}-{hi}",
    "keirin_stage": "{round}: {heats} heats",
    "keirin_stage_rep": " + {n} repechages",
    "ride_final_b": "The second final (7th-12th place) is ridden",
    "no_final_b_line": ("Only one final is ridden: the others are classified "
                        "by the round they reached."),
    "compose_race": "Composition · {race}",
    "arrivals_of": "Finishes · {race}",
    "final_named": "Final for {name} place",
    "round_repechages": "{round} - Repechages",
    # the block a results sheet composes underneath itself is named after the
    # round it is the start order of: the register calls these two by their
    # full name, which is not the key the programme schedules them under
    "quarters_full": "Quarterfinals",
    "semifinals_full": "Semifinals",
    "finals_full": "Finals",

    # -- races: madison ------------------------------------------------------
    "pairing_line_heats": "{n} pairs · {heats} heats scheduled",
    "pairing_line_direct": "{n} pairs · straight final, no heats",
    "number_1_to_n": "Number 1..N",
    "spread_into_heats": "Spread across the heats",
    "pair_number": "Pair no.",
    "head_number": "**No.**",
    "head_heat": "**Ht.**",
    "head_pair": "**Pair**",
    "head_black": "**Black**",
    "head_red": "**Red**",
    "eliminate_last": "The last pairs do not qualify",
    "eliminate_line": "{sizes} starters → **{through} pairs in the final**",
    "eliminate_track_limit": " · track limit: {n}",
    "pairs_in_heat": "**{round}** - {n} pairs",
    "heat_qualified": "Heat {n}: {through} qualified, {out} eliminated",

    # -- races: composing the heats of an omnium -----------------------------
    # the same page as the madison, without the numbers: riders ride under
    # their own bib and the only decision is who rides in which heat
    "riders_line_heats": "{n} riders · {heats} qualifying heats",
    "riders_line_direct": "{n} riders · no qualifying heats",
    "eliminate_line_riders": "{sizes} starters → **{through} admitted**",
    "riders_in_heat": "**{round}** - {n} riders",
    "heat_qualified_riders": "Heat {n}: {through} admitted, {out} eliminated",
    "the_prove": "the omnium races",

    # -- races: omnium -------------------------------------------------------
    "partial_after_scratch": "{scratch} Results and {next} Start Order",
    "partial_standings": "Standings and {next} Start Order",
    "results_of": "{round} Results",
    "round_results": "{round} - Results",
    "round_repechage_results": "{round} - Repechages - Results",
    "final_5_8_results": "Final for 5th-8th place - Results",
    "finals_1_2_3_4_results": "Finals for {a} and {b} place - Results",
    "results_short": "{what} res.",

    # -- statistics ----------------------------------------------------------
    "medal_table": "Medal table",
    "gold": "🥇 1st",
    "silver": "🥈 2nd",
    "bronze": "🥉 3rd",
    "medals": "Medals",
    "podium_places": "Podiums",
    "events_counted": "Events completed",
    "events_open": "Not completed",
    "include_unfinished": "Count events that are not completed too",
    "stats_detail": "Podiums, event by event",
    "stats_open_list": "Events not completed yet ({n})",
    "stats_provisional": "provisional",
    "stats_partial": "partial results",
    "stats_no_result_yet": "no result",
    "stats_position": "Pos.",
    "stats_who": "Riders",
    "stats_download": "⬇ Download CSV",
    "save_medals_pdf": "Save the medal table as PDF",
    "stats_print_detail": "Print the podiums as well",
    "stats_no_printed_at": "Without «Issued on…»",
    "trofeo_table": "Regions Trophy standings",
    "trofeo_detail": "Points, event by event",
    "trofeo_scale": "Points table",
    "trofeo_scale_final": "National final (art. 9)",
    "trofeo_scale_qualifying": "Qualifying round (art. 8)",
    "trofeo_total": "Total",
    "trofeo_champion": "Champion",
    "trofeo_teams_scored": "Teams scoring",
    "trofeo_points_awarded": "Points awarded",
    "trofeo_print_detail": "Print the points event by event as well",
    "save_trofeo_pdf": "Save the Trophy standings as PDF",
    "trofeo_download": "⬇ Download CSV",

    # -- programme -----------------------------------------------------------
    "prog_tab_competition": "Competition",
    "prog_tab_check": "Check",
    "prog_tab_checks": "Checks",
    "check_cat": "Category",
    "check_event": "Event",
    "check_unit": "Counts",
    "check_per": "Per",
    "check_max": "Max",
    "check_level": "Level",
    "check_reserves": "Reserves",
    "check_note": "Article",
    "check_any": "All",
    "check_unit_riders": "riders",
    "check_unit_teams": "teams",
    "check_unit_pairs": "pairs",
    "check_unit_events": "events",
    "check_per_region": "team",
    "check_per_club": "club",
    "check_per_club_in_region": "club within the team",
    "check_per_cat": "category",
    "check_per_rider": "rider",
    "check_level_error": "error",
    "check_level_warn": "warning",
    "check_level_off": "off",
    "checks_migrate": "Turn the old quotas into rules",
    "date": "Date",
    "count_categories": "Categories",
    "count_rounds": "Rounds",
    "count_days": "Days",
    "count_riders": "Riders entered",
    "event_minutes": "Duration (min)",
    "day_begin": "Start",
    "day_end": "End",
    "ready_dates": "The dates of the competition",
    "ready_events": "Every category has its events",
    "ready_events_no": "{n} categories with no event: {list}",
    "ready_days": "Every round is on a day",
    "ready_days_no": "{n} rounds are on no day at all",
    "ready_clock": "Every day has a start time",
    "ready_clock_no": "Days with no start time: {list}",
    "ready_register": "The communiqué register is planned",
    "ready_register_no": ("The register is behind the programme: {n} lines "
                          "would change (Giornate → Recount the numbers)"),
    "ready_entries": "The entry list has been built",
    "entry_format": "File format",
    "entry_upload": "Entry file (.xls / .xlsx)",
    "entry_read": "{n} riders read · {cats}",
    "entry_numbering": "How to hand out the bibs",
    "entry_bibs_as_imported": "1…N as they are in the file",
    "entry_bibs_by_cat": "1…N per category, running on",
    "entry_bibs_by_cat_restart": "From 1 in every category",
    "entry_build": "Build the entry list of the competition",
    "entry_import_first": "Import the entry list",
    "map_columns": "⇄ Map the columns",
    "map_columns_save": "Save the mapping",
    "map_columns_none": "— none —",
    "entry_import_open": "Import a corrected entry list",
    "entry_replace": "Replace the entry list",
    "entry_delta_added": "New",
    "entry_delta_removed": "Withdrawn",
    "entry_delta_changed": "Changed",
    "entry_delta_kept": "Marks kept",
    "entry_delta_detail": "Detail ({n})",
    "entry_book_here": "Entry list of the competition: `{path}`",
    "entry_book_sync": "↻ Follow the programme",
    "prog_tab_categories": "Categories, events and days",
    "prog_tab_days": "Schedule",
    "save_programme": "💾 Save programme.yaml",
    "reload_programme": "↩ Reload from the file",
    "programme_counts": "{events} races scheduled · {communiques} communiqués · `{path}`",
    "yaml_preview": "File preview",
    "competition_name": "Name",
    "competition_short": "Short name",
    "competition_id": "Federation ID",
    "competition_location": "Venue",
    "competition_kind": "Kind of meeting",
    "kind_championship": "Championship",
    "kind_ordinary": "Ordinary",
    "kind_trofeo_regioni": "Regions Trophy",
    "track_len": "Track length (km)",
    "dates": "Dates (one per day, separated by commas)",
    "dates_hint": "2026-09-05, 2026-09-06",
    "dates_caption": "The dates decide how many days the competition has: "
                     "one date, one «Day» tab.",
    "categories_caption": "The categories racing, in the order they appear in "
                          "everywhere in the app.",
    "events_of_category": "Events contested",
    "prog_tab_events": "Events",
    "events_caption": "What each event is, for every category riding it. The "
                      "values are the UCI ones: touched only in the particular "
                      "cases.",
    "rounds_of_race_caption": "Which rounds are ridden, and on which day. "
                              "Unticking one takes it out of the programme (an "
                              "omnium without the scratch starts on the "
                              "elimination).",
    "round_ridden": "Ridden",
    "running_order": "No.",
    "pick": "•",
    "move_whole_race": "Move the whole race",
    "move_to_day": "Move to day…",
    "move_go": "Move",
    "picked_n": "{n} rounds picked",
    "title_join": " and ",
    "number_on_classification": "Number the classification only",
    "communique_rules": "Communiqué rules",
    "recount": "Recount the numbers",
    "recount_go": "Apply the numbers",
    "recount_regroup": "Redo the groupings as well",
    "recount_this_day": "Day {day} only",
    "recount_what": "What",
    "recount_was": "Now",
    "recount_now": "Becomes",
    "recount_why": "Why it stays",
    "recount_more": "…and {n} more.",
    "recount_moved": "moves",
    "recount_added": "new",
    "recount_dropped": "leaves the register",
    "recount_held": "stays",
    "held_issued": "already issued",
    "held_pinned": "typed by hand",
    "held_ret": "annulled",
    "sheet_on": "communiqué {n}",
    "sheet_carried": "the number prints on the other sheet",
    "sheet_unnumbered": "no communiqué",
    "rides_with": "Goes out with…",
    "rides_with_go": "Put together",
    "rides_alone": "on its own",
    "rides_alone_go": "Split it off",
    "composition_round": "{name}: the jury composes it in Gare, before the race is ridden.",
    "round_duration": "Duration",
    "day_start": "Start of the racing",
    "round_start_hint": "14:30",
    "round_sheet_note": "Start order note",
    "round_sheet_note_hint": "Printed on the start order",
    "round_results_note": "Results note",
    "round_results_note_hint": "Printed on the results sheet",
    "round_note": "Working note",
    "round_note_hint": "Stays in the programme, never printed",
    "event_settings_caption": "They hold for every category riding this "
                              "event.",
    "event_settings_under": "Settings of {event}: under {cat}, the first "
                            "category riding it.",
    "add_category_code": "New code",
    "add_category_hint": "MA",
    "programme_matrix": "Categories × events",
    "programme_matrix_caption": "How many rounds, and on which days. An empty "
                                "box: the category does not ride that event.",
    "rounds_no_day": "{n} with no day",
    "event_notes": "Start notes",
    "event_notes_caption": "The line the «Decision / notes» field of every "
                           "start order begins from.",
    "note_startlist": "On every start order",
    "note_qualifying": "On the qualifying rounds only",
    "note_finals": "On the finals only",
    "feminine": "feminine",
    "events": "Events",
    "events_settings_edit": "What each event is",
    "save_events": "💾 Save the events",
    "sheet_lines": "Default communiqué notes",
    "sheet_lines_language": "In the language of the competition: {language}.",
    "save_sheet_lines": "💾 Save the lines",
    "restore_sheet_lines": "↩ Back to the shipped ones",
    "masculine": "masculine",
    "code": "Code",
    "short_name": "Short name",
    "abbr": "UCI code",
    "format": "Format",
    "team_size": "Riders/team",
    "per_start": "Per start",
    "entry_columns": "Entry file columns",
    "order": "Order",
    "day_line": "Day {day} · {date}",
    "rounds_of_day": "Rounds of the day",
    "rounds_of_day_caption": "The rounds ridden on this day, in the order "
                             "they go on the track. An event can be split "
                             "over more than one day.",
    "round_of": "{cat} · {event} · {round}",
    "off_day": "Remove",
    "assign_docs": "Assign the documents",
    "assign_docs_go": "Assign to every round",
    "docs_classification": "Classification on the round that closes an event",
    "docs_repechages": "Repechage sheets (sprint and keirin)",
    "docs_keep_edited": "Leave the rounds already changed by hand",
    "com_partenti": "Start order no.",
    "com_risultati": "Results no.",
    "com_classifica": "Classification no.",
    "communiques_of_round": "Communiqués of this round",
    "merge_communiques": "⇄ One communiqué",
    "show_communiques": "Communiqué numbers",
    "show_race_line": "Km, laps and sprints",
    "mark_issued": "Highlight",
    "issued_tint": "Colour",
    "communiques_left_caption": "What goes out on this day and is not a round "
                                "of the running order above.",
    "n_km": "{n} km",
    "n_minutes": "{n}′",
    "n_laps": "{n} laps",
    "n_sprints": "{n} sprints",
    "laps_derived": "{km} km on a {track} m track is {laps} laps.",
    "round_to_edit": "Round to edit",
    "n_rounds": "{n} rounds",
    "day_n": "Day {n}",
    "day_short": "D{n}",
    "day_none": "—",
    "add_rounds": "Add rounds to the day",
    "rounds_to_add": "Rounds",
    "add": "Add",
    "round_default": "Final",
    "qualify": "Qualify",
    "eliminate": "Eliminate",
    "setup_round": "Setup",
    "communiques_of_day": "Communiqués of the day",
    "communiques_of_day_caption": "The order of this table is the order they "
                                  "go out in. **Adjacent rows with the same "
                                  "number are the same sheet**: that is how "
                                  "one communiqué carries a start order and a "
                                  "classification together.",
    "register_range": "communiqués {first}-{last} ({n} documents)",

    # -- settings ------------------------------------------------------------
    "track": "Track",
    "races_scheduled": "Races scheduled",
    "communiques_planned": "Communiqués planned",
    "competition_line": "{name} - {location} - {dates}",
    "programme_path": "Programme: `{path}`",
    "out_folder": "Communiqué folder",
    "path": "Path",
    "save_folder": "Save folder",
    "restore_default": "Restore the default",
    "documents_in_folder": "{n} documents in the current folder",
    "folder_will_be_created": "The folder will be created on the first save.",
    "produced_documents": "Documents produced",
    "file": "File",
    "modified": "Modified",
    "appearance": "Look of the communiqués",
    "fonts": "Fonts",
    "font_element": "Element",
    "font_value": "Font",
    "font_color": "Colour",
    "font_default": "Default",
    "font_sample": "Sample Trophy - round 1",
    "set": "Set",
    "restore_all_defaults": "↩ Restore every default",
    "font_family": "Whole sheet (family)",
    "font_title": "Title",
    "font_subtitle": "Subtitle",
    "font_table_title": "Table heading",
    "font_info": "Information line",
    "font_legend": "Legend",
    "font_communique": "«Communiqué no.» box",
    "font_printed_at": "Printed-at line",
    "font_decision": "Decision box",
    "font_decision_tag": "Decision tag",
    "font_signature_label": "«For the jury» caption",
    "font_signature": "Signature",
    "font_body": "Letterhead body text",
    "font_footline": "Foot line",
    "letterhead": "Letterhead and footer",
    "communique_align": "Communique number",
    "sheet_slots": "Header and footer lines",
    "docs_letterhead": "Letterhead sheet",
    "letterhead_title": "Title",
    "letterhead_subtitle": "Subtitle",
    "letterhead_text": "Text",
    "slot_head": "Under the letterhead",
    "slot_foot": "Above the footer",
    "slot_left": "Left",
    "slot_center": "Centre",
    "slot_right": "Right",
    "slot_none": "-",
    "slot_communique": "Communiqué no.",
    "slot_printed_at": "Issued on",
    "head_gap": "Space above (mm)",
    "foot_gap": "Space below (mm)",
    "header_img": "Letterhead",
    "footer_img": "Footer",
    "image_fit": "How it sits on the sheet",
    "fit_page": "Fit to the page",
    "fit_size": "Size and alignment",
    "image_width": "Width (% of the sheet)",
    "image_align": "Alignment",
    "header_top": "Distance from the top edge (mm)",
    "footer_bottom": "Distance from the bottom edge (mm)",
    "align_left": "Left",
    "align_center": "Centred",
    "align_right": "Right",
    "save_named": "Save {what}",
    "advanced": "Advanced settings",
    "signature": "Signature",
    "signature_how": "How to sign",
    "signature_file": "Signature file",
    "save_signature": "Save signature",
    "signature_name": "Name of the secretary of the commissaires' panel",
    "save_name": "Save name",
    "signature_where": "Where to apply it",
    "sig_mode_image": "Image of the signature",
    "sig_mode_text": "Name and surname (text in bold)",
    "sig_scope_always": "Everywhere",
    "sig_scope_results": "Results and classifications only",
    "sig_scope_never": "Never",
    "name_style": "Name",
    "name_style_how": "How a rider is printed",
    "name_split": "Surname + Name (two columns)",
    "name_full": "Full name (one column)",
    "name_split_example": "ROSSI · Mario Luigi",
    "name_full_example": "ROSSI Mario Luigi - a single «Name» column",
    "name_width": "Width of the «Name» column",
    "language": "Language",
    "language_how": "What the app and the documents are written in",
    "round_start": "Time",
    "race_options": "How it is run",
    "repropose": "↩ Re-propose",
    "repropose_round": "↩",
    "option_scheme": "Qualified from the 200 m",
    "option_final_5_8": "The 5th-8th final is ridden",
    "option_final_b": "The second final is ridden",
    "option_heats": "Qualifying heats",
    "option_eliminate": "Eliminated from each heat",
    "option_qualify": "Qualified for the finals",
    "option_team_size": "Riders a team",
    "add_pause": "➕ Add a pause",
    "pause_text": "Text of the pause",
    "edited_fields": "edited by hand: {list}",
    "setup_title": "New competition",
    "setup_intro": "Let us build the programme",
    "setup_create": "Create the programme",
    "track_len_m": "Track length (m)",
    "new_competition": "➕ New competition",
    "new_competition_name": "Folder name",
    "create": "Create",
    "add_event": "Add an event",
    "add_categories": "Standard categories",
    "add_event_other": "Another (by hand)",
    "event_code_new": "Code",
    "starts_per_race": "How they start",
    "starts_pairs": "In pairs (two at a time)",
    "starts_single": "One at a time",
    "option_per_start": "How they start",
    "option_direct_final": "How the pursuit is ridden",
    "timed_with_finals": "Qualifying + final for four",
    "timed_direct": "Direct final",
    "recent_races": "Latest races",
    "penalties_shown": "Measures",
    "measure_a": "Warnings",
    "measure_c": "Relegations",
    "measure_d": "Disqualifications",
    "register_range_filter": "Numbers",
    "export_xlsx": "Export Excel",
    "credit": "Released under the GPLv3 License © 2026 {name}",
    "programme_print": "Programme sheet",
    "prog_sheet_columns": "Columns",
    "prog_sheet_merge": "Merged columns",
    "prog_sheet_issued": "Issued communiqués",
    "prog_sheet_layout": "Page layout",
    "programme_times": "Time",
    "programme_durations": "Duration",
    "programme_merge_round": "Event and round",
    "programme_merge_results": "Results and classification",
    "programme_bold_final": "Final classifications in bold",
    "save_programme_pdf": "Save the programme as PDF",
    "reset_event": "Clear a race",
    "reset_confirm": "Confirmed: delete {n} races of {cat} · {event}",
    "reset_with_results": " ({n} with results)",
    "reset_button": "Clear the race",
    "backup": "Backup",
    "backup_dest": "Copy destination",
    "backup_button": "Make a backup copy",
    "journal": "Operations log (last {n})",
    "final_band": "FINAL FOR {name} PLACE",
    "col_results": "Results",
    "col_starters": "Starters",
    "col_last_saved": "Last saved",
    "yes_short": "yes",
    "none_short": "-",

    # -- derny -------------------------------------------------------------
    "derny_view": "View",
    "derny_board": "Passings",
    "derny_log": "Chronological",
    "derny_stats": "Statistics",
    "derny_call": "Number at the line",
    "derny_start": "Go",
    "derny_start_at": "Start {at}",
    "derny_start_clear": "Clear start",
    "derny_undo": "Undo last number",
    "derny_standings": "Provisional standings",
    "derny_lap_n": "L{n}",
    "derny_lap": "Lap",
    "derny_clock": "Time",
    "derny_lap_time": "Lap time",
    "derny_sigma": "Deviation from the mean (σ)",
    "derny_mean": "mean",
    "derny_sd": "σ",
    "derny_laps_ridden": "laps",
    "derny_delete": "Delete",
    "derny_flagged": "{n} laps outside the band",
    "derny_start_time": "Start time",
    "derny_row_no": "No.",
    "derny_splits": "Splits",
    "derny_insert": "Insert a passing",
    "derny_insert_do": "Insert",
    "derny_prev_lap": "Lap before again",
    "derny_laps_left": "{n} laps to go",
    "derny_over": "Arrival: the winner has crossed, the ranking is closed",
    "derny_after_row": "After row no.",
    "derny_lap_axis": "Lap no.",
    "laps_down_column": "Laps down column",

}


# ── help texts ──────────────────────────────────────────────────────────────

HELP = {
    "check_cat": ("The category the rule is about. \"All\" where the article "
                  "does not distinguish."),
    "check_event": ("The event it is about. \"All\" for a rule that holds over "
                    "the whole meeting - the limit on events per rider is "
                    "one."),
    "check_unit": ("What is counted: riders entered, teams, madison pairs, or "
                   "events - the one thing counted per rider."),
    "check_per": ("What it is counted for: team, club, club within a team, or "
                  "the whole category."),
    "check_max": "How many there may be. 0 turns the rule off.",
    "check_level": ("How going over is reported: error (red), warning, or "
                    "off. Neither blocks any work."),
    "check_reserves": ("Whether reserve entries count towards the total. "
                       "Normally not: starters are counted."),
    "check_note": ("Where the rule comes from - \"Art. 4 reg. TR 2026\". It is "
                   "printed after the finding."),
    # -- notation ------------------------------------------------------------
    "bibs_csv": "Bibs separated by commas.",
    "teams_pick": "You pick the team, not the bib.",
    "status_dns": ("Did not start: they never took the start. They stay at "
                   "the foot of the classification under the DNS sigla, like "
                   "the riders who did not finish."),
    "status_dnf": ("Did not finish: started, did not finish. They keep the "
                   "points they scored and are written in the order they left "
                   "the race: the last to leave is the first of the DNFs."),
    "status_abd": ("Abandoned: they left the race of their own accord. Their "
                   "points are not printed; the order is the order of the "
                   "field, the last to pull out is the first of them."),
    "status_dsq": "Disqualified: out of the classification.",
    "status_rel": "Relegated: they stay in the classification, at the back.",
    "sprint_order": "Finishing order of the sprint, bibs separated by commas.",
    "sprint_final": "Final sprint: it scores 10-6-4-2.",
    "sprint_string": ("Every sprint on one line: «,» separates the bibs, «-» "
                      "the sprints. E.g. 3,7,1,9-7,3,9,1"),
    "heat_bibs": "Bibs of the heat, separated by commas.",
    "heat_order": ("Finishing order of the heat: bibs separated by commas, "
                   "the winner first."),
    "heat_notation": ("Heat composition: `,` riders of the same team, `-` "
                      "opponents in the same heat, `/` next heat. E.g. "
                      "`1,2,3,4-5,6,7,8/9,10,11,12-13,14,15,16`"),
    "heat_notation_same": "Same notation: `/` separates the heats.",
    "laps_csv": ("Bibs separated by commas. A bib repeated counts one lap each "
                 "time: `3, 3` = two laps."),
    "elimination_order": ("The first eliminated is the last in the classification. Every rider is typed, the winner included: the winner is the last bib on the line. Whoever is not typed stays without a placing."),
    "time_format": "Time as m:ss,mmm.",
    "unridden_final": ("How the final is settled when it is not ridden. "
                       "«Tied»: the two are classified together in {place} "
                       "place and the place above stays empty. «Qualifying "
                       "times»: the two are placed on their qualifying time, "
                       "the only one they have ridden. Either way, those "
                       "behind them do not move."),
    # The one legend of the inline flags, shared by every field that shows them
    # (see `core.checks.FLAGS`): one notation, one explanation.
    "flags": ("?N bib N is not a starter · !N bib N is repeated · -N N bibs "
              "missing · <N fewer than N placed · ? line cannot be read."),

    # -- races ---------------------------------------------------------------
    "sprint_scheme": ("Decides how many riders the 200 m qualifies and which "
                      "rounds are ridden afterwards. It is the line that goes "
                      "on the start order below."),
    "final_5_8_toggle": ("Off, the quarterfinals do not compose the 5th-8th "
                         "final: there is no results sheet for it and from "
                         "5th place on the classification of the event "
                         "follows the qualifying times. It is decided here "
                         "because it applies before the quarterfinals compose "
                         "anything."),
    "final_b_toggle": ("Off, the keirin has a single final: the last round "
                       "composes the final for the title only, there is no "
                       "results sheet for the second one and the others are "
                       "classified by the round they reached. It is decided "
                       "here because it applies before the last round "
                       "composes anything."),
    "reserve_bibs": ("Replace the number of a rider who does not start with "
                     "the reserve's."),
    "starts_mode": ("Two at a time is the pursuit heat (one per straight); "
                    "one at a time is a start order, like the team sprint. It "
                    "applies to this round: changing it re-queues what you "
                    "have already composed, without losing the order."),
    "fill_pairs": "Pair the entrants two by two, then correct what needs it.",
    "fill_start_order": ("Puts {who} in entry order, then correct what needs "
                         "it."),
    "number_pairs": ("Renumber the pairs in the order of this list (team, "
                     "then pair)."),
    "spread_pairs": ("Assigns the pairs round-robin: heat 1, heat 2, heat 1, "
                     "... The order is by team, and splitting it in half "
                     "would put half the alphabet in a single heat."),
    "eliminate_pairs": ("Pairs eliminated from EACH heat, among those that "
                        "started (UCI 3.2.157: never fewer than 2)."),
    "spread_riders": ("Assigns the riders round-robin: heat 1, heat 2, heat "
                      "1, ... The order is by bib, and splitting it in half "
                      "would put half the category in a single heat."),
    "eliminate_riders": ("Riders eliminated from EACH heat, among those that "
                         "started. The others are admitted to the four "
                         "omnium races. The starting value is the one in the "
                         "programme."),
    "compose_next": "Composes «{round}»{extra} from these results.",
    "compose_next_uci": ("Composes «{round}» from these results, following the "
                         "UCI table."),
    "load_finals": ("Carries the classification into «{round}»: the finals are "
                    "composed from the first qualifiers."),
    "load_madison_final": ("Carries into «{round}» the pairs qualified from "
                           "every heat."),
    "load_omnium_final": ("Carries into the four omnium races the riders "
                          "admitted from every heat, alternating them heat by "
                          "heat."),
    "compose_from_previous": "Composes this round from the previous classification.",

    # -- sheet options -------------------------------------------------------
    "signature_tick": ("Prints the signature of the secretary of the "
                       "commissaires' panel at the foot of the document. The "
                       "default is set in Settings → advanced."),
    "club_column": ("Adds each rider's club of registration and the club code, "
                    "beside the representative side."),
    "lane_column": ("The standings are the start order of the next race: adds "
                    "an untitled column alternating Bal. and Rail."),
    "points_race_detail": ("Points carried into the points race from the first "
                           "three races, every sprint and lap, as well as the "
                           "total."),
    "time_column": "The times stay on the results of every round.",
    "bib_column": "Adds the «classic» bib next to the pair number.",
    "font_pdf": "Body text size in the PDF to be printed.",
    "font_color": ("The colour the element is printed in. The title and the "
                   "\u00abComunicato n.\u00bb box follow the colour of the "
                   "competition: changed here they stop following it, and "
                   "Restore the default puts them back in line."),
    "font_element": ("What is being set: the title, the subtitle, the box of "
                     "a decision. \u00abWhole sheet\u00bb is the font family "
                     "of every communiqué."),
    "restore_all_defaults": ("Clears every choice of this section from "
                             "settings.json: the sheets go back to the way a "
                             "freshly installed app prints them."),
    "font_screen": ("The preview below only: it is the page the announcer "
                    "reads during the race."),
    "landscape": ("More room for the columns, but on a landscape sheet the "
                  "browser does not repeat the letterhead on the pages that "
                  "follow."),
    "landscape_short": ("On a landscape sheet the browser does not repeat the "
                        "letterhead on the pages that follow."),
    "title_suffix": ("Text appended to the title of every printed document - "
                     "«updated version», «correction». The file name and the "
                     "communiqué number do not change."),

    # -- startlists ----------------------------------------------------------
    "row_number": ("Grey counter to the left of the table: it says how many "
                   "there are and gives the jury a reference to point at on "
                   "the sheet."),
    "event_matrix": ("Columns on the right with the event codes and an X for "
                     "those entered in them."),
    "only_verified": ("Prints only those who passed the licence check (at "
                      "least one event entered on the Check-in page)."),
    "draft": ("Provisional sheet: instead of the communiqué number it prints "
              "an orange NOT FINAL box, and the file is saved as draft_."),
    "print_all_entries": ("Saves the entry list of every category into the "
                          "communiqué folder."),

    # -- entry file ----------------------------------------------------------
    "entries_source": ("The file sent by the federation: the ksport export "
                       "(Iscritti_NNNNNN_KSPORT.xlsx) or the workbook with "
                       "one sheet per category. It is never modified: it can "
                       "be reloaded whenever a new one arrives."),
    "use_overlay": ("On, whatever the jury changes in Check-in is kept apart "
                    "and re-applied on top of the file at every reload; the "
                    "file is never touched. Off, Check-in writes straight "
                    "into the workbook: the cell is modified in the file and "
                    "the file re-read (a copy of the previous one goes into "
                    ".snapshots). Checked-in and NS only go there if the file "
                    "has the columns (they have to be added by hand and "
                    "declared in entries.check_in in the programme). Edits "
                    "already recorded are not lost: they stay apart and come "
                    "back when it is switched on again."),

    # -- team recap ----------------------------------------------------------
    "team_group": ("How riders are grouped in the classification and in the "
                   "team summary: the side that enters them, the club they "
                   "are registered with, the province or the nation. At a "
                   "national championship it is the region."),
    "team_name": ("The word printed on the documents in place of «Team» - for "
                  "example «Representative side», «Club» or «Nation»."),
    "team_recap": ("One sheet per team: every rider in a single table, one "
                   "column per event with X, R or the pairing letter and, "
                   "where the jury has already composed it, the heat."),
    "all_event_columns": ("Prints a column for every event the team's "
                          "categories contest, including those with no entry "
                          "yet: this is the sheet handed over before the "
                          "check-in, to collect the events by hand. Off, only "
                          "the columns somebody is already entered in."),
    "rule_categories": ("Draws a rule where the category changes, so a "
                        "sheet with four of them on it reads as blocks "
                        "instead of one long list."),
    "short_headers": ("Heads the event columns with the short name («Ind. "
                      "Pursuit», «Madison») instead of the UCI code («IP», "
                      "«MD»). It reads without a legend, but the columns are "
                      "wider: with many events the code is the better bet."),
    "name_width": ("How much of the width of the two Surname and Name columns "
                   "the single column takes: 1.00 takes it all, below that it "
                   "leaves the rest to the columns the sheet is actually read "
                   "for - sprints, points, club."),

    # -- decisions -----------------------------------------------------------
    "penalty_class": ("A warning, B fine, C relegation, D disqualification. "
                      "It gives the box on the communiqué its tint."),
    "penalty_quick": ("The infringements of the UCI table, with the number "
                      "they are to be cited by. For reference: the wording of "
                      "the decision is composed in the entry form."),
    "puis_panel": ("The national table of sporting infringements: what the "
                   "federation provides for each one, in the column of the "
                   "categories racing. For reference; it does not decide."),
    "decision_panel": ("The decision is written here, in the race it was "
                       "taken in: it reaches the register of Decisions "
                       "already referred to a category, an event and a "
                       "round."),
    "show_warnings": ("Prints a W beside those who took a warning in this "
                      "event: they carry it into every round that follows. "
                      "Two warnings in the same round are a disqualification."),
    "decision_codes": ("Opens the box of the decision with the compact code it "
                       "was taken under (A1, C3). Normally not: the "
                       "communiqué carries the decision written out, the code "
                       "stays in the jury's register."),
    "decision_code": ("Measure and UCI article, in compact code: A1, C3, D5. "
                      "The measure gives the box on the communiqué its tint, "
                      "the article the grounds."),
    "decision_bib": ("The bib it refers to, chosen among the starters of the "
                     "round. Several bibs are written separated by commas."),
    "decision_proposal": ("The wording proposed from the fields above, in the "
                          "style of the decisions already recorded. It is a "
                          "proposal: correct it, it is what goes on the "
                          "communiqué."),
    "decision_summary": ("What has already been decided in this event, round "
                         "by round."),

    # -- check-in ------------------------------------------------------------
    "checked_in": ("Verified: the jury has entered at least one event. There "
                   "is no tick to set, only what the rider rides."),
    "not_starting": "Not starting: they take no part in the races.",
    "n_events": "Events as a starter{reserves}.",
    "n_events_reserves": " or reserve",
    "edit_reason": "The NS tick does not need a reason.",
    "event_flag": "{event}: X entered, R reserve",
    "event_flag_group": ("{event}: X entered, R reserve; a letter (A, B, C, "
                         "...) the region's {what}, the same letter with R "
                         "(AR, BR, ...) its reserve"),

    # -- statistics ----------------------------------------------------------
    "medal_table": ("An event counts once only, on its final classification: "
                    "the omnium, the sprint and the keirin over every round, "
                    "the others on the last round ridden."),
    "include_unfinished": ("Events whose last round has not been ridden yet "
                           "stay out of the count. Ticking this brings them "
                           "in, with the podium as it stands."),
    "stats_print_detail": ("On the sheet, under the medal table, the list of "
                           "the podiums it is counted from: a line can be "
                           "checked against the communiqués without reopening "
                           "the app."),
    "stats_no_printed_at": ("Removes the «Issued on…» line from the footer. "
                            "The medal table is reprinted all day: without a "
                            "date and time, two identical copies stay "
                            "identical. The page number stays."),
    "trofeo_table": ("The per-region standings of the Regions Trophy "
                     "regulation: the first ten of every event score off the "
                     "points table, plus 1 participation point for each "
                     "rider, team or madison pair that takes the start. Ties "
                     "are settled by races won, then participation points, "
                     "then the score in the last event of the programme."),
    "trofeo_scale": ("Art. 9 for the national final "
                     "(14-12-10-8-6-5-4-3-2-1), art. 8 for the qualifying "
                     "rounds (10-9-8-7-6-5-4-3-2-1). The participation point "
                     "is the same in both."),
    "trofeo_print_detail": ("On the sheet, under the standings, every region's "
                            "score in every event: a line can be checked "
                            "against the communiqués without reopening the "
                            "app."),

    # -- programme -----------------------------------------------------------
    "save_programme": ("Rewrites `programme.yaml`. The previous version stays "
                       "in `.snapshots/`. It touches no race, entry or "
                       "communiqué already issued."),
    "programme_print": ("The race programme with the communiqué number of "
                        "every sheet beside it: one row per round, in the order "
                        "they are ridden. It is the sheet that sits on the "
                        "jury's table."),
    "reload_programme": "Throws away the unsaved edits and re-reads the file.",
    "track_len": ("The laps of every distance that does not declare them are "
                  "computed from this."),
    "dates": "E.g. 2026-08-04, 2026-08-05",
    "category_sex": ("Decides CHAMPION / CHAMPIONESS and the feminine forms on "
                     "the sheets."),
    "event_format": ("Decides how it is run and how it is scored: bunch, "
                     "elimination, timed, sprint, keirin, omnium, madison."),
    "team_size": "Riders a team fields (0 if it is individual).",
    "per_start": ("How many start together in a timed round: 2 the pursuit, 1 "
                  "the team sprint and the 200 m."),
    "event_minutes": ("How long one round of this event takes, in "
                      "minutes. It is the duration that applies when a round "
                      "states none of its own, and the day's timetable is "
                      "built out of it."),
    "entry_columns": ("What the column is called in the entry file, when it "
                      "does not match the name. Several variants separated by "
                      "commas."),
    "restore_sheet_lines": ("Drops the lines rewritten in this language: the "
                            "ones the app ships come back. The other languages "
                            "are not touched."),
    "note_feminine": ("The same line written in the feminine. Empty: the one "
                      "beside it is used."),
    "programme_note": ("Your own note on the race: it survives a save, a "
                       "comment in the file does not."),
    "move_up": "Move earlier",
    "move_down": "Move later",
    "remove_race": "Take this race off the day",
    "race_options": ("What decides how the event is run: the rounds come out "
                     "of it, with distances, laps and sprints proposed from the "
                     "regulation and the track length. All of it editable "
                     "afterwards, and re-proposable with ↩."),
    "option_direct_final": ("«Qualifying + final for four»: the teams qualify "
                            "against the clock and the fastest four ride the "
                            "two finals. «Direct final»: one race, the times "
                            "are taken and the classification comes straight "
                            "out of them - what a category without four teams "
                            "rides. Either way, whether they start two or one "
                            "at a time is chosen next to it."),
    "pause_text": ("What prints on the programme sheet, in italic, in the "
                   "column of the event - a pause is not a race and it "
                   "reads as one. Empty means «Pause»."),
    "option_team_size": ("How many riders each team fields in this race. "
                         "What is proposed is the regulation number for the "
                         "event - four in a team pursuit, three in a "
                         "team sprint - and it is changed only where this "
                         "category is authorised to ride with another one. "
                         "It is the number the teams are built to at the "
                         "check-in and the one the jury is warned against at "
                         "the track."),
    "repropose": ("Rebuilds the rounds from the regulation, keeping your notes "
                  "and your durations. Whatever you had corrected by hand "
                  "goes back to the proposal."),
    "round_start": ("When the round starts, on the programme sheet. It is not "
                    "typed: it is the start of the day plus the durations of "
                    "everything that runs before. Not a race time: that lives "
                    "in the results."),
    "scaletta_pick": ("Tick the rounds to move, then use the arrows below. The "
                      "selection survives the move, so three places is three "
                      "presses."),
    "move_whole_race": ("Tick one round and the whole event moves, in its "
                        "own order - including the rounds sitting at the other "
                        "end of the day."),
    "scaletta_top": "To the top of the day.",
    "scaletta_up": "Up one place.",
    "scaletta_down": "Down one place.",
    "scaletta_bottom": "To the bottom of the day.",
    "round_duration": ("How long the round takes, in minutes. The whole day's "
                       "timetable comes out of it. Empty means however long "
                       "that event usually takes (Settings → "
                       "Specialità), the way an empty distance does: what you "
                       "type here is the correction."),
    "day_start": ("The hour the racing starts - the only one anybody decides. "
                  "Every other one follows from it and from the durations, and "
                  "no round carries an hour of its own: that was a second "
                  "origin, and it is what made the durations look useless. "
                  "Left empty the day has no times at all, which is the right "
                  "thing to print until they are known."),
    "new_competition": ("Creates a folder under `competitions/` and opens the "
                        "programme builder in it. The name is the folder's, not "
                        "the championship's: short, no spaces - CITA26."),
    "competition_kind": ("Whether the meeting assigns titles. At a "
                         "championship the classifications print NATIONAL "
                         "CHAMPION TEAM under the winning quartet and NATIONAL "
                         "CHAMPION under the rider who wins the event; at an "
                         "ordinary meeting nothing is printed - there is a "
                         "winner, not a champion. It holds on every "
                         "classification."),
    "track_len_m": ("In metres: 250, 333.33, 400. The laps of every distance "
                    "come from it, and how many pairs the madison holds."),
    "add_categories": ("The usual categories, ready made: code, name and sex "
                       "already right. Tick the ones this competition races "
                       "and add them - the table below is where they are then "
                       "renamed, reordered or removed."),
    "add_event": ("The events of the catalogue: code, UCI abbreviation, format "
                  "and riders per team already right. All of it stays editable "
                  "in the table below."),
    "starts_per_race": ("The kilometre and the pursuit run on the same "
                        "machinery: in pairs, one per straight, or one at a "
                        "time. It is the starting value - the jury can change "
                        "it on the individual race."),
    "events_of_category": ("The events this category rides. Ticking one puts "
                          "the race in the programme with the rounds the "
                          "regulation proposes; unticking it removes the "
                          "race, rounds and all."),
    "category_name": ("What the category is called on every document: start "
                      "orders, results, classifications, communiqués."),
    "add_category_code": ("A code the catalogue has not got. Name and sex are "
                          "then written in the category's own block."),
    "remove_category": ("Removes the category. Its events have to go first: "
                        "the races would be left hanging off a category the "
                        "file no longer declares."),
    "remove_from_day": ("Takes the round off this day. It stays in the "
                        "programme, on no day, ready to be put elsewhere. "
                        "Tick it and it is applied with the rest of the "
                        "table."),
    "round_to_edit": ("Which round of the running order the fields below are "
                      "about. One at a time: they are a dozen fields, and a "
                      "day has thirty rounds."),
    "round_day": ("Which day this round is ridden on. «—»: none yet. Rounds "
                  "on different days are an event split - qualifying on the "
                  "Saturday, finals on the Sunday."),
    "rounds_to_add": ("The rounds of this race that are not on this day "
                      "yet."),
    "recent_races": ("The rounds you worked on last: one tap and the page goes "
                     "back to one, without walking through the three pickers "
                     "again."),
    "penalties_shown": ("Which measures appear here and on the printed "
                        "register. Taking one out hides it: the warnings are "
                        "the many, and hardly ever the ones to publish. Fines "
                        "and plain notes are not filtered - they always "
                        "stay."),
    "register_range_filter": ("From which number to which. The register of a "
                             "four-day meeting is long: print the piece that is "
                             "needed, not all of it."),
    "abbr": ("The UCI code, the one that goes in the narrow columns: SP, KE, "
             "IP, TP, MD. Empty, it comes from the code or from the format."),
    "communique_in_scaletta": ("The communiqué number this sheet goes out "
                               "under. The same number on two sheets is **one "
                               "communiqué carrying two documents** - which is "
                               "what a sprint does every round. 0 takes it out "
                               "of the register."),
    "merge_communiques": ("Puts every sheet of this round on one communiqué, "
                          "the first one's."),
    "show_communiques": ("Shows the communiqué number of the start order, the "
                         "results and the classification in the running order, "
                         "and lets them be typed there."),
    "mark_issued": ("Tints the cells of the communiqués already issued, as "
                    "the jury registered them: the sheet says by itself how "
                    "far the day has got. Off for the copy that goes on the "
                    "noticeboard."),
    "issued_tint": ("The colour the issued communiqués are laid on. Pale: the "
                    "sheet is read for its numbers."),
    "show_race_line": ("Shows what each event rides next to its name: "
                       "kilometres, laps and sprints, as they come from the "
                       "track when the round does not state them."),
    "programme_bold_final": ("Prints in bold the number of the final "
                             "classification, the one that closes the "
                             "event. Partial classifications - the races "
                             "of an omnium - stay plain."),
    "programme_times": ("The «Ora» column: the start of the day plus the "
                        "durations of what runs before. Empty where the day "
                        "has no start time."),
    "programme_durations": ("The 'Duration' column: how long each round takes. "
                            "It is what a day being planned is read for; the "
                            "sheet that goes on the noticeboard usually drops "
                            "it."),
    "entry_format": ("The shape the file arrived in. «Federal export» is what "
                     "the federation's own system sends - Fattore K or ksport, "
                     "it is the same file - one row per rider; «per category» "
                     "is the laid-out workbook, the one this page produces. "
                     "The header row is found, letterhead or no letterhead."),
    "map_columns": ("Says which column of the file is which field of Blue "
                    "Band. For a file that names things its own way or puts "
                    "something where you would not look for it - the team "
                    "inside «Note», the bib in a column with no heading."),
    "entry_upload": ("The file the federation sends. It is copied into the "
                     "folder of the competition: it is the record of what was "
                     "received."),
    "entry_numbering": ("Three ways, all of them ridden somewhere. «From 1 in "
                        "every category» is only usable where two categories "
                        "never line up together: two riders share a number the "
                        "moment they do."),
    "entry_book_sync": ("Writes the sheets and the columns again for the "
                        "programme as it is now. Bibs, ticks and event entries "
                        "stay: the file is read back before it is written."),
    "number_on_classification": ("When the results of a round and the "
                                 "classification go out on the same "
                                 "communiqué, the number is printed on the "
                                 "classification alone and the results carry "
                                 "none - one number, one sheet. Off, both "
                                 "print it."),
    "recount": ("Redoes the numbers from the programme, in the order the "
                "sheets can go out in, flowing around what is already issued, "
                "typed by hand or annulled. It shows what changes first."),
    "recount_regroup": ("Rereads which sheets travel together as well, by the "
                        "rules in Manifestazione: two sheets you had split "
                        "come back on one communiqué. Off, the groupings stay "
                        "as they are and only the numbers change."),
    "rides_alone_go": ("Gives this sheet a communiqué of its own, on the "
                       "first free number. The other half of \"goes out "
                       "with…\"."),
    "rides_with": ("Sends this sheet onto another one's communiqué: one "
                   "number, two documents. It is what a sprint does every "
                   "round - the results and the repechage start order on one "
                   "sheet."),
    "assign_docs": ("Writes the documents of every round of the programme "
                    "again, as the regulation has them. It is how not to tick "
                    "them by hand thirty times."),
    "docs_classification": ("The classification of an event goes out with the "
                            "round that closes it - the final, the last prova "
                            "of an omnium."),
    "docs_repechages": ("The sprint and the keirin file the sheets of their "
                        "repechages: a start order and results, on the same "
                        "communiqué as the round that composed them."),
    "docs_keep_edited": ("Leaves alone the rounds that state documents other "
                         "than the regulation's: somebody has already decided "
                         "those."),
    "running_order": ("Where the round runs in the day: type the number and "
                      "the running order closes around it, renumbered from 1. "
                      "More than one can be typed before it is applied: the "
                      "day is reshuffled in one go. It is the order they are "
                      "ridden in, so the communiqués follow it: a round moved "
                      "up takes its numbers with it."),
    "round_ridden": ("Whether this round is ridden. The regulation proposes it, "
                     "the jury decides: an omnium can be run without the scratch "
                     "and start on the elimination. Unticked it leaves the "
                     "programme and files no communiqués; ↩ Riproponi puts the "
                     "whole regulation back."),
    "round_sheet_note": ("Printed: it is the line the «Decision / notes» field "
                         "of this round's start order begins from, above the one "
                         "of the event."),
    "round_results_note": ("Printed: the line the risultati of this round "
                           "open on - the sheet that says who went through is "
                           "the one that has to say how many do. The "
                           "regulation proposes it and it follows the numbers "
                           "of the round; typed over, it stays as typed."),
    "round_note": ("Printed nowhere: the jury's note about the programme, and it "
                   "survives a save - a comment written by hand in the file does "
                   "not."),
    "round_distance": "Km. Empty: the round declares no distance.",
    "round_laps": ("Empty: computed from the track length. Write them only if "
                   "the race does not follow the formula."),
    "round_qualify": "How many go through to the next round.",
    "round_eliminate": "Madison: pairs eliminated from EACH heat (3.2.157).",
    "round_setup": ("A round that is not ridden: the jury composes it (numbers "
                    "and heats of the madison)."),
    "round_docs": "Documents separated by commas. For this event:",
    "communique_number": ("Repeat the same number on the next row to put two "
                          "documents on the same sheet."),
    "communique_doc": "Which sheet of the round.",
    "ret": "Cancelled communiqué: the number stays taken and prints «N RET».",

    # -- settings ------------------------------------------------------------
    "competition_folder": ("Data folder under `competitions/`. Chosen once: it "
                           "stays set when the app is reopened."),
    "out_folder": ("Where the PDFs of the communiqués are saved. It can be a "
                   "shared folder (Drive, a USB stick): it is created if it "
                   "is missing."),
    "signature_file": "PNG or SVG of the scanned signature.",
    "signature_name": ("Printed in bold in place of the image. No line "
                       "underneath."),
    "signature_scope": ("Sets the «Sign «For the commissaires' panel»» tick on "
                        "the Races and Documents pages. It stays a tick: the "
                        "jury can always change it on the individual sheet."),
    "header_img": "Banner at the top of the communiqué: competition, venue and dates.",
    "footer_img": "Strip at the foot of the sheet: sponsors, federation logos.",
    "image_fit": ("*Fit to the page* prints the image as wide as the sheet, "
                  "edge to edge: that is what a letterhead drawn for it wants. "
                  "A logo has proportions of its own and stretched across A4 "
                  "it is unreadable: give it a width and a side instead."),
    "image_width": ("How wide the image is, as a percentage of the width of "
                    "the sheet. It holds on A4 portrait and landscape alike."),
    "image_align": "Which side of the sheet the image sits on.",
    "letterhead_title": ("The title at the head of the sheet, as on a "
                         "classification. Empty: the name of the meeting."),
    "letterhead_subtitle": ("The smaller line under the title: what the sheet "
                            "is about."),
    "letterhead_text": ("The body of the sheet, written in markdown: **bold**, "
                        "*italic*, `# heading`, lists with «- ». A blank line "
                        "starts a paragraph. Everything else is text: what is "
                        "typed here never becomes markup on the sheet."),
    "sheet_slots": ("What prints on the line under the letterhead and on the "
                    "one above the footer: one item per position, or nothing. "
                    "It holds for every communiqué of the meeting."),
    "head_gap": ("How much air is left between the top edge of the sheet - or "
                 "the letterhead, where there is one - and the first printed "
                 "line."),
    "foot_gap": ("How much air is left between the last printed line and the "
                 "bottom edge of the sheet, or the footer where there is one. "
                 "The margin the sheet reserves for the footer grows by as "
                 "much."),
    "communique_align": ("Where the «Comunicato n.» box sits at the head of "
                         "the sheet: right as on the jury workbooks, centred "
                         "under the letterhead, or left."),
    "header_top": ("How much white paper is left above the letterhead. Zero "
                   "runs it to the edge, the way a letterhead is drawn; a logo "
                   "usually wants some air above it."),
    "footer_bottom": ("How much white paper is left below the footer. The "
                      "margin the sheet reserves for it grows by as much, so "
                      "the table never prints over it."),
    "language": ("What the app, the communiqués and the printed sheets are "
                 "written in. It is a setting of this competition: the "
                 "programme, the entry file and the races are not touched - "
                 "the names of the categories, the events and the rounds are "
                 "written in the programme and print as they stand there."),

    "derny_call": "One button per starter: press it as the number crosses the "
                  "line and the passing is stored with the moment. \"?\" is "
                  "the passing seen without reading the number. Only starters "
                  "have a button; a passing to be added by hand goes in from "
                  "Cronologico.",
    "derny_start": "Mark the gun: the first lap is measured from there. "
                   "Without it the first lap time is the second passing.",
    "laps_down_column": "Print the laps-down column on the classification. "
                        "Normally off: with nobody lapped it is a column of "
                        "zeros.",
    "derny_board": "One column per lap, in the order the numbers were called. "
                   "In light grey the lap a lapped rider did not ride, where "
                   "he would have come through; in red his number in the "
                   "column he reappears in, which is where the lap went; in "
                   "yellow the lap whose time falls outside the band.",
    "derny_log": "Every passing in the order it was called, first one first. "
                 "It is the only thing stored: correct bibs and times here, "
                 "add rows at the foot or delete them with the bin, and "
                 "everything else is drawn again.",
    "derny_bib_cell": "The bib called. \"?\" if the finish judge saw somebody "
                      "come through without reading the number.",
    "derny_insert": "Puts a passing back where it happened: the bib (\"?\" "
                    "as well) and the number of the row it goes after.",
    "derny_prev_lap": "Repeats the whole lap before into the lap after it: "
                      "the same numbers, in the same order, all on the same "
                      "hour. For the lap the bunch comes through together, "
                      "when there is no time to press ten buttons.",
    "derny_unknown_call": "A passing seen without reading the number: it holds "
                          "its place in the column and is nobody's lap until "
                          "you give it a bib in Cronologico.",
    "derny_insert_at": "The hour of the passing. It opens on the hour of the "
                       "row picked in \u201cAfter row no.\u201d - or on the "
                       "start time when it goes in at the head - and is "
                       "edited by hand.",
    "derny_sigma": "How many standard deviations a lap time may sit from the "
                   "rider's own mean before it is flagged. Mean and σ are "
                   "computed from the third available time on.",

}


# ── messages ────────────────────────────────────────────────────────────────

MSG = {
    # -- programme / configuration ------------------------------------------
    # the default text of a pause in the running order: it is only a default,
    # and what prints is whatever the jury types over it
    "pause": "Pause",
    "pause_added": "Pause «{text}» of {minutes}′ added.",
    "no_programme": "'{name}' contains no programme.yaml.",
    "no_competitions": "No competition in {path}",
    "cfg_no_categories": "No category defined.",
    "cfg_no_events": "No event defined.",
    "cfg_bad_track_len": "track_len is not valid.",
    "cfg_unknown_cat": "Programme: unknown category '{cat}'.",
    "cfg_unknown_event": "Programme: unknown event '{event}'.",
    "cfg_no_rounds": "Programme: {cat} {event} has no rounds.",
    "cfg_duplicate_communique": "Communiqué no. {n} duplicated ({a} / {b}).",

    # -- parsing the jury's shorthand ---------------------------------------
    "parse_missing_number": "Number missing{context}.",
    "parse_bad_bib": "'{token}' is not a valid bib{context}.",
    "parse_in_sprint": " (sprint {n})",
    "parse_in_heat": " (heat {n})",
    "parse_missing_time": "Time missing.",
    "parse_bad_time": "Time not valid: {text} (use mm:ss,mmm).",
    "parse_seconds_over_60": "Time not valid: {text} (seconds ≥ 60).",

    # -- entry list: reading the workbook ------------------------------------
    "xls_sheet_missing": "Sheet '{sheet}' missing from the entry file.",
    "xls_no_ksport": "Sheet '_KSPORT' missing: federation data not merged in.",
    "xls_column_missing": "[{cat}] column '{column}' missing in row {row}.",
    "xls_unknown_event_column": "[{cat}] unknown event column: {column}.",
    "xls_duplicate_rider": "[{cat}] duplicate rider (row {row}): {name} {key}.",
    "xls_missing_region": "[{cat}] region missing: {name}.",
    "xls_bad_flag": "[{cat}] {name}: {event} -> {note}",
    "xls_unknown_flag": "value not recognised: {value}",
    "xls_unknown_cat": "[{file}] category not recognised in row {row}: {value}",
    "ksport_not_in_category": ("[KSPORT] entrant not present in the category "
                               "sheets: {name} ({uci})."),
    "ksport_missing": ("{n} riders in the category sheets are not in KSPORT "
                       "(entry added by hand): {who}{more}"),
    "flat_field_unmapped": ("{field}: no column of the file is mapped onto "
                            "this field. «⇄ Map the columns», in Programma → "
                            "Gara."),
    "flat_column_missing": ("Column '{header}' ({field}) missing from the entry "
                            "file: the data was not imported."),

    # -- entry list: teams and pairs -----------------------------------------
    "team_loose_x": ("{where}: {n} riders with an X outside the teams "
                     "({bibs}): assign the letter (or {letter}R for the "
                     "reserve)."),
    "team_wrong_size": "{where}: {n} starters instead of {size} ({bibs}).",
    "team_region_wrong_size": "{where}: {n} riders instead of {size} ({bibs}){hint}",
    "team_compose_hint": ": compose the teams with A, AR, B, BR, ...",
    "pair_wrong_size": "[{cat} {event}] pair {who}: {n} riders instead of 2.",
    "pairs_guessed": ("[{cat} {event}] {region}: {n} riders with an X and no "
                      "pair given ({bibs}) - the pairs were formed in bib "
                      "order, to be confirmed."),
    "pairs_guessed_page": ("**{region}**: {n} riders with an X and no pair "
                           "given in the entry list. The pairs below were "
                           "formed in bib order - confirm them, or correct the "
                           "pairing in Check-in (Madison column: A, B, ...).  "
                           "\n{who}"),

    # -- entry list: overlay of jury edits -----------------------------------
    "patch_rider_gone": "{op} on a rider who is gone ({target}): {reason}",
    "patch_unknown_field": "unknown field '{field}' ({target})",
    "patch_not_entered": "{target} was not entered in {event}",
    "patch_no_pair_entry": "{target} is not entered in {event} (pair)",
    "patch_unknown_op": "unknown operation '{op}' ({target})",

    # -- entry list: validation ---------------------------------------------
    "rider_no_uci": "{cat} {bib} {name}: UCI ID missing.",
    "rider_no_team": "{name}: {what} not determined.",
    "rider_no_bib": "{name}: bib missing.",
    "rider_event_not_run": ("{cat} {bib} {name}: entered in {event}, which the "
                            "programme does not schedule for this category."),
    "rider_over_events": "{cat} {bib} {name}: {n} events (max {max}) - {events}.",
    "rider_old_certificate": "{cat} {bib} {name}: certificate of {date}, to be checked.",
    "duplicate_bib": "[{cat}] bib {bib} assigned to {a} and {b}.",
    "quota_region": "[{cat} {event}] {region}: {n} riders (max {max}).",
    "quota_club": "[{cat} {event}] {club}: {n} riders (max {max}).",
    "quota_club_region": ("[{cat} {event}] {region}: {n} riders from the same "
                          "club {club} (max {max}) - bibs {bibs}."),
    "quota_teams": "[{cat} {event}] {region}: {n} teams/pairs (max {max}).",
    "quota_cat": "[{cat} {event}] {n} riders entered (max {max}).",
    "quota_teams_cat": ("[{cat} {event}] {n} teams/pairs entered "
                        "(max {max})."),
    "over_event_limit": "Over the event limit ({limits}): {who}",
    "limit_of": "{cat} max {n}",

    # -- scoring: bunch races ------------------------------------------------
    "extra_sprints": ("{n} sprints entered, {planned} scheduled: the extra "
                      "ones are scored all the same."),
    "sprint_duplicate_bib": "Bib {bib} repeated in sprint {n}.",
    "sprint_unknown_bib": "Bib {bib} (sprint {n}) is not a starter.",
    "sprint_too_few": ("Sprint {n}: only {found} riders placed (at least "
                       "{expected} expected)."),
    "lap_gained_unknown": "Bib {bib} (lap gained) is not a starter.",
    "lap_lost_unknown": "Bib {bib} (lap lost) is not a starter.",
    "eliminated_twice": "Bib {bib} eliminated twice.",
    "bib_not_entered": "Bib {bib} is not a starter.",
    "too_many_eliminations": "{n} eliminations entered for {starters} starters.",

    # -- scoring: timed and bracket rounds -----------------------------------
    "same_time": "Two competitors on the same time ({ms} ms): check the photo finish.",
    "bib_in_two_heats": "Bib {bib} is in more than one heat.",
    "key_in_two_heats": "{who} is in more than one heat.",
    "not_in_any_heat": "Not placed in any heat: {bibs}.",
    "not_in_this_heat": "{who} does not ride in heat {n}.",
    "heat_no_result": "Heat {n}: result not entered.",
    "partial_standings": ("Standings after {done} races of {total}: {rounds}."),

    # -- races: what the page says while a race is being entered -------------
    "pages_need_entries": ("Verifica, Documenti, Gare, Decisioni and Statistics open once there is an entry list: it is built in Programma → Gara."),
    "entries_caption": ("The federation's file is never modified. Reload it "
                        "whenever a new one arrives: the edits made here "
                        "(bibs, teams, events) are recorded apart against the "
                        "UCI ID and are re-applied."),
    "team_caption": "On the documents the column is called «{name}» and holds: {group}.",
    "no_race_for_category": "No race scheduled for this category.",
    "no_pairs_entered": "No pair entered in this category.",
    "no_riders_entered": "No rider entered in this event.",
    "no_riders_for_filter": "No rider matches these filters.",
    "no_riders_for_selection": "No rider for this selection.",
    "no_documents_for_selection": "No document for this selection.",
    "teams_half_verified": ("Check-in started but not finished: {n} riders in a "
                            "{what} whose team-mates are already verified have "
                            "no event entered yet.\n\n{list}"),
    "stale_patches": "Edits no longer applicable after the re-import:\n\n{list}",
    "overlay_off": ("Check-in writes straight into the entry file. The {n} "
                    "edits already recorded stay apart and are not applied: "
                    "checked-in and NS go back to what is written in the "
                    "columns of the file, where there are any."),
    "edits_go_to_file": ("The edits on this page are written into {file} and "
                         "the file is re-read.{left_out}"),
    "check_in_not_in_file": (" {what}: the file has no column for this, so it "
                             "stays out."),
    "written_to_file": "{n} cells written into {file}.",
    "write_back_refused": "Not written into the file:\n\n{list}",
    "write_back_not_xlsx": ("{file} is not an .xlsx: only that format can be "
                            "written to."),
    "write_back_no_column": "{name}: «{what}» has no column in the file.",
    "write_back_no_event_column": ("{name}: the file has no {event} column in "
                                   "this sheet."),
    "write_back_row_gone": ("{name}: row {source} is no longer theirs, the "
                            "file has changed. Reload and try again."),
    "no_edits_to_save": "No edit to save.",
    "reason_required": "Give the reason for the edit.",
    "edits_saved": "{n} edits recorded.",
    "entries_imported": "Imported {n} riders from {file}.",
    "file_not_found": "File not found",
    "source_changed": "The file has changed since the last import",
    "exported_to": "Written {path}",

    # -- races: flags shown under an input field -----------------------------
    "sprint_hole": "Sprint {list} empty: the ones after it shift in the scoring.",
    "unplaced_riders": ("**{n} {who} not in the results yet**: {bibs}. They go "
                        "into the finishing order of the last sprint, or are "
                        "declared DNF / DNS / DSQ."),
    "pending_results": "{n} competitors still without a result.",
    "pending_times": ("Times not entered yet ({n} missing): the order above is "
                      "the start order, not a classification."),
    "times_missing": "{n} without a time: the classification does not place them.",
    "tied_final_who": "{place} place tied: {who}.",
    "qual_final_who": "On the qualifying time: {who}.",
    "no_previous_version": "No previous version.",
    "heat_wrong_size": ("Heat {heat}, lane {lane}: {n} bibs instead of {size} "
                        "({bibs})."),
    "status_field_error": "{field}: {error}",
    "communique_already_issued": ("Communiqué {n} already issued for «{title}»: "
                                  "issuing it again replaces it in the "
                                  "register."),
    "communique_duplicates": "Numbers issued more than once: {list}",
    "sheet_not_ready": "«{round}» has no result yet: {doc} does not go into the communiqué.",

    # -- races: composition --------------------------------------------------
    "entrant_twice_start_order_f": "already entered",
    "entrant_twice_start_order_m": "already entered",
    "entrant_twice_heat": "already in another heat",
    "odd_field_first": "Odd number of entrants: whoever rides alone goes in heat 1.",
    "odd_field_must_be_first": ("Odd number of entrants: one heat must have a "
                                "single competitor, and it is heat 1."),
    "heats_not_matched": ("Heats cannot be matched to the entrants of this "
                          "race: the notation stands."),
    "heats_from_previous": ("The heats are composed from the classification of "
                            "the previous round with the button below."),
    "duplicate_pair_numbers": ("Pair numbers repeated: {list}. Two pairs with "
                               "the same number cannot be told apart in the "
                               "order of the sprints."),
    "empty_heats": "No pair in {list}.",
    "empty_heats_riders": "No rider in {list}.",
    "heat_ordinal": "heat {n}",

    # -- races: sending a race on --------------------------------------------
    "round_not_in_programme": "Round not present in the programme.",
    "first_round_no_previous": "It is the first round: there is no classification to start from.",
    "no_previous_ranking": "No previous classification available.",
    "heats_composed_from": "Heats composed from {n} qualifiers.",
    "round_composed": "«{round}»: {n} heats composed.",
    "missing_result": "A result is still missing: the next round is not composed.",
    "missing_arrival": "A finishing order is still missing: the next round is not composed.",
    "need_two_qualified_f": "At least two qualifiers are needed.",
    "need_two_qualified_m": "At least two qualifiers are needed.",
    "finals_loaded": "«{round}»: {n} {who}, finals {names} composed.",
    "qualified_teams": "qualified teams",
    "qualified_riders": "qualifiers",
    "madison_heat_no_result": "«{round}»: no result, its pairs are not in the final.",
    "madison_no_qualified": ("No pair qualified: enter the results of the "
                             "heats first."),
    "madison_final_loaded": "«{round}»: {n} pairs in the final.",
    "omnium_heat_no_result": ("«{round}»: no result, its riders are not among "
                              "those admitted."),
    "omnium_no_qualified": ("No rider admitted: enter the results of the heats "
                            "first."),
    "omnium_final_loaded": "{round}: {n} riders admitted.",

    # -- races: what has not been loaded yet ---------------------------------
    "finals_not_loaded": ("Finals not loaded from the qualifying round. Open "
                          "«{round}» → **Results** → **Load Finals**: the "
                          "seeding (3rd/4th and 1st/2nd), the times and {who} "
                          "come from there."),
    "finals_not_loaded_keirin": ("Finals not loaded. Run «{round}» → "
                                 "**Results** → **Load Finals**: the two "
                                 "finals and their starters come from there."),
    # a sprint tournament is seeded round by round: a round opened before the
    # one before it has composed shows the whole entry list and no heats
    "sprint_round_not_loaded": ("«{round}» is not composed yet: open «{prev}» → "
                                "**{doc}** → **{button}**. Without it, the "
                                "round starts with every entrant and no "
                                "heats."),
    "qualifying_no_times": "«{round}» has no times saved yet.",
    "teams_not_qualified": "teams not qualified",
    "riders_not_qualified": "riders not qualified",
    "keirin_round_not_ridden": ("With {n} entered this round is not ridden: the "
                                "UCI table takes «{last}» straight to the "
                                "finals."),
    "repechages_from_losers": ("The repechages are composed from the losers of "
                               "the 1st round, as soon as every heat has a "
                               "result."),
    "final_5_8_from_quarters": "The 5th-8th final is composed from the quarterfinals.",
    "quarters_from_winners": ("The quarterfinals are composed from the winners "
                              "of the heats and of the repechages, as soon as "
                              "every heat has a result."),

    # -- sheet notes the jury starts from ------------------------------------
    "events_settings_caption": ("What each event is: UCI code, format, "
                                "riders per team, how many start together, "
                                "what its column is called in the entry file. "
                                "These are the UCI values and they are the "
                                "same at every championship, so they are "
                                "written here once and not in every "
                                "programme. A programme that does otherwise "
                                "says so itself, and wins."),
    "events_saved": "Events saved in {path}.",
    "entry_book_caption": ("The list the whole meeting runs on: a sheet per "
                           "category with a column for each of its events, "
                           "plus the federal export kept whole. It is built "
                           "here, once, from the file the federation sends."),
    "entry_book_needs_categories": ("Categories first: a sheet per category "
                                    "cannot be written while there is no "
                                    "category. Tab «Categories, events and "
                                    "days»."),
    "entry_book_needs_events": ("Events first: the columns to tick are the "
                                "events of each category. Tab «Categories, "
                                "events and days»."),
    "entry_book_read_nothing": ("The file holds no rider this format can read. "
                                "Check the format you picked."),
    "entry_book_built": "Entry list built: {n} riders in `{path}`.",
    "map_columns_caption": ("Blue Band's fields on the left, the column of the "
                            "file each one is read from on the right. For a "
                            "file that names things its own way, or that puts "
                            "something in an unexpected column - the region "
                            "inside «Note», say. It holds for this competition "
                            "and is saved in its programme."),
    "map_columns_required": ("The starred fields are needed: without one of "
                             "them the entry list cannot be built."),
    "map_columns_ok": "Every column that is needed was found.",
    "map_columns_missing": ("Columns not found in the file: **{list}**. Map "
                            "them by hand."),
    "map_columns_no_file": ("Upload the file first: the columns on offer are "
                            "its own."),
    "map_columns_saved": "Mapping saved: {n} columns.",
    "prog_check_caption": ("What has come out, before saving: how big the "
                           "programme is, what is still missing, what does not "
                           "add up, and the file as it will be on disk."),
    "checks_caption": ("What the regulation limits: one row per sentence of "
                       "its article on entries - how many riders, teams or "
                       "pairs, and per what. The rules are counted over the "
                       "entry list and reported on Check and at the licence "
                       "desk: they warn, they never block."),
    "checks_none": ("No rules: the entries are not compared against any "
                    "limit."),
    "checks_count": "{n} rules in force out of {tot}.",
    "checks_legacy": ("{n} limits are still written in the old `quotas:` "
                      "block and hold all the same. Converting them makes "
                      "them editable here."),
    "checks_migrated": "{n} limits turned into rules.",
    "prog_check_clean": ("Nothing to report: the programme is consistent and "
                         "can be saved."),
    "entry_delta_none": ("The file changes nothing: same riders, same data. "
                         "Replacing is harmless but pointless."),
    "entry_delta_kept_checks": ("{n} riders keep the NP already "
                                "recorded."),
    "entry_merge_unreadable": ("`{path}` cannot be read as the entry list of "
                               "the competition, so there is no telling what "
                               "would change. Move it aside and import again."),
    "entry_book_needs_building": ("There is no entry list yet: it is built in **Programma → Gara**, once the categories and events are "
                                  "defined."),
    "entry_book_synced": "`{path}` now follows the programme.",
    "entry_book_sync_caption": ("Press it when you change categories or "
                                "events: the sheets and the columns follow, "
                                "and everything already ticked stays."),
    "entry_no_bibs": ("{n} riders have no bib in the file ({list}{more}). "
                      "Choose how to hand them out."),
    "assign_docs_caption": ("Which sheets each round files: the regulation "
                            "says it — a start order and its results, the "
                            "classification on the one that closes the event, "
                            "the repechage sheets where there are any. It is "
                            "written onto **every round of the programme** in "
                            "one go."),
    "docs_assigned": "Documents assigned: {n} rounds changed.",
    "communique_rules_caption": ("Which sheets travel on the same communiqué. "
                                "They hold for the whole competition and are "
                                "written into the file: here you only say "
                                "where this meeting differs from the table of "
                                "formats."),
    "recount_caption": ("The numbers follow the order the sheets can go out "
                        "in. Below is what would change: nothing is written "
                        "until you press."),
    "recount_counts": ("{moved} move · {added} new · {dropped} leave · {held} "
                       "stay where they are."),
    "recount_nothing": "Nothing to change in this view.",
    "recount_drops": ("{n} communiqués are no longer produced by the "
                      "programme and would be taken out. Issued, hand-typed "
                      "and annulled ones stay."),
    "register_behind": "the register is {n} lines behind the programme",
    "register_in_step": "the register follows the programme",
    "register_recounted": "Register recounted: {n} communiqués.",
    "sheet_lines_caption": ("The lines a communiqué opens on: what a heat "
                            "qualifies for, where the first team lines up. "
                            "They come out of the regulation and are the same "
                            "at every meeting, so they are written here once "
                            "and not in every programme. Which line goes on "
                            "which sheet is the regulation's; how it is worded "
                            "is decided here."),
    "sheet_line_default": "Shipped: {text}",
    "event_notes_moved": ("The lines this event used to put on every sheet are the regulation's now, round by round: they are read in **Schedule** and worded in **Settings → Sheet lines**. The ones the file carries still print."),
    "sheet_lines_saved": "Lines saved in {path}.",
    "sheet_lines_restored": "The lines the app ships are back.",
    "register_is_in_the_scaletta": ("The communiqué numbers of this day are "
                                    "typed in the running order above, next to "
                                    "the round that files them."),
    "laps_do_not_match": ("{km} km on a {track} m track is {expected} laps, "
                          "not {laps}: one of the two numbers is wrong."),
    "note_scheme_12": "The best 12 times qualify for the 1st round.",
    "note_scheme_8": "The best 8 times qualify straight for the quarterfinals.",
    "team_letter": "{where} team {letter}",
    "note_madison_startlist": ("The last {n} pairs among the starters do not "
                               "qualify for the final."),
    "note_madison_results": "The first {n} pairs classified go through to the final.",
    "note_omnium_startlist_m": ("The last {n} classified among the starters are "
                                "not admitted to the omnium races."),
    "note_omnium_startlist_f": ("The last {n} classified among the starters are "
                                "not admitted to the omnium races."),
    "note_omnium_results_m": ("The first {n} classified are admitted to the "
                              "omnium races."),
    "note_omnium_results_f": ("The first {n} classified are admitted to the "
                              "omnium races."),
    "note_sprint_round1_start": ("{winner} of each heat goes through to the "
                                 "quarterfinals, {others} to the repechages."),
    "note_sprint_round1_results": ("{winner} of each repechage heat goes "
                                   "through to the quarterfinals."),
    "note_sprint_repechage": ("Two runs + a decider. {winners} go through to "
                              "the semifinals, {others} to the final for "
                              "5th-8th place."),
    # -- pursuits and team sprint: where they start, what qualifies ---------
    "note_change_half_lap": "Change every half lap.",
    "note_qualify_teams": "The first {n} teams qualify for the finals.",
    "note_qualify_times": "The {n} fastest times qualify for the finals.",
    "note_first_team_finish": "The first team starts on the finishing straight.",
    "note_first_team_back": "The first team starts on the back straight.",
    "note_first_rider_m": "The first rider starts on the finishing straight.",
    "note_first_rider_f": "The first rider starts on the finishing straight.",
    "note_first_rider_back_m": "The first rider starts on the back straight.",
    "note_first_rider_back_f": "The first rider starts on the back straight.",
    "note_keirin_stage": "{round}: {heats} heats. {first} of each heat {to}{rest}",
    "note_keirin_repechages": ", {rest} to the repechages.",
    "note_keirin_rep_stage": ("Repechages: {heats} heats. {first} of each heat "
                              "{to}."),
    "winner_f": "The winner",
    "winner_m": "The winner",
    "winners_f": "The winners",
    "winners_m": "The winners",
    "others_f": "the others",
    "others_m": "the others",
    "first_n_f": "The first {n} classified",
    "first_n_m": "The first {n} classified",
    "goes_through_1": "goes through",
    "goes_through_n": "go through",
    "to_semifinals": "to the semifinals",
    "to_quarters": "to the quarterfinals",
    "to_round": "to «{round}»",
    "to_next": "through",
    "to_final_one": "to the final for {top} place",
    "to_final_two": "to the final for {top} place, {rest} to the final for {low} place",
    "and_final_5_8": " and the final for 5th-8th place",

    # -- decisions -----------------------------------------------------------
    "no_decisions": "No decision recorded.",
    "decision_empty": "Write the decision before recording it.",
    "decision_saved": "Decision no. {n} recorded.",
    "decision_removed": "Decision no. {n} deleted.",
    "decision_updated": "Decision no. {n} updated.",
    # the line a penalty goes on the sheet as, composed from the pickers
    "penalty_for": "{who}:",
    "penalty_rider": "{cat} {bib} {name}",
    "decision_of_race": "{cat} · {event}{round}",
    "decision_day": "day {day}",
    "no_penalties_table": "Penalty table not available.",
    "no_puis_table": "National infringement table not available.",
    # the W a rider carries through the event, and the second one
    "warned_carried": "Warned in this event: {bibs}.",
    "warned_twice": ("Two warnings in the same round: {bibs}. The regulations "
                     "call for disqualification."),
    "warned_none": "No warning in this event.",
    # which race the sidebar panel is filing a decision about
    "decision_of_this_race": "{cat} · {event} · {round}",
    # the compact recap above the button, one line per round
    "decision_recap_line": "{code} bib {bibs}",
    "decision_recap_note": "note",
    # the line under a classification that no longer lists them
    # the announcer's banner over a race against the clock
    "provisional_time": "{n} provisional time",

    # -- statistics ----------------------------------------------------------
    "stats_no_results": ("No event completed: the medal table is still empty."),
    "stats_nothing_selected": "No event in the chosen filter.",
    "stats_counting_unfinished": ("{n} events not completed are counted with "
                                  "the podium as it stands."),
    "stats_no_teams": ("No podium has a {what}: check the list of entries."),

    # -- printing ------------------------------------------------------------
    "chromium_missing": ("Chromium is not installed: the HTML will be saved "
                         "instead (printable with Ctrl+P)."),
    "pdf_no_browser": "No Chromium browser found: the PDF cannot be created.",
    "pdf_failed": "Chromium produced no PDF. {error}",
    "pdf_timeout": "Chromium stuck for {seconds} s on {dir}.",
    "saved_as": "Saved {name}",
    "saved_entry_lists": "{n} entry lists saved",
    "race_saved": "Race saved",
    "pairing_saved": "Pairing saved",
    "open_document": "Open {name}",

    # -- settings ------------------------------------------------------------
    "folder_not_a_dir": "{path} exists but is not a folder.",
    "folder_no_parent": "No part of the path {path} exists.",
    "folder_not_writable": "Write permission denied on {path}.",
    "folder_confirm": "Press «Save folder» to confirm.",
    "folder_saved": "The communiqués will be saved in {path}",
    "signature_file_missing": "File not found: the communiqués will come out unsigned.",
    "signature_name_missing": "Without a name the communiqués come out unsigned.",
    "image_missing": "File not found: the communiqué will come out without this image.",
    "signature_caption": "What is printed under «{label}» at the foot of the communiqué.",
    "appearance_caption": ("It holds for every sheet of this competition. Set "
                           "once and it stays: it is not part of the race "
                           "programme."),
    "letterhead_caption": ("Images printed at the top and the foot of every "
                           "communiqué sheet (SVG, PNG or JPEG). They do not "
                           "show on screen."),
    "sheet_slots_caption": ("The two lines that frame the table: the one under "
                            "the letterhead, above the title, and the one "
                            "above the footer. Three positions per line - "
                            "left, centre, right - and one item in each, or "
                            "none. The NON DEFINITIVO mark takes the place of "
                            "the communiqué number."),
    "communique_align_caption": ("The «Comunicato n.» box at the head of the "
                                 "sheet: where it sits, above the title. It holds "
                                 "for every communiqué of the meeting, the NON "
                                 "DEFINITIVO mark that takes its place included."),
    "fonts_caption": ("Which font and which colour every element of a "
                      "communiqué is set in: the family applies to the whole "
                      "sheet, the rest are sizes (`12pt`, `1.2em`). Pick the "
                      "element, set the value and the colour, press Set."),
    "font_default": "Default: {value}",
    "font_not_readable": ("\u00ab{value}\u00bb is not a font that can be "
                          "printed: a size is written with its unit (`12pt`, "
                          "`14px`, `1.2em`), a family as names separated by "
                          "commas."),
    "restore_appearance_caption": ("Puts **the whole look of the communiqués** "
                                   "- letterhead, lines, signature, names, "
                                   "colours and fonts - back to what the app "
                                   "ships. It touches neither the programme "
                                   "nor the communiqués already saved."),
    "appearance_restored": "Look of the communiqués restored ({n} settings).",
    "note_colors_caption": ("How each decision appears on the communiqué of "
                            "the round it was taken in: the colour of the "
                            "box, and whether to open it with the UCI code. "
                            "The note stays grey: it sanctions nobody."),
    "language_caption": ("What the app and the printed sheets are written in. "
                         "It is a setting of this competition, like the look "
                         "of the communiqués: what the programme spells out - "
                         "the names of the categories, the events and the "
                         "rounds - prints as it is written there."),
    "reset_caption": ("Deletes the saved results of an event: **every round**, "
                      "qualifying and heats included. It touches neither the "
                      "list of entries nor the licence check; the communiqués "
                      "already issued stay in the register, with their "
                      "number."),
    "no_event_for_category": "No event scheduled for {cat}.",
    "no_saved_race": "No race saved for this event: nothing to clear.",
    "races_reset": ("{n} races deleted ({cat} · {event}). The previous "
                    "versions stay in `.snapshots/`."),
    "backup_caption": ("Data folder: `{root}` - every save keeps the previous "
                       "version in `.snapshots/`. The documents produced go "
                       "into `{out}`."),
    "backup_done": "Copied into {path}",
    "no_findings": "Nothing to report.",

    # -- the programme file --------------------------------------------------
    "yaml_header": ("# {name}\n"
                    "#\n"
                    "# Written by the Programme page of Blue Band. The layout\n"
                    "# is generated: notes go in the `note:` fields, which\n"
                    "# survive a save - a comment does not.\n"),
    "yaml_day": "day {n}",
    "yaml_no_day": "no day",
    "yaml_competition": "competition",
    "yaml_entries": "list of entries: where the file is and what its columns are called",
    "yaml_branding": "letterhead, footer, signature",
    "yaml_categories": "categories",
    "yaml_events": "events",
    "yaml_quotas": "entry quotas (technical communiqué)",
    "yaml_checks": "entry checks (regulation)",
    "yaml_programme": "race programme",
    "yaml_communiques": "communiqué register",
    "communique_gaps": "Numbers unused in the register: {list}{more}",
    "communique_moved": ("Communiqué {n} was issued as «{was}»: in the "
                         "programme it is now «{now}». The sheet in the jury's "
                         "hands and the register would say two different "
                         "things."),
    "no_communique_planned": "{cat} {event}: no communiqué planned.",
    "round_without_day": "{cat} {event} · {round}: on no day of the programme.",
    "category_without_event": "{cat}: no event in the programme.",
    "day_without_race": "Day {day}{date}: no round in the programme.",
    "programme_count": "{races} races  ·  {rounds} rounds  ·  {days} days",
    "race_reproposed": "«{cat} {event}»: {n} rounds re-proposed.",
    "setup_needed": ("«{name}» has no programme yet. The programme is what "
                     "everything else comes out of: the categories, the events, "
                     "the rounds of every race and the communiqués. It is built "
                     "here, in three steps, and corrected whenever you like on "
                     "the Programma page."),
    "setup_track_holds": "On this track the madison holds {n} pairs in the final.",
    "setup_track_unknown": ("Length not in the table (3.2.157): how many pairs "
                            "ride the final is the jury's call."),
    "setup_done": "Programme created in {path}",
    "setup_no_categories": "Declare at least one category.",
    "competition_exists": "«{name}» already exists.",
    "competition_created": "«{name}» created.",
    "event_exists": "«{name}» is already in the programme.",
    "event_added": "«{name}» added.",
    "programme_saved": "Programme saved in {path}",
    "no_race_on_day": "No race scheduled on day {day}.",
    "all_rounds_on_day": "{cat} {event}: every round is already on day "
                         "{day}.",
    "category_in_programme": "{cat} has events in the programme: take those "
                             "off first.",
    "no_categories_yet": "No category yet: add one above.",
    "no_events_yet": "No event in the programme: tick one under a category.",
    "race_removed": "{cat} {event}: taken off the programme with its {n} "
                    "rounds.",
    "rounds_still_loose": "{n} rounds are on no day: {list}{more}",
    "declare_cats_and_events": ("Declare the categories and the events first, "
                                "in the Competition and Events tabs."),
    "docs_not_of_format": ("Documents a {fmt} format does not produce: {list}. "
                           "The sheet will come out empty."),
    "rounds_decided_on_the_day": ("How many of these rounds are actually ridden "
                                  "is decided by the number of entries "
                                  "(keirin: UCI table 3.2.135; sprint: the "
                                  "scheme chosen on the 200 m). What is "
                                  "declared here is which ones are possible."),

    # -- printed sheets ------------------------------------------------------
    "event_key": "Event codes:  {list}",
    "count_entered_starters": "{entered} entered / {starters} starters",
    "count_starters": "{n} starters",
    "count_documents": "{n} documents  ·  {issued} issued",
    "count_decisions": "{n} decisions",
    "count_medals": "{events} {concluded}  ·  {podiums} {podium}  ·  {teams} {team}",
    "medals_concluded_one": "event completed",
    "medals_concluded_many": "events completed",
    "medals_podium_one": "podium",
    "medals_podium_many": "podiums",
    "medals_team_one": "team",
    "medals_team_many": "teams",
    "medal_counting_note": ("Events not completed yet are counted with the "
                            "podium as it stands: the sheet is provisional."),
    "medal_open_events": "Events not completed yet:  {list}",
    "count_trofeo": "{events} {concluded}  ·  {teams} {team}  ·  {points} points",
    "trofeo_rule": ("Points per event: {table}.  Participation: 1 point per "
                    "starting rider, team or madison pair.  Ties: more races "
                    "won, then more participation points, then the better "
                    "score in the last event of the programme."),
    "trofeo_provisional_note": ("Events that are not completed are counted on "
                                "the standings so far: this sheet is "
                                "provisional."),
    "trofeo_open_events": "Events not completed yet:  {list}",
    "trofeo_counting_unfinished": ("{n} events that are not completed are "
                                   "counted in the standings: they are "
                                   "provisional."),
    "trofeo_no_scores": ("No event completed yet: the Trophy standings have "
                         "nothing to add up."),
    "count_recap": "{riders} riders  ·  {entries} entries",
    "recap_legend": ("Event codes:  {list}.    {marks}"),
    # what the cells say - it is read whatever the columns are headed by, so
    # it stands on its own line of the dictionary
    "recap_marks": ("In the cells: X entered, R reserve, A/B the pair or the "
                    "team in the pairings (AR = reserve of team A); the number "
                    "that follows is the heat, where it has already been "
                    "announced."),
    "no_teams": ("No team: the riders have no region and no club."),
    "heats_count": "{n} heats",
    "heat_one": "1 heat",

    "derny_no_passages": "No passings yet. Call the numbers: they show up here "
                         "in the order you type them.",
    "derny_passage_deleted": "Passing deleted.",
    "derny_unknown_bib": "Bib {bib} is not among the starters: not recorded.",
    "derny_log_saved": "Log updated.",
    "derny_passage_added": "Passing inserted.",
    "derny_prev_lap_done": "Lap before written again: {n} passings.",
    "derny_bad_bib": "\u201c{bib}\u201d is not a bib.",
    "derny_bad_clock": "\u201c{at}\u201d is not a time: write it as 10:41:07.3.",
    "derny_no_starters": ("Nobody is entered in this event: enter the riders "
                          "at the verification, then call the numbers."),
    "derny_laps_mismatch": ("Laps actually ridden by the leader: {done}. "
                            "The programme plans {planned}."),
    "derny_needs_times": "At least {n} lap times are needed for a mean and σ.",

}
